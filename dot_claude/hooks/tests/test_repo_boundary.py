#!/usr/bin/env python3
"""Exercise repo-boundary-guard.py against the real checkouts on this machine."""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path

HOOK = Path("/home/vincent/.claude/hooks/repo-boundary-guard.py")
STATE = Path.home() / ".cache" / "claude-code-repo-guard" / "pins"
TMP = Path(__file__).parent / "fixtures"

TYREX = Path("/home/vincent/code/tyrex")

failures: list[str] = []


def call(session: str, path: str, tool: str = "Edit", agent: str | None = None,
         key: str = "file_path", event: str = "PreToolUse") -> dict | None:
    payload = {
        "hook_event_name": event,
        "session_id": session,
        "tool_name": tool,
        "tool_input": {key: path},
        "cwd": str(TYREX),
        "permission_mode": "bypassPermissions",
    }
    if agent:
        payload["agent_id"] = agent
    proc = subprocess.run(
        [sys.executable, str(HOOK)],
        input=json.dumps(payload),
        capture_output=True,
        text=True,
        timeout=15,
    )
    assert proc.returncode == 0, f"hook exited {proc.returncode}: {proc.stderr}"
    out = proc.stdout.strip()
    if not out:
        return None
    return json.loads(out)


def decision(result: dict | None) -> str:
    if result is None:
        return "defer"
    return result["hookSpecificOutput"]["permissionDecision"]


def check(name: str, got: str, want: str, extra: str = "") -> None:
    ok = got == want
    print(f"  {'PASS' if ok else 'FAIL'}  {name}: {got}" + (f"  {extra}" if extra else ""))
    if not ok:
        failures.append(f"{name}: got {got}, want {want}")


def clean(*sessions: str) -> None:
    for s in sessions:
        (STATE / f"{s}.json").unlink(missing_ok=True)


print("== raw payload robustness")
for bad in ("", "not json", "[]", "{}"):
    proc = subprocess.run([sys.executable, str(HOOK)], input=bad,
                          capture_output=True, text=True, timeout=15)
    ok = proc.returncode == 0 and not proc.stdout.strip()
    print(f"  {'PASS' if ok else 'FAIL'}  malformed {bad!r} -> defer silently")
    if not ok:
        failures.append(f"malformed {bad!r}")

print("\n== tools and events outside scope are ignored")
clean("t-scope")
check("Read tool ignored", decision(call("t-scope", str(TYREX / "tyrex-dwc2/src/lib.rs"), tool="Read")), "defer")
check("PostToolUse ignored", decision(call("t-scope", str(TYREX / "tyrex-dwc2/src/lib.rs"), event="PostToolUse")), "defer")
ok = not (STATE / "t-scope.json").exists()
print(f"  {'PASS' if ok else 'FAIL'}  out-of-scope calls create no pin")
if not ok:
    failures.append("out-of-scope call pinned the session")

print("\n== ungoverned paths never pin")
clean("t-free")
check("scratchpad", decision(call("t-free", str(Path(__file__).parent / "note.md"))), "defer")
check("~/.claude/CLAUDE.md", decision(call("t-free", "/home/vincent/.claude/CLAUDE.md")), "defer")
check("/tmp work order", decision(call("t-free", "/tmp/x-work-order.md"))    , "defer")
check("flat checkout root", decision(call("t-free", str(TYREX / "CLAUDE.md"))), "defer")
check("als (no vcs markers)", decision(call("t-free", str(TYREX / "als/README.md"))), "defer")
ok = not (STATE / "t-free.json").exists()
print(f"  {'PASS' if ok else 'FAIL'}  no pin was created by ungoverned writes")
if not ok:
    failures.append("ungoverned write created a pin")

print("\n== chezmoi source dir is exempt")
clean("t-cm")
check("chezmoi template", decision(call("t-cm", "/home/vincent/.local/share/chezmoi/dot_claude/private_settings.json")), "defer")
ok = not (STATE / "t-cm.json").exists()
print(f"  {'PASS' if ok else 'FAIL'}  chezmoi source did not pin the session")
if not ok:
    failures.append("chezmoi source pinned the session")

print("\n== pin on first write, then confine")
clean("t-pin")
check("first write to tyrex-dwc2", decision(call("t-pin", str(TYREX / "tyrex-dwc2/src/lib.rs"))), "defer")
rec = json.loads((STATE / "t-pin.json").read_text())
ok = rec["root"] == str(TYREX / "tyrex-dwc2")
print(f"  {'PASS' if ok else 'FAIL'}  pinned root == {rec['root']}")
if not ok:
    failures.append("wrong pinned root")
check("same repo, another file", decision(call("t-pin", str(TYREX / "tyrex-dwc2/Justfile"))), "defer")
check("same repo, new nested file", decision(call("t-pin", str(TYREX / "tyrex-dwc2/src/deep/new.rs"))), "defer")
check("foreign repo tyrex-io", decision(call("t-pin", str(TYREX / "tyrex-io/src/lib.rs"))), "deny")
check("foreign repo frisk", decision(call("t-pin", str(TYREX / "frisk/README.md"))), "deny")
check("still free outside repos", decision(call("t-pin", "/tmp/note.md"))    , "defer")
check("Write tool, foreign", decision(call("t-pin", str(TYREX / "tyrex-io/x.rs"), tool="Write")), "deny")
check("MultiEdit, foreign", decision(call("t-pin", str(TYREX / "tyrex-io/x.rs"), tool="MultiEdit")), "deny")
check("NotebookEdit via notebook_path", decision(call("t-pin", str(TYREX / "tyrex-io/x.ipynb"), tool="NotebookEdit", key="notebook_path")), "deny")

res = call("t-pin", str(TYREX / "tyrex-io/src/lib.rs"))
reason = res["hookSpecificOutput"]["permissionDecisionReason"]
for token in ("tyrex-dwc2", "tyrex-io", "work-order", "Reads are not blocked"):
    ok = token in reason
    print(f"  {'PASS' if ok else 'FAIL'}  denial message mentions {token!r}")
    if not ok:
        failures.append(f"denial message missing {token!r}")
ok = "This session" in reason
print(f"  {'PASS' if ok else 'FAIL'}  main-session wording")
if not ok:
    failures.append("main-session wording")

print("\n== subagents inherit the parent pin (shared session_id)")
res = call("t-pin", str(TYREX / "tyrex-io/src/lib.rs"), agent="sub-1")
check("subagent foreign write", decision(res), "deny")
reason = res["hookSpecificOutput"]["permissionDecisionReason"]
ok = "This subagent" in reason
print(f"  {'PASS' if ok else 'FAIL'}  subagent wording")
if not ok:
    failures.append("subagent wording")
check("subagent inside pinned repo", decision(call("t-pin", str(TYREX / "tyrex-dwc2/src/x.rs"), agent="sub-1")), "defer")

print("\n== a subagent's first write pins the session too")
clean("t-sub-first")
check("subagent pins fresh session", decision(call("t-sub-first", str(TYREX / "frisk/src/main.rs"), agent="sub-9")), "defer")
check("parent then confined to it", decision(call("t-sub-first", str(TYREX / "tyrex-dwc2/src/lib.rs"))), "deny")

print("\n== real fixtures: building actual git/jj repos")
shutil.rmtree(TMP, ignore_errors=True)
TMP.mkdir(parents=True)


def run(*args: str) -> None:
    proc = subprocess.run(args, capture_output=True, text=True, timeout=120)
    assert proc.returncode == 0, f"{args!r} failed: {proc.stderr or proc.stdout}"


GIT_ID = ("-c", "user.email=t@t", "-c", "user.name=t")
# A real git repo with a real linked worktree.
(TMP / "main").mkdir()
run("git", "-C", str(TMP / "main"), "init", "-q")
run("git", "-C", str(TMP / "main"), *GIT_ID, "commit", "-q", "--allow-empty", "-m", "init")
run("git", "-C", str(TMP / "main"), "worktree", "add", "-q", str(TMP / "wt"), "-b", "wtb")
# A real submodule, added from a second local repo.
(TMP / "dep").mkdir()
run("git", "-C", str(TMP / "dep"), "init", "-q")
run("git", "-C", str(TMP / "dep"), *GIT_ID, "commit", "-q", "--allow-empty", "-m", "init")
run("git", "-C", str(TMP / "main"), *GIT_ID, "-c", "protocol.file.allow=always",
    "submodule", "add", "-q", str(TMP / "dep"), "sub")
# A real jj repo with a real secondary workspace (stores a RELATIVE pointer),
# plus a git worktree of that same repo. `jj git init` colocates, so this is
# the shape every checkout under ~/code/tyrex actually has.
run("jj", "git", "init", str(TMP / "jjmain"))
run("jj", "-R", str(TMP / "jjmain"), "workspace", "add", str(TMP / "jjws"))
run("git", "-C", str(TMP / "jjmain"), *GIT_ID, "commit", "-q", "--allow-empty", "-m", "seed")
run("git", "-C", str(TMP / "jjmain"), "worktree", "add", "-q", str(TMP / "jjwt"), "-b", "jjwtb")
print(f"  built: worktree, submodule, jj workspace, colocated repo under {TMP}")
for label, cond in (
    ("git worktree uses a real gitdir pointer file", (TMP / "wt/.git").is_file()),
    ("jj workspace uses a real repo pointer file", (TMP / "jjws/.jj/repo").is_file()),
    ("jj repo is colocated, like the real checkouts",
     (TMP / "jjmain/.git").exists() and (TMP / "jjmain/.jj").is_dir()),
    ("submodule uses a real gitdir pointer file", (TMP / "main/sub/.git").is_file()),
):
    print(f"  {'PASS' if cond else 'FAIL'}  {label}")
    if not cond:
        failures.append(label)

print("\n== git worktree of the pinned repo counts as the same repo")
clean("t-wt")
check("pin via main checkout", decision(call("t-wt", str(TMP / "main/src/a.rs"))), "defer")
check("write via linked worktree", decision(call("t-wt", str(TMP / "wt/src/a.rs"))), "defer")
clean("t-wt2")
check("pin via worktree first", decision(call("t-wt2", str(TMP / "wt/src/a.rs"))), "defer")
check("then main checkout allowed", decision(call("t-wt2", str(TMP / "main/src/a.rs"))), "defer")

print("\n== a submodule is its own repo")
clean("t-sm")
check("pin via superproject", decision(call("t-sm", str(TMP / "main/src/a.rs"))), "defer")
check("submodule write denied", decision(call("t-sm", str(TMP / "main/sub/src/a.rs"))), "deny")

print("\n== every view of one colocated repo collapses to the same identity")
clean("t-jj")
check("pin via primary workspace", decision(call("t-jj", str(TMP / "jjmain/a.rs"))), "defer")
check("write via secondary jj workspace", decision(call("t-jj", str(TMP / "jjws/a.rs"))), "defer")
check("write via git worktree of it", decision(call("t-jj", str(TMP / "jjwt/a.rs"))), "defer")
clean("t-jj2")
check("pin via secondary jj workspace", decision(call("t-jj2", str(TMP / "jjws/a.rs"))), "defer")
check("then primary allowed", decision(call("t-jj2", str(TMP / "jjmain/a.rs"))), "defer")
check("then its git worktree allowed", decision(call("t-jj2", str(TMP / "jjwt/a.rs"))), "defer")
check("but a different repo still denied", decision(call("t-jj2", str(TMP / "main/a.rs"))), "deny")

print("\n== symlink into a foreign repo is resolved, not evaded")
clean("t-link")
check("pin tyrex-dwc2", decision(call("t-link", str(TYREX / "tyrex-dwc2/src/lib.rs"))), "defer")
(TMP / "links").mkdir(parents=True, exist_ok=True)
link = TMP / "links/io"
if link.is_symlink():
    link.unlink()
link.symlink_to(TYREX / "tyrex-io")
check("write through symlink", decision(call("t-link", str(link / "src/lib.rs"))), "deny")

print("\n== hostile session_id cannot escape the state dir")
res = call("../../../../etc/evil", str(TYREX / "tyrex-io/src/lib.rs"))
check("path-traversal session_id defers", decision(res), "defer")
ok = not Path("/etc/evil.json").exists()
print(f"  {'PASS' if ok else 'FAIL'}  no file written outside the state dir")
if not ok:
    failures.append("session_id traversal")

clean("t-scope", "t-free", "t-cm", "t-pin", "t-sub-first", "t-wt", "t-wt2",
      "t-sm", "t-jj", "t-jj2", "t-link")
shutil.rmtree(TMP, ignore_errors=True)

leftover = sorted(p.name for p in STATE.glob("t-*.json"))
if leftover:
    print(f"  FAIL  test pins left behind: {leftover}")
    failures.append(f"leftover pins {leftover}")

print()
if failures:
    print(f"{len(failures)} FAILURE(S):")
    for f in failures:
        print(f"  - {f}")
    sys.exit(1)
print("all checks passed")

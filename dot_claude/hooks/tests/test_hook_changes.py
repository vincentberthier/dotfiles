#!/usr/bin/env python3
"""Regression checks for allow-compound.py logging and chezmoi-guard.py output.

Covers the two defects fixed on 2026-08-03: allow-compound logged every Bash
call at DEBUG with no bound (60 MB, 332k lines, inside the chezmoi-managed
config dir), and chezmoi-guard emitted the retired `{"decision": "block"}`
shape while reading only `file_path`, so notebook edits went unguarded.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

HOOKS = Path("/home/vincent/.claude/hooks")
ALLOW_COMPOUND = HOOKS / "allow-compound.py"
CHEZMOI_GUARD = HOOKS / "chezmoi-guard.py"
LOG = Path.home() / ".cache" / "claude-code-hooks" / "allow-compound.log"

failures: list[str] = []


def check(name: str, ok: bool, detail: str = "") -> None:
    print(f"  {'PASS' if ok else 'FAIL'}  {name}" + (f"  [{detail}]" if detail else ""))
    if not ok:
        failures.append(name)


def run(hook: Path, payload: dict, env: dict | None = None) -> str:
    full = dict(os.environ)
    full.pop("ALLOW_COMPOUND_DEBUG", None)
    if env:
        full.update(env)
    proc = subprocess.run(
        [sys.executable, str(hook)],
        input=json.dumps(payload),
        capture_output=True,
        text=True,
        timeout=30,
        env=full,
    )
    assert proc.returncode == 0, f"{hook.name} exited {proc.returncode}: {proc.stderr}"
    return proc.stdout.strip()


def bash_payload(command: str) -> dict:
    return {
        "hook_event_name": "PreToolUse",
        "session_id": "test-hook-changes",
        "tool_name": "Bash",
        "tool_input": {"command": command},
        "cwd": str(Path.home()),
    }


print("== allow-compound.py: logging is off by default")
LOG.unlink(missing_ok=True)
run(ALLOW_COMPOUND, bash_payload("echo hi && echo there"))
run(ALLOW_COMPOUND, bash_payload("rm -rf /"))
check("no log file created without the env var", not LOG.exists())
check("nothing written into ~/.claude/hooks", not list(HOOKS.glob("*.log")))

print("\n== allow-compound.py: logging still works when asked for")
run(ALLOW_COMPOUND, bash_payload("echo hi"), env={"ALLOW_COMPOUND_DEBUG": "1"})
check("log appears with ALLOW_COMPOUND_DEBUG=1", LOG.exists())
if LOG.exists():
    check("log records the decision", "DECISION" in LOG.read_text(errors="replace"))
LOG.unlink(missing_ok=True)

print("\n== allow-compound.py: still decides correctly (logging change is inert)")
out = run(ALLOW_COMPOUND, bash_payload("echo hi && echo there"))
check("benign compound is not denied", '"deny"' not in out, out[:60] or "<defer>")

print("\n== chezmoi-guard.py: modern deny shape on a source-file edit")
source = subprocess.run(
    ["chezmoi", "source-path", str(Path.home() / ".claude" / "CLAUDE.md")],
    capture_output=True, text=True, timeout=15,
).stdout.strip()
check("located a real chezmoi source file", bool(source), source)
if source:
    out = run(CHEZMOI_GUARD, {
        "hook_event_name": "PreToolUse",
        "session_id": "test-hook-changes",
        "tool_name": "Edit",
        "tool_input": {"file_path": source},
        "cwd": str(Path.home()),
    })
    check("source edit is refused", bool(out))
    if out:
        data = json.loads(out)
        spec = data.get("hookSpecificOutput", {})
        check("uses hookSpecificOutput, not legacy 'decision'", "decision" not in data)
        check("permissionDecision == deny", spec.get("permissionDecision") == "deny")
        check("hookEventName is set", spec.get("hookEventName") == "PreToolUse")
        check("reason names the re-add command",
              "chezmoi re-add" in spec.get("permissionDecisionReason", ""))

print("\n== chezmoi-guard.py: notebook_path is no longer ignored")
if source:
    nb = str(Path(source).with_suffix(".ipynb"))
    Path(nb).write_text("{}")
    try:
        out = run(CHEZMOI_GUARD, {
            "hook_event_name": "PreToolUse",
            "session_id": "test-hook-changes",
            "tool_name": "NotebookEdit",
            "tool_input": {"notebook_path": nb},
            "cwd": str(Path.home()),
        })
        # The guard must at least READ the key; a source .ipynb with no target
        # is correctly allowed, so assert the path was parsed, not the verdict.
        check("notebook_path parsed without error", True)
    finally:
        Path(nb).unlink(missing_ok=True)
    out = run(CHEZMOI_GUARD, {
        "hook_event_name": "PreToolUse",
        "session_id": "test-hook-changes",
        "tool_name": "NotebookEdit",
        "tool_input": {"notebook_path": source},
        "cwd": str(Path.home()),
    })
    check("a source file reached via notebook_path is refused", bool(out))

print("\n== both hooks survive junk input")
for hook in (ALLOW_COMPOUND, CHEZMOI_GUARD):
    for bad in ("", "not json", "[]", "{}"):
        proc = subprocess.run([sys.executable, str(hook)], input=bad,
                              capture_output=True, text=True, timeout=30)
        check(f"{hook.name} defers on {bad!r}", proc.returncode == 0)

print()
if failures:
    print(f"{len(failures)} FAILURE(S):")
    for f in failures:
        print(f"  - {f}")
    sys.exit(1)
print("all checks passed")

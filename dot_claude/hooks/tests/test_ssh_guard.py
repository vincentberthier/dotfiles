#!/usr/bin/env python3
"""Exercise ssh-guard.py: everything into ~/.ssh denied, everything else deferred."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

HOOK = Path("/home/vincent/.claude/hooks/ssh-guard.py")
HOME = str(Path.home())

failures: list[str] = []


def call(tool: str, tool_input, event: str = "PreToolUse") -> dict | None:
    payload = {
        "hook_event_name": event,
        "session_id": "test-ssh-guard",
        "tool_name": tool,
        "tool_input": tool_input,
        "cwd": HOME,
        "permission_mode": "bypassPermissions",
    }
    proc = subprocess.run(
        [sys.executable, str(HOOK)],
        input=json.dumps(payload),
        capture_output=True,
        text=True,
        timeout=15,
    )
    assert proc.returncode == 0, f"hook exited {proc.returncode}: {proc.stderr}"
    out = proc.stdout.strip()
    return json.loads(out) if out else None


def decision(result: dict | None) -> str:
    if result is None:
        return "defer"
    return result["hookSpecificOutput"]["permissionDecision"]


def check(name: str, got: str, want: str) -> None:
    ok = got == want
    print(f"  {'PASS' if ok else 'FAIL'}  {name}: {got}")
    if not ok:
        failures.append(f"{name}: got {got}, want {want}")


def path_case(name: str, path: str, want: str, tool: str = "Read") -> None:
    key = "notebook_path" if tool == "NotebookEdit" else "file_path"
    check(name, decision(call(tool, {key: path})), want)


def bash_case(name: str, command: str, want: str) -> None:
    check(name, decision(call("Bash", {"command": command})), want)


print("\nfile tools -- ssh paths in every spelling")
path_case("tilde", "~/.ssh/config", "deny")
path_case("absolute", f"{HOME}/.ssh/config", "deny")
path_case("the directory itself", "~/.ssh", "deny")
path_case("nested config.d", "~/.ssh/config.d/tyrex", "deny")
path_case("private key", "~/.ssh/id_ed25519", "deny")
path_case("known_hosts", "~/.ssh/known_hosts", "deny")
path_case("another user's", "/home/someone/.ssh/config", "deny")
path_case("root's", "/root/.ssh/authorized_keys", "deny")
path_case("$HOME unexpanded", "$HOME/.ssh/config", "deny")
path_case("chezmoi source", "~/.local/share/chezmoi/private_dot_ssh/private_config", "deny")
path_case("via Edit", "~/.ssh/config", "deny", tool="Edit")
path_case("via Write", "~/.ssh/config", "deny", tool="Write")
path_case("via MultiEdit", "~/.ssh/config", "deny", tool="MultiEdit")
path_case("via NotebookEdit", "~/.ssh/x.ipynb", "deny", tool="NotebookEdit")

print("\nfile tools -- innocent paths stay free")
path_case("global CLAUDE.md", "~/.claude/CLAUDE.md", "defer")
path_case("a repo file", "/home/vincent/code/tyrex/CLAUDE.md", "defer")
path_case("/etc/ssh is host config", "/etc/ssh/sshd_config", "defer")
path_case("a file merely named .ssh", "/home/vincent/notes/backup.sshkeys", "defer")
path_case("ssh in a filename", "/home/vincent/docs/ssh-setup.md", "defer")
path_case("dot_sshd is not dot_ssh", "~/.local/share/chezmoi/dot_sshd_notes", "defer")

print("\nbash -- naming the directory, however it is written")
bash_case("cat", "cat ~/.ssh/config", "deny")
bash_case("rg into it", "rg -n Host ~/.ssh/config", "deny")
bash_case("eza listing", "eza -la ~/.ssh", "deny")
bash_case("fd inside it", "fd . ~/.ssh", "deny")
bash_case("$HOME form", 'rg Host "$HOME/.ssh/config"', "deny")
bash_case("absolute form", f"wc -l {HOME}/.ssh/config", "deny")
bash_case("~user form", "cat ~vincent/.ssh/config", "deny")
bash_case("quoted around the dot", "cat ~/'.ssh'/config", "deny")
bash_case("fully quoted", 'cat "~/.ssh/config"', "deny")
bash_case("second in a pipeline", "echo hi && cat ~/.ssh/config", "deny")
bash_case("chezmoi source", "chezmoi cat ~/.local/share/chezmoi/private_dot_ssh/private_config", "deny")
bash_case("chezmoi re-add of it", "chezmoi re-add ~/.ssh/config", "deny")
bash_case("python reading it", "python3 -c \"print(open('/home/vincent/.ssh/config').read())\"", "deny")

print("\nbash -- content searches rooted at $HOME reach it without naming it")
bash_case("rg over ~", "rg -n password ~", "deny")
bash_case("rg over $HOME", "rg -n password $HOME", "deny")
bash_case("rg over the absolute home", f"rg -n password {HOME}", "deny")
bash_case("grep -r over ~", "grep -r password ~", "deny")

print("\nbash -- normal work is untouched")
bash_case("ssh to a host", "ssh tyrex-gl01-dev.kub.local uptime", "defer")
bash_case("ssh-keygen version", "ssh-keygen -V", "defer")
bash_case("host resolution", "getent hosts tyrex-gl01-dev.kub.local", "defer")
bash_case("git over ssh", "git clone ssh://git@host/repo.git", "defer")
bash_case("rg in a repo", "rg -n TODO /home/vincent/code/tyrex", "defer")
bash_case("rg under ~/.claude", "rg -n hooks ~/.claude/settings.json", "defer")
bash_case("fd in home is not a content search", "fd -t f -d 1 . ~", "defer")
bash_case("just ci", "just ci", "defer")

print("\nsubagent dispatch")
check(
    "Agent prompt naming it",
    decision(call("Agent", {"prompt": "check what ~/.ssh/config says about that host"})),
    "deny",
)
check(
    "Task prompt naming it",
    decision(call("Task", {"prompt": "read /home/vincent/.ssh/known_hosts"})),
    "deny",
)
check(
    "innocent Agent prompt",
    decision(call("Agent", {"prompt": "find where the CI justfile lives"})),
    "defer",
)

print("\nfailure modes")
check("unreadable input fails closed", decision(call("Read", "not-a-dict")), "deny")
check("wrong event defers", decision(call("Read", {"file_path": "~/.ssh/config"}, event="PostToolUse")), "defer")
check("ungoverned tool defers", decision(call("WebFetch", {"url": "https://example.com/.ssh"})), "defer")
check("Bash with no command defers", decision(call("Bash", {})), "defer")

print()
if failures:
    print(f"{len(failures)} FAILURE(S):")
    for failure in failures:
        print(f"  - {failure}")
    sys.exit(1)
print("all checks passed")

#!/usr/bin/env python3
"""Checks for process-wait-guard.py.

The bug it guards: `pgrep -f 'just ci'` in a wait loop matches the very shell
running the loop, so the waiter never exits. Two got stuck at once on
2026-08-07 and had to be killed by hand.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

HOOK = Path("/home/vincent/.claude/hooks/process-wait-guard.py")

failures: list[str] = []


def check(name: str, ok: bool, detail: str = "") -> None:
    print(f"  {'PASS' if ok else 'FAIL'}  {name}" + (f"  [{detail}]" if detail else ""))
    if not ok:
        failures.append(name)


def verdict(command: str) -> str | None:
    """Return the permissionDecision for a Bash command, or None if deferred."""
    proc = subprocess.run(
        [sys.executable, str(HOOK)],
        input=json.dumps({
            "hook_event_name": "PreToolUse",
            "session_id": "test-process-wait-guard",
            "tool_name": "Bash",
            "tool_input": {"command": command},
            "cwd": str(Path.home()),
        }),
        capture_output=True, text=True, timeout=30,
    )
    assert proc.returncode == 0, f"exited {proc.returncode}: {proc.stderr}"
    if not proc.stdout.strip():
        return None
    return json.loads(proc.stdout)["hookSpecificOutput"]["permissionDecision"]


print("== denies self-matching waiters")
for cmd in (
    "until ! pgrep -f 'ci-tools|just ci'; do sleep 5; done",
    "pgrep -f 'just ci'",
    "pgrep --full 'just ci'",
    "while pgrep -fa cargo; do sleep 1; done",
    "pkill -f 'just ci'",
    "ps aux | grep ci-tools",
    "ps -ef | rg 'just ci'",
    "echo start && pgrep -f build.sh",
):
    check(f"deny: {cmd}", verdict(cmd) == "deny")

print("\n== allows precise queries and unrelated commands")
for cmd in (
    "pgrep -Af 'just ci'",
    "pgrep --ignore-ancestors -f 'just ci'",
    "pgrep -f -P 12345 cargo",
    "pgrep -F /var/tmp/ci.pid -f cargo",
    "pgrep -x cargo",
    "pgrep cargo",
    "ps aux | grep -v grep | grep ci-tools",
    "ps aux | grep '[c]i-tools'",
    "ps aux",
    "docker ps | grep runner",
    "rg -n 'pgrep -f' /home/vincent/.claude/hooks",
    "just ci > /var/tmp/ci.log 2>&1; echo $? > /var/tmp/ci.done",
):
    check(f"allow: {cmd}", verdict(cmd) is None, str(verdict(cmd)))

print("\n== the denial message names the real fixes")
proc = subprocess.run(
    [sys.executable, str(HOOK)],
    input=json.dumps({
        "hook_event_name": "PreToolUse", "tool_name": "Bash",
        "tool_input": {"command": "pgrep -f 'just ci'"},
    }),
    capture_output=True, text=True, timeout=30,
)
reason = json.loads(proc.stdout)["hookSpecificOutput"]["permissionDecisionReason"]
check("points at run_in_background", "run_in_background" in reason)
check("points at polling an artifact", "artifact" in reason.lower())
check("names -A / --ignore-ancestors", "--ignore-ancestors" in reason)
check("warns -A is not enough on its own", "second copy" in reason)

print("\n== ignores other tools and junk input")
proc = subprocess.run(
    [sys.executable, str(HOOK)],
    input=json.dumps({
        "hook_event_name": "PreToolUse", "tool_name": "Read",
        "tool_input": {"file_path": "/etc/hostname"},
    }),
    capture_output=True, text=True, timeout=30,
)
check("defers on non-Bash tools", proc.returncode == 0 and not proc.stdout.strip())
for bad in ("", "not json", "[]", "{}", '{"tool_name":"Bash","tool_input":null}'):
    proc = subprocess.run([sys.executable, str(HOOK)], input=bad,
                          capture_output=True, text=True, timeout=30)
    check(f"defers on {bad!r}", proc.returncode == 0)
check("defers on unbalanced quotes", verdict("pgrep -f 'unclosed") is None)

print()
if failures:
    print(f"{len(failures)} FAILURE(S):")
    for f in failures:
        print(f"  - {f}")
    sys.exit(1)
print("all checks passed")

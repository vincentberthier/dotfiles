#!/usr/bin/env python3
"""Checks for pipe-truncation-guard.py.

The bug it guards: `just ci 2>&1 | tail -50` reports tail's exit status (always
0) and throws away every line above the window, so a failed build reads as a
clean one and there is nothing left to re-read.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

HOOK = Path("/home/vincent/.claude/hooks/pipe-truncation-guard.py")

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
            "session_id": "test-pipe-truncation-guard",
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


print("== denies a build/test run piped into a filter")
for cmd in (
    'TMPDIR=/var/tmp CI_VARIANT=rust just ci 2>&1 | tail -50',
    'just ci | tail -50',
    'cargo test 2>&1 | tail -n 100',
    'cargo build 2>&1 | rg error',
    'make -j8 2>&1 | head -40',
    'pytest 2>&1 | tail -20',
    'uv run pytest -q 2>&1 | wc -l',
    'npm run build 2>&1 | less',
    'go test ./... 2>&1 | grep FAIL',
    'docker build . 2>&1 | tail -30',
    'cargo clippy --all 2>&1 | tail -50 | rg warning',
    'echo start && just ci 2>&1 | tail -50',
    '/usr/bin/cargo test 2>&1 | tail -5',
    'just ci 2>&1 | tail -50; echo "exit=${PIPESTATUS[0]}"',
    'set -o pipefail; just ci 2>&1 | tail -50',
    'just ci 2>&1 | tail -50 > /var/tmp/ci.log',
):
    check(f"deny: {cmd}", verdict(cmd) == "deny")

print("\n== allows the log-file forms")
for cmd in (
    'just ci >/var/tmp/ci.log 2>&1; echo "exit=$?"',
    'set -o pipefail; just ci 2>&1 | tee /var/tmp/ci.log | tail -50',
    'set -o pipefail; cargo test 2>&1 | tee "$LOG" | rg error',
    'just ci 2>&1 | tee /var/tmp/ci.log | tail -50; echo ${PIPESTATUS[0]}',
    'cargo build 2>build.log; rg -n error build.log',
):
    check(f"allow: {cmd}", verdict(cmd) is None)

print("\n== allows query pipelines that share the same binaries")
for cmd in (
    'cargo tree | rg serde',
    'cargo metadata --format-version 1 | jq .packages',
    'cargo --version | head -1',
    'just --list | rg ci',
    'make -n | head -20',
    'npm ls | rg typescript',
    'go list ./... | wc -l',
    'docker ps | rg postgres',
    'make help | rg test',
):
    check(f"allow: {cmd}", verdict(cmd) is None)

print("\n== leaves unrelated pipelines alone")
for cmd in (
    'rg -n TODO src | head -20',
    'git log --oneline | head -30',
    'eza -l /var/tmp | tail',
    'fd -e rs | wc -l',
    'just ci',
    'cargo test',
    'ps aux | rg cargo',
    'printf "a\\nb\\n" | tail -1',
):
    check(f"allow: {cmd}", verdict(cmd) is None)

print("\n== fails open on junk")
for cmd in (
    "just ci 2>&1 | tail -50 'unbalanced",
    "",
):
    check(f"defer: {cmd!r}", verdict(cmd) is None)

print("\n== the suggested command is runnable as printed")


def reason(command: str) -> str:
    proc = subprocess.run(
        [sys.executable, str(HOOK)],
        input=json.dumps({"tool_name": "Bash", "tool_input": {"command": command}}),
        capture_output=True, text=True, timeout=30,
    )
    out = json.loads(proc.stdout)
    return out["hookSpecificOutput"]["permissionDecisionReason"]


msg = reason("TMPDIR=/var/tmp CI_VARIANT=rust just ci 2>&1 | tail -50")
check("keeps the env assignments", "TMPDIR=/var/tmp CI_VARIANT=rust just ci" in msg)
check("strips the source redirect", '2>&1 >"$LOG"' not in msg)
check("redirects stdout then dups stderr", 'just ci >"$LOG" 2>&1' in msg)
check("no doubled dup in the tee form", "2>&1 2>&1" not in msg)
check("names the real command in the tee form", "just ci 2>&1 | tee" in msg)

print("\n== survives junk input")
for bad in ("", "not json", "[]", "{}", '{"tool_input": "nope"}'):
    proc = subprocess.run([sys.executable, str(HOOK)], input=bad,
                          capture_output=True, text=True, timeout=30)
    check(f"defers on {bad!r}", proc.returncode == 0 and not proc.stdout.strip())

print()
if failures:
    print(f"FAILED ({len(failures)}): " + ", ".join(failures))
    sys.exit(1)
print("all checks passed")

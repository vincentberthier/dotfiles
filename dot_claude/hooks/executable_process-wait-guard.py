#!/usr/bin/env python3
"""Claude Code PreToolUse hook: block waiters that can match themselves.

The recurring failure: an agent wants to wait for a long job, so it polls the
process table by command-line substring —

    until ! pgrep -f 'ci-tools|just ci'; do sleep 5; done

`pgrep -f` matches against /proc/*/cmdline, and the shell running that loop has
the pattern *in its own cmdline* (`bash -c "until ! pgrep -f 'just ci' ..."`).
pgrep skips its own PID but not its ancestors, so the loop matches itself and
can never exit. It hangs until someone kills it by hand. Two of them once got
stuck at the same time — and once two exist, each one also matches the other,
so even excluding ancestors would not have saved it.

The same bug in its older costume is `ps aux | grep foo`, where grep finds its
own command line in the ps output.

Caught, in Bash commands and in the content written to shell-ish files:
  - `pgrep -f` / `pkill -f` with no precise selector (-A, -p, -P, -F)
  - `ps ... | grep PATTERN` with no `-v` and no bracket trick

File scanning is deliberately narrow: only files that get executed as shell
(*.sh, Justfile, Makefile, CI YAML, …), never Markdown or source, because
prose about this bug — including this docstring — must stay writable. The
hooks directory itself is exempt for the same reason.

Fails open (exit 0, no output) on anything it cannot parse — a guard that
wedges Bash is worse than the bug it guards against.
"""

from __future__ import annotations

import json
import re
import shlex
import sys
from pathlib import PurePosixPath

# Shell tokens that end one simple command and start another.
_OPERATORS = {"|", "||", "&&", ";", "&", "|&", "(", ")", "{", "}", "\n"}

# Operators that pipe stdout of the previous command into the next one.
_PIPES = {"|", "|&"}

_PROC_MATCHERS = {"pgrep", "pkill"}
_GREPS = {"grep", "egrep", "fgrep", "rg", "ag", "ack"}

_SHORT_BUNDLE = re.compile(r"^-[a-zA-Z]+$")
# The bracket trick: `grep [c]i-tools` cannot match its own cmdline.
_BRACKETED = re.compile(r"\[[^\]]+\]")
# Words that can sit in front of the real command word: shell keywords, the
# negation operator, and wrappers. `until ! pgrep -f X` is still a pgrep call.
_PREFIXES = {
    "!", "until", "while", "if", "elif", "then", "do", "else", "time",
    "command", "builtin", "exec", "nohup", "setsid", "doas", "sudo", "xargs",
}
_ASSIGNMENT = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*=")

# File content is only scanned when the file is executed as shell. Markdown,
# source code and config that merely mentions pgrep must stay writable.
_SHELLISH_SUFFIXES = {
    ".sh", ".bash", ".zsh", ".fish", ".ksh", ".just", ".mk", ".yml", ".yaml",
}
_SHELLISH_NAMES = {
    "justfile", "makefile", "gnumakefile", "dockerfile", "containerfile",
}
# The guard and its tests must be able to spell out the pattern they catch.
_EXEMPT_PREFIXES = ("/home/vincent/.claude/hooks/",)

# Leading noise before a command: indentation, YAML list dashes, make/just
# recipe prefixes (@ silent, - ignore-error, + always-run). Make attaches its
# prefix directly to the command (`-cmd`), YAML puts a space after it.
_LINE_PREFIX = re.compile(r"^\s*(?:[-@+]\s*)*")

_FILE_TOOLS = {"Write", "Edit", "MultiEdit", "NotebookEdit"}

FILE_REASON = """Blocked: {path} would contain a waiter that can match itself.

A script hangs the same way a typed command does — worse, because it hangs
every future run of that script, not just this one.

"""

REASON = """Blocked: this waits on a process by command-line substring, which can match itself.

`pgrep -f` reads /proc/*/cmdline, and the shell running your command has the
pattern in ITS cmdline. pgrep skips its own PID, never its ancestors — so the
check reports "still running" forever and the waiter hangs until it is killed
by hand. `ps aux | grep foo` is the same bug (grep matches its own line).

Use, in this order:

1. Do not hand-roll a waiter. Run the job with Bash `run_in_background: true`
   and let the harness re-invoke you when it exits; fill the wait with other
   work. Or use the Monitor tool to wait on a condition.

2. If you must poll, poll the ARTIFACT, not the process table — a marker the
   job itself writes, and only writes when it is done:
       just ci >/var/tmp/ci.log 2>&1; echo $? >/var/tmp/ci.done
   then poll for /var/tmp/ci.done. It cannot match itself.

3. If you started the process here, wait on its PID, not its name:
       cmd & pid=$!; wait $pid          # or: while kill -0 $pid; do ...

4. Only if you genuinely must read the process table, make the query precise:
       pgrep -Af PATTERN                # -A = --ignore-ancestors
       pgrep -P <ppid> / -p <pid> / -F <pidfile>
       ps aux | grep -v grep | grep PATTERN     (or grep '[P]ATTERN')
   Note -A excludes only YOUR ancestors: a second copy of the same waiter
   still matches you and you still deadlock. Prefer 1-3."""


def _tokenize(command: str) -> list[str] | None:
    try:
        lexer = shlex.shlex(command, posix=True, punctuation_chars=True)
        lexer.whitespace_split = True
        return list(lexer)
    except ValueError:
        # Unbalanced quotes etc. — defer to normal permissions.
        return None


def _segments(tokens: list[str]) -> list[tuple[str | None, list[str]]]:
    """Split tokens into simple commands, each tagged with the operator before it."""
    out: list[tuple[str | None, list[str]]] = []
    op: str | None = None
    seg: list[str] = []
    for tok in tokens:
        if tok in _OPERATORS:
            out.append((op, seg))
            op, seg = tok, []
            continue
        seg.append(tok)
    out.append((op, seg))
    return [(o, s) for o, s in out if s]


def _basename(tok: str) -> str:
    return tok.rsplit("/", 1)[-1]


def _head(seg: list[str]) -> tuple[str, list[str]] | None:
    """Return (command word, args) for a simple command, or None if there is none.

    Skips leading keywords and env assignments, so `until ! pgrep -f X` and
    `FOO=1 pgrep -f X` both report `pgrep`.
    """
    for i, tok in enumerate(seg):
        if tok in _PREFIXES or _ASSIGNMENT.match(tok):
            continue
        return _basename(tok), seg[i + 1:]
    return None


def _short_flags(args: list[str]) -> set[str]:
    """Every letter appearing in a single-dash flag bundle."""
    letters: set[str] = set()
    for tok in args:
        if _SHORT_BUNDLE.match(tok):
            letters.update(tok[1:])
    return letters


def _unsafe_proc_matcher(args: list[str]) -> bool:
    """True for a pgrep/pkill that matches full cmdlines with no precise selector."""
    letters = _short_flags(args)
    matches_full = "f" in letters or any(
        a == "--full" or a.startswith("--full=") for a in args
    )
    if not matches_full:
        return False
    # Selectors that pin the query to specific processes rather than a substring.
    safe_letters = {"A", "p", "P", "F"}
    if letters & safe_letters:
        return False
    safe_long = ("--ignore-ancestors", "--pid", "--parent", "--pidfile")
    if any(a == long or a.startswith(long + "=") for a in args for long in safe_long):
        return False
    return True


def _pipelines(
    segments: list[tuple[str | None, list[str]]],
) -> list[list[tuple[str, list[str]]]]:
    """Group simple commands into pipelines, dropping ones with no command word."""
    out: list[list[tuple[str, list[str]]]] = []
    for op, seg in segments:
        head = _head(seg)
        if head is None:
            continue
        if op in _PIPES and out:
            out[-1].append(head)
        else:
            out.append([head])
    return out


def _filters_out_grep(cmd: str, args: list[str]) -> bool:
    """True for the `grep -v grep` guard clause that sanitises a ps pipeline."""
    if cmd not in _GREPS:
        return False
    letters = _short_flags(args)
    if "v" not in letters and "--invert-match" not in args:
        return False
    return any("grep" in a for a in args if not a.startswith("-"))


def _unsafe_ps_grep(pipeline: list[tuple[str, list[str]]]) -> bool:
    """True for `ps ... | grep PATTERN` with nothing to stop grep matching itself."""
    if any(_filters_out_grep(cmd, args) for cmd, args in pipeline):
        return False
    saw_ps = False
    for cmd, args in pipeline:
        if cmd == "ps":
            saw_ps = True
            continue
        if not saw_ps or cmd not in _GREPS:
            continue
        if any(_BRACKETED.search(a) for a in args):
            continue
        return True
    return False


def command_is_self_matching_waiter(command: str) -> bool:
    tokens = _tokenize(command)
    if tokens is None:
        return False
    for pipeline in _pipelines(_segments(tokens)):
        for cmd, args in pipeline:
            if cmd in _PROC_MATCHERS and _unsafe_proc_matcher(args):
                return True
        if _unsafe_ps_grep(pipeline):
            return True
    return False


def _is_shellish(path: str) -> bool:
    """True if this file is executed as shell, so its lines are commands."""
    if not path or path.startswith(_EXEMPT_PREFIXES):
        return False
    name = PurePosixPath(path).name.lower()
    if name in _SHELLISH_NAMES:
        return True
    return PurePosixPath(name).suffix in _SHELLISH_SUFFIXES


def content_has_self_matching_waiter(text: str) -> bool:
    """Scan written file content line by line for the same footgun."""
    for raw in text.splitlines():
        line = _LINE_PREFIX.sub("", raw).strip()
        if not line or line.startswith("#"):
            continue
        if command_is_self_matching_waiter(line):
            return True
    return False


def _written_text(tool: str, tool_input: dict) -> str:
    """The text this call introduces — never the text it replaces."""
    if tool == "Write":
        return str(tool_input.get("content", ""))
    if tool == "Edit":
        return str(tool_input.get("new_string", ""))
    if tool == "NotebookEdit":
        return str(tool_input.get("new_source", ""))
    if tool == "MultiEdit":
        edits = tool_input.get("edits")
        if not isinstance(edits, list):
            return ""
        return "\n".join(
            str(e.get("new_string", "")) for e in edits if isinstance(e, dict)
        )
    return ""


def _deny(reason: str) -> None:
    print(json.dumps({
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "deny",
            "permissionDecisionReason": reason,
        }
    }))


def main() -> int:
    try:
        payload = json.load(sys.stdin)
    except (json.JSONDecodeError, ValueError):
        return 0
    if not isinstance(payload, dict):
        return 0
    tool = payload.get("tool_name")
    tool_input = payload.get("tool_input")
    if not isinstance(tool_input, dict):
        return 0

    if tool == "Bash":
        text = str(tool_input.get("command", ""))
        scan = command_is_self_matching_waiter
        reason = REASON
    elif tool in _FILE_TOOLS:
        path = tool_input.get("file_path") or tool_input.get("notebook_path") or ""
        if not _is_shellish(str(path)):
            return 0
        text = _written_text(tool, tool_input)
        scan = content_has_self_matching_waiter
        reason = FILE_REASON.format(path=path) + REASON
    else:
        return 0

    # Cheap pre-filter: nothing to do unless one of the risky words is present.
    if not text or not any(w in text for w in ("pgrep", "pkill", "ps ")):
        return 0
    if scan(text):
        _deny(reason)
    return 0


if __name__ == "__main__":
    sys.exit(main())

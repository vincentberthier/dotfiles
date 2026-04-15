#!/usr/bin/env python3
"""Claude Code PreToolUse hook: auto-allow compound Bash commands
when every sub-command is individually in the allowed set.

Handles: &&, ||, ;, | operators and $(...) / backtick subshells.
If parsing fails or any command is unknown, defers to normal permissions.
"""

import json
import logging
import re
import sys
from pathlib import Path

_LOG_PATH = Path.home() / ".claude" / "hooks" / "allow-compound.log"
logging.basicConfig(
    filename=str(_LOG_PATH),
    level=logging.DEBUG,
    format="%(asctime)s %(message)s",
)
log = logging.getLogger(__name__)

SETTINGS_PATH = Path.home() / ".claude" / "settings.json"
BASH_PATTERN = re.compile(r"^Bash\((\S+?):\*\)$")

# Tools that are safe to use as pipe filters (read-only, no side effects).
# These are exempt from the deny list when they appear after a pipe (|).
PIPE_SAFE = frozenset({
    "awk", "cat", "column", "cut", "diff", "df", "du", "fold",
    "grep", "head", "jq", "less", "ls", "nl", "paste", "rev",
    "rg", "sed", "sort", "tac", "tail", "tr", "uniq", "wc",
})

# Commands that have dedicated tools and should be denied when used standalone,
# but allowed as pipe filters. Maps command name → preferred tool name.
TOOL_NUDGE = {
    "grep": "Grep",
    "find": "Glob",
    "ls": "Glob",
    "sed": "Edit",
}

# Pure read-only commands removed from the deny list. No dedicated tool
# alternative exists, so they're always allowed (no nudge needed).
PURE_READONLY = frozenset({"df", "diff", "du"})


def load_command_sets() -> tuple[set[str], set[str]]:
    """Read allowed/denied base command names from settings.json."""
    allowed = set()
    denied = set()
    try:
        settings = json.loads(SETTINGS_PATH.read_text())
    except (OSError, json.JSONDecodeError):
        return allowed, denied

    perms = settings.get("permissions", {})
    for entry in perms.get("allow", []):
        m = BASH_PATTERN.match(entry)
        if m:
            allowed.add(m.group(1))
    for entry in perms.get("deny", []):
        m = BASH_PATTERN.match(entry)
        if m:
            denied.add(m.group(1))
    return allowed, denied


def extract_subshells(cmd: str) -> tuple[str, list[str]] | None:
    """Strip $(...) and backtick subshells, returning the outer command
    with subshells blanked out, plus a list of inner command strings.
    Returns None on parse failure (unmatched delimiters)."""
    inners = []
    result = _extract_dollar_parens(cmd, inners)
    if result is None:
        return None
    result = _extract_backticks(result, inners)
    if result is None:
        return None
    return result, inners


def _extract_dollar_parens(cmd: str, inners: list[str]) -> str | None:
    while True:
        start = _find_unquoted(cmd, "$(")
        if start is None:
            return cmd
        end = _find_matching_paren(cmd, start + 2)
        if end is None:
            return None
        inner = cmd[start + 2 : end]
        cmd = cmd[:start] + " __sub__ " + cmd[end + 1 :]
        inners.append(inner)


def _extract_backticks(cmd: str, inners: list[str]) -> str | None:
    while True:
        start = _find_unquoted(cmd, "`")
        if start is None:
            return cmd
        end = _find_unquoted(cmd, "`", start + 1)
        if end is None:
            return None
        inner = cmd[start + 1 : end]
        cmd = cmd[:start] + " __sub__ " + cmd[end + 1 :]
        inners.append(inner)


def _find_unquoted(cmd: str, needle: str, start: int = 0) -> int | None:
    """Find needle in cmd, skipping single-quoted regions."""
    i = start
    in_single = False
    in_double = False
    while i < len(cmd):
        c = cmd[i]
        if c == "'" and not in_double:
            in_single = not in_single
        elif c == '"' and not in_single:
            in_double = not in_double
        elif c == "\\" and not in_single and i + 1 < len(cmd):
            i += 2
            continue
        elif not in_single and not in_double:
            if cmd[i : i + len(needle)] == needle:
                return i
        i += 1
    return None


def _find_matching_paren(cmd: str, start: int) -> int | None:
    """Find the ) that closes the $( at position start, handling nesting."""
    depth = 1
    i = start
    in_single = False
    in_double = False
    while i < len(cmd):
        c = cmd[i]
        if c == "'" and not in_double:
            in_single = not in_single
        elif c == '"' and not in_single:
            in_double = not in_double
        elif c == "\\" and not in_single and i + 1 < len(cmd):
            i += 2
            continue
        elif not in_single and not in_double:
            if cmd[i : i + 2] == "$(":
                depth += 1
                i += 2
                continue
            elif c == ")":
                depth -= 1
                if depth == 0:
                    return i
        i += 1
    return None


def split_on_operators(cmd: str) -> list[tuple[str, bool]] | None:
    """Split on &&, ||, ;, | respecting quotes.

    Returns a list of (segment, is_pipe_filter) tuples where is_pipe_filter
    is True for segments that follow a pipe (|) operator.
    Returns None on unclosed quotes.
    """
    parts: list[tuple[str, bool]] = []
    current: list[str] = []
    i = 0
    in_single = False
    in_double = False
    after_pipe = False

    while i < len(cmd):
        c = cmd[i]
        if c == "'" and not in_double:
            in_single = not in_single
            current.append(c)
        elif c == '"' and not in_single:
            in_double = not in_double
            current.append(c)
        elif c == "\\" and not in_single and i + 1 < len(cmd):
            current.append(c)
            current.append(cmd[i + 1])
            i += 2
            continue
        elif not in_single and not in_double:
            if c == "&" and i + 1 < len(cmd) and cmd[i + 1] == "&":
                parts.append(("".join(current), after_pipe))
                current = []
                after_pipe = False
                i += 2
                continue
            elif c == "|" and i + 1 < len(cmd) and cmd[i + 1] == "|":
                parts.append(("".join(current), after_pipe))
                current = []
                after_pipe = False
                i += 2
                continue
            elif c == "|":
                parts.append(("".join(current), after_pipe))
                current = []
                after_pipe = True
                i += 1
                continue
            elif c == ";":
                parts.append(("".join(current), after_pipe))
                current = []
                after_pipe = False
                i += 1
                continue
            else:
                current.append(c)
        else:
            current.append(c)
        i += 1

    if in_single or in_double:
        return None
    parts.append(("".join(current), after_pipe))
    return parts


def get_command_name(part: str) -> str | None:
    """Extract base command name from a simple command, skipping var assignments."""
    part = part.strip()
    if not part:
        return None
    tokens = part.split()
    for token in tokens:
        # Skip VAR=value assignments
        eq = token.find("=")
        if eq > 0 and token[0].isalpha():
            continue
        # Skip shell keywords
        if token in ("!", "{", "}", "then", "else", "fi", "do", "done",
                      "while", "for", "if", "elif", "case", "esac", "in"):
            continue
        # Strip path prefix
        return token.rsplit("/", 1)[-1]
    return None


def extract_all_commands(cmd: str) -> list[tuple[str, bool]] | None:
    """Extract every base command name from a (possibly compound) shell command.

    Returns a list of (name, is_pipe_filter) tuples, or None if the command
    can't be parsed safely.
    """
    result = extract_subshells(cmd)
    if result is None:
        return None

    outer, inners = result
    # (segment_text, is_subshell) — subshell internals are treated as primary
    all_segments: list[tuple[str, bool]] = [(outer, False)] + [
        (s, True) for s in inners
    ]

    # Recursively flatten any nested subshells in inners
    commands: list[tuple[str, bool]] = []
    for segment, is_subshell in all_segments:
        # Check for any remaining subshells (from nested inners)
        if "$(" in segment or "`" in segment:
            nested = extract_subshells(segment)
            if nested is None:
                return None
            seg_outer, seg_inners = nested
            all_segments.extend((s, True) for s in seg_inners)
            segment = seg_outer

        parts = split_on_operators(segment)
        if parts is None:
            return None
        for part, is_filter in parts:
            name = get_command_name(part)
            if name and name != "__sub__":
                # Inside subshells, treat everything as primary (conservative)
                commands.append((name, is_filter and not is_subshell))

    return commands


def emit_allow() -> None:
    json.dump(
        {"hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "allow",
        }},
        sys.stdout,
    )


def emit_deny(reason: str) -> None:
    json.dump(
        {"hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "deny",
            "permissionDecisionReason": reason,
        }},
        sys.stdout,
    )


def main():
    try:
        data = json.load(sys.stdin)
    except (json.JSONDecodeError, EOFError):
        log.debug("PARSE_FAIL: no valid JSON on stdin")
        return

    if data.get("tool_name") != "Bash":
        return

    command = data.get("tool_input", {}).get("command", "")
    log.debug("INPUT command=%r  keys=%s", command, list(data.keys()))
    if not command:
        return

    tagged = extract_all_commands(command)
    log.debug("TAGGED %s", tagged)
    if tagged is None or not tagged:
        log.debug("DECISION defer (parse failure)")
        return

    allowed, denied = load_command_sets()

    # Phase 1: Hard denies from settings.json (security rules)
    for name, is_filter in tagged:
        if name in denied and not (is_filter and name in PIPE_SAFE):
            log.debug("DECISION deny name=%r is_filter=%s", name, is_filter)
            emit_deny(f"'{name}' is in the deny list")
            return

    # Phase 2: Tool-nudge denies — standalone use of commands that have
    # dedicated tools. Allowed as pipe filters, denied otherwise.
    for name, is_filter in tagged:
        if name in TOOL_NUDGE and not is_filter:
            tool = TOOL_NUDGE[name]
            log.debug("DECISION deny (nudge) name=%r tool=%s", name, tool)
            emit_deny(f"Use the {tool} tool instead of '{name}'")
            return

    # Phase 3: Check if all commands are known/allowed
    for name, is_filter in tagged:
        known = (
            name in allowed
            or name in PURE_READONLY
            or name in TOOL_NUDGE  # pipe-filter use (standalone caught above)
            or (is_filter and name in PIPE_SAFE)
        )
        if not known:
            log.debug("DECISION defer (unknown) name=%r is_filter=%s", name, is_filter)
            return

    log.debug("DECISION allow")
    emit_allow()


if __name__ == "__main__":
    main()

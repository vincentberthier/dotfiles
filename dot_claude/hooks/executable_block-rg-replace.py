#!/usr/bin/env python3
"""Claude Code PreToolUse hook: block `rg` misuse of the -r / --replace flag.

In ripgrep, `-r` is --replace (it rewrites matched text in the OUTPUT), NOT a
recursive flag — ripgrep already recurses by default. Typing `rg -rn PATTERN`
silently treats `n` (or the pattern) as a replacement string and mangles every
line of output. There is a standing rule against it (memory: rg-never-dash-r),
and it keeps getting ignored. This hook enforces the rule mechanically.

Behaviour:
- Scans the Bash command (including pipes / && / ; / subshells) for `rg` calls.
- Flags any short-flag bundle containing `r` (e.g. -r, -rn, -nr, -rln) or the
  long `--replace` / `--replace=...` form.
- Blocks with a corrective message telling the agent what to use instead.
- On any parse trouble, defers silently (exit 0) — fail open, never wedge Bash.

This is intentionally strict: it blocks ALL -r/--replace use, not just the
recursive-confusion case. Replacement-in-output is virtually never what's wanted
here; on the rare occasion it is, use the long form spelled out and the agent
can re-run after the user adjusts the rule.
"""

import json
import re
import shlex
import sys

# Shell tokens that end one simple command and start another.
_OPERATORS = {"|", "||", "&&", ";", "&", "|&", "(", ")", "{", "}", "\n"}

# A short-flag bundle (single dash, letters only) that contains `r`.
# Matches -r, -rn, -nr, -rln, -ir, etc. Excludes long flags (--...) and
# anything with non-letter chars (paths, negative numbers, regex like -r{2}).
_SHORT_BUNDLE_WITH_R = re.compile(r"^-[a-zA-Z]*r[a-zA-Z]*$")


def command_uses_rg_replace(command: str) -> bool:
    """Return True if any rg invocation in `command` uses -r / --replace."""
    try:
        lexer = shlex.shlex(command, posix=True, punctuation_chars=True)
        lexer.whitespace_split = True
        tokens = list(lexer)
    except ValueError:
        # Unbalanced quotes etc. — defer to normal permissions.
        return False

    in_rg = False
    after_double_dash = False
    for tok in tokens:
        if tok in _OPERATORS:
            in_rg = False
            after_double_dash = False
            continue
        if not in_rg:
            # A command word is `rg` possibly via a path (e.g. /usr/bin/rg).
            base = tok.rsplit("/", 1)[-1]
            if base == "rg":
                in_rg = True
            continue
        # We are inside an rg invocation's argument list.
        if tok == "--":
            after_double_dash = True
            continue
        if after_double_dash:
            continue
        if tok == "--replace" or tok.startswith("--replace="):
            return True
        if _SHORT_BUNDLE_WITH_R.match(tok):
            return True
    return False


def main() -> int:
    try:
        payload = json.load(sys.stdin)
    except (json.JSONDecodeError, ValueError):
        return 0

    if payload.get("tool_name") != "Bash":
        return 0
    command = payload.get("tool_input", {}).get("command", "")
    if not command or "rg" not in command:
        return 0

    if command_uses_rg_replace(command):
        reason = (
            "Blocked: `rg -r` / `--replace` detected.\n\n"
            "In ripgrep, `-r` is --replace (it REWRITES matched text in the "
            "output) — it is NOT a recursive flag. ripgrep already recurses by "
            "default, so `rg -rn PATTERN` treats your pattern/flags as a "
            "replacement string and mangles the output. This is a standing rule "
            "(rg-never-dash-r) you keep ignoring.\n\n"
            "Fix:\n"
            "  - recursive search is the default: just `rg PATTERN [PATH]`\n"
            "  - line numbers: `rg -n PATTERN`\n"
            "  - files-with-matches: `rg -ln PATTERN`\n"
            "  - if you genuinely want output replacement, spell out `--replace`"
            " AND confirm with the user first."
        )
        print(json.dumps({"decision": "block", "reason": reason}))
        return 0

    return 0


if __name__ == "__main__":
    sys.exit(main())

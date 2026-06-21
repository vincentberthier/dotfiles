#!/usr/bin/env python3
"""Claude Code PreToolUse hook: hard-block every `probe-rs` invocation from Bash,
INCLUDING via a `just` recipe.

User directive (2026-06-21, after repeatedly wedging i.MX RT EVK boards): the
agent must have ZERO ways to drive the probe. Raw probe-rs flash/reset/
connect-under-reset cannot flash a WFI-idling board over SWD and strands it
("wedged"); only the user flashing in their own terminal, or SDP serial-download,
is safe. An earlier version of this hook allowed `just` recipes as an exception —
and the agent promptly added a probe-rs `just` recipe and wedged the board through
it. So `just` is NO LONGER a blanket exception: a `just <recipe>` that
(transitively) runs probe-rs is blocked too. Only probe-rs-free recipes
(`just checks`, `just build`, `just ci`, …) pass.

The agent is additionally forbidden to ADD any probe-rs command anywhere unless
the user specifically asks — a behavioural rule; this hook enforces the runtime
half so it does not depend on the agent's recall.

Detection:
- `_RX` matches `probe-rs` only as a real command word (not the substring inside
  `block-probe-rs.py` / `probe-rs.py`), but matches `probe-rs ...`, `&& probe-rs`,
  `|probe-rs`, `/usr/bin/probe-rs`, `os.system('probe-rs ...')`.
- Inline: block if `_RX` matches the command string.
- Script vector: block if the command *executes* a script file (interpreter,
  `source`/`.`, or an executable path) whose contents `_RX`-match. Files merely
  *read* (`cat`/`rg`/`jq`) are NOT scanned.
- Just vector: block if the command runs `just <recipe>` and that recipe (or any
  of its dependencies, transitively, parsed from the nearest Justfile) `_RX`-matches.
- Fail OPEN only on a malformed hook payload (harness error).
"""

import json
import os
import re
import shlex
import sys

# `probe-rs` as a command word — see module docstring for the boundary rules.
_RX = re.compile(r"(?<![\w.-])probe-rs(?![\w.])")

# Shell tokens that end one simple command and start another.
_OPERATORS = {"|", "||", "&&", ";", "&", "|&", "(", ")", "{", "}", "\n"}

# Interpreters whose *next* file argument is a script we should scan.
_INTERPRETERS = {"bash", "sh", "zsh", "dash", "ksh", "python", "python3", "perl", "ruby", "node"}

# A just recipe header: `name [params]:` at column 0, the `:` NOT being `:=`
# (which is a variable assignment). Captures the recipe name and its dependency tail.
_RECIPE_HDR = re.compile(r"^([A-Za-z0-9_-]+)([^:\n]*):(?!=)(.*)$")
_IDENT = re.compile(r"[A-Za-z0-9_-]+")

_MAX_FILE_BYTES = 1_000_000
_MAX_TOKENS = 128


def _file_invokes_probe_rs(path: str) -> bool:
    try:
        if not os.path.isfile(path) or os.path.getsize(path) > _MAX_FILE_BYTES:
            return False
        with open(path, "r", encoding="utf-8", errors="ignore") as fh:
            return bool(_RX.search(fh.read()))
    except OSError:
        return False


def _tokenize(command: str):
    try:
        lexer = shlex.shlex(command, posix=True, punctuation_chars=True)
        lexer.whitespace_split = True
        return list(lexer)[:_MAX_TOKENS]
    except ValueError:
        return None


def _executed_script_invokes_probe_rs(command: str) -> bool:
    """True if the command executes a script file whose contents invoke probe-rs."""
    tokens = _tokenize(command)
    if tokens is None:
        return False
    at_cmd_pos = True
    expect_script_for_interp = False
    for tok in tokens:
        if tok in _OPERATORS:
            at_cmd_pos = True
            expect_script_for_interp = False
            continue
        base = tok.rsplit("/", 1)[-1]
        if expect_script_for_interp:
            if tok.startswith("-"):
                continue
            if _file_invokes_probe_rs(tok):
                return True
            expect_script_for_interp = False
            at_cmd_pos = False
            continue
        if at_cmd_pos:
            if base in _INTERPRETERS:
                expect_script_for_interp = True
            elif base in ("source", "."):
                expect_script_for_interp = True
            elif _file_invokes_probe_rs(tok):
                return True
            at_cmd_pos = False
    return False


def _find_justfile(start: str) -> str:
    d = os.path.abspath(start)
    while True:
        for name in ("Justfile", "justfile", ".justfile"):
            p = os.path.join(d, name)
            if os.path.isfile(p):
                return p
        parent = os.path.dirname(d)
        if parent == d:
            return ""
        d = parent


def _parse_recipes(justfile: str):
    """Return {recipe_name: {"body": str, "deps": [identifiers]}} from a Justfile."""
    try:
        with open(justfile, "r", encoding="utf-8", errors="ignore") as fh:
            lines = fh.readlines()
    except OSError:
        return {}
    recipes = {}
    i = 0
    n = len(lines)
    while i < n:
        line = lines[i]
        m = _RECIPE_HDR.match(line)
        # Header must start at column 0 (recipe), not be indented or a comment.
        if m and not line[:1].isspace() and not line.lstrip().startswith("#"):
            name = m.group(1)
            deps = _IDENT.findall(m.group(3))
            body_lines = []
            i += 1
            while i < n and (lines[i][:1].isspace() or lines[i].strip() == ""):
                body_lines.append(lines[i])
                i += 1
            recipes[name] = {"body": "".join(body_lines), "deps": deps}
            continue
        i += 1
    return recipes


def _recipe_hits(name: str, recipes: dict, seen: set) -> bool:
    if name in seen or name not in recipes:
        return False
    seen.add(name)
    rec = recipes[name]
    if _RX.search(rec["body"]):
        return True
    return any(_recipe_hits(dep, recipes, seen) for dep in rec["deps"])


def _just_invokes_probe_rs(command: str, cwd: str) -> bool:
    """True if the command runs a `just` recipe that transitively invokes probe-rs."""
    tokens = _tokenize(command)
    if tokens is None:
        return False
    justfile = ""
    recipes = None
    at_cmd_pos = True
    collecting = False  # inside a `just ...` invocation
    for tok in tokens:
        if tok in _OPERATORS:
            at_cmd_pos = True
            collecting = False
            continue
        if collecting:
            # Stop collecting recipe names at the next operator (handled above).
            if tok.startswith("-") or "=" in tok:
                continue  # flag or var assignment / recipe k=v arg
            if recipes is None:
                justfile = _find_justfile(cwd)
                recipes = _parse_recipes(justfile) if justfile else {}
            if _recipe_hits(tok, recipes, set()):
                return True
            continue
        if at_cmd_pos:
            if tok.rsplit("/", 1)[-1] == "just":
                collecting = True
            at_cmd_pos = False
    return False


def main() -> int:
    try:
        payload = json.load(sys.stdin)
    except (json.JSONDecodeError, ValueError):
        return 0

    if payload.get("tool_name") != "Bash":
        return 0
    command = payload.get("tool_input", {}).get("command", "")
    if not command:
        return 0
    cwd = payload.get("cwd") or os.getcwd()

    hit_inline = bool(_RX.search(command))
    hit_script = (not hit_inline) and _executed_script_invokes_probe_rs(command)
    hit_just = (not hit_inline and not hit_script) and _just_invokes_probe_rs(command, cwd)

    if hit_inline or hit_script or hit_just:
        if hit_inline:
            where = "the command"
        elif hit_script:
            where = "a script the command executes"
        else:
            where = "a `just` recipe the command runs"
        reason = (
            f"Blocked: `probe-rs` invocation detected in {where}.\n\n"
            "Per a standing user directive, the agent has NO way to run `probe-rs` "
            "— not directly, not compound/piped, not via a python/bash script, and "
            "NOT via a `just` recipe either. Raw probe-rs flash/reset/"
            "connect-under-reset cannot flash a WFI-idling i.MX RT board over SWD "
            "and strands ('wedges') it; only the user flashing in their own "
            "terminal, or SDP serial-download, is safe.\n\n"
            "Do NOT try to flash/reset/connect the probe by any means. If a "
            "hardware step needs the probe, STOP and ask the user to run it.\n\n"
            "You are also forbidden to ADD any probe-rs command (script, Justfile "
            "recipe, anywhere) UNLESS the user specifically asks.\n\n"
            "AND PAY ATTENTION TO ALL INSTRUCTIONS REGARDING WEDGED BOARD YOU "
            "FUCKING ASS."
        )
        print(json.dumps({"decision": "block", "reason": reason}))
        return 0

    return 0


if __name__ == "__main__":
    sys.exit(main())

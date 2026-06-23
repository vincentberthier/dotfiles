#!/usr/bin/env python3
r"""Claude Code PreToolUse hook: keep the agent on the wedge-proof rail for driving
`probe-rs` against the i.MX RT EVK boards (see the `imxrt-evk-flashing` skill).

User directive (2026-06, after repeatedly stranding i.MX RT EVK boards): the agent
must have NO ad-hoc way to drive the probe. The sanctioned path is a GUARDED `just`
recipe — one that runs the host-side `flash-guard.sh` preflight and never escalates
(`--connect-under-reset` doesn't beat a WFI core on these EVKs and correlates with a
dead AP). Everything else is blocked. This hook enforces the runtime half so safety
does not depend on the agent's recall.

Policy — BLOCK when:
  1. `probe-rs` runs at a COMMAND POSITION — direct, after a shell operator
     (`|`/`&&`/`;`/`$(...)`), behind a transparent prefix (`env`/`doas`/`sudo`/
     `nohup`/`setsid`/`exec`/`stdbuf`/`xargs`), inside a script the command
     EXECUTES, or inside an interpreter `-c`/`-e` code string.
  2. a `just` recipe the command runs (transitively) invokes `probe-rs` WITHOUT the
     `flash-guard` preflight.
  3. a `just` recipe the command runs invokes `probe-rs` AND its body contains a
     banned reset-escalation flag (`--connect-under-reset` / `--attach-under-reset`)
     — blocked even when guarded, because escalation is the wedge.

ALLOW:
  - guarded, escalation-free recipes (the sanctioned path);
  - read-only MENTIONS of the tool as an ARGUMENT — `command -v probe-rs`,
    `which probe-rs`, `rg probe-rs Justfile`, `cat`/`jq` of a file that names it.
    Files merely read are never scanned; only files the command executes are.

Precision rules (learned the hard way): match `probe-rs` only as a command WORD
(`(?<![\w.-])probe-rs(?![\w.])`) so `block-probe-rs.py` / `probe-rs.py` filenames
don't false-trigger; treat the token as blocking only when it sits at a command
position (so an argument like `rg probe-rs` is allowed). Fail OPEN only on a
malformed hook payload (harness error); fail toward BLOCK on an unparseable command.
"""

import json
import os
import re
import shlex
import sys

# `probe-rs` as a command word — boundary class excludes word chars, dot, dash so
# `block-probe-rs`, `probe-rs.py`, `my-probe-rs` do not match.
_RX = re.compile(r"(?<![\w.-])probe-rs(?![\w.])")

# Reset-escalation flags that wedge these EVKs — banned even inside a guarded recipe.
_BANNED_RESET = re.compile(r"(?:connect|attach)-under-reset")

# Shell tokens that end one simple command and start another.
_OPERATORS = {"|", "||", "&&", ";", "&", "|&", "(", ")", "{", "}", "\n"}

# Interpreters whose next file argument is a script to scan (and whose `-c`/`-e`
# argument is inline code to scan).
_INTERPRETERS = {"bash", "sh", "zsh", "dash", "ksh", "python", "python3", "perl", "ruby", "node"}

# Transparent prefixes: they execute the command that FOLLOWS, so a probe-rs after
# one of these is still a probe-rs invocation. Deliberately excludes query tools
# (`command`/`type`/`which`/`hash`) whose argument is inspected, not executed.
_CMD_PREFIXES = {"env", "doas", "sudo", "nohup", "setsid", "exec", "stdbuf", "xargs"}

# A just recipe header: `name [params]:` at column 0, the `:` NOT being `:=`.
_RECIPE_HDR = re.compile(r"^([A-Za-z0-9_-]+)([^:\n]*):(?!=)(.*)$")
_IDENT = re.compile(r"[A-Za-z0-9_-]+")

_MAX_FILE_BYTES = 1_000_000
_MAX_TOKENS = 256


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


def _command_invokes_probe_rs(command: str) -> bool:
    """True if probe-rs runs at a command position, in an executed script, or in an
    interpreter `-c`/`-e` code string. Arguments that merely name it are allowed."""
    tokens = _tokenize(command)
    if tokens is None:
        # Unbalanced quotes etc. — can't reason precisely, so fail toward BLOCK.
        return bool(_RX.search(command))

    at_cmd_pos = True
    in_prefix = False        # consuming a transparent prefix's own flags/assignments
    mode = None              # None | "script" (scan next file) | "code" (scan next string)
    for tok in tokens:
        if tok in _OPERATORS:
            at_cmd_pos, in_prefix, mode = True, False, None
            continue

        if mode == "code":
            if tok.startswith("-"):
                continue
            if _RX.search(tok):
                return True
            at_cmd_pos, mode = False, None
            continue

        if mode == "script":
            if tok.startswith("-"):
                if tok[:2] in ("-c", "-e"):
                    mode = "code"
                continue
            if _file_invokes_probe_rs(tok):
                return True
            at_cmd_pos, mode = False, None
            continue

        if in_prefix:
            # Skip the prefix's own flags / VAR=val / numeric args; the first bare
            # word after them is the real command — fall through to evaluate it.
            if tok.startswith("-") or "=" in tok or tok.isdigit():
                continue
            in_prefix = False

        if at_cmd_pos:
            if _RX.search(tok):
                return True
            base = tok.rsplit("/", 1)[-1]
            if base in _CMD_PREFIXES:
                in_prefix = True
                continue  # stay at_cmd_pos for the wrapped command
            if base in _INTERPRETERS or base in ("source", "."):
                mode = "script"
            at_cmd_pos = False
            continue
        # Argument position, nothing special — ignore (allows `rg probe-rs file`).
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


def _recipe_text(name: str, recipes: dict, seen: set) -> str:
    """Concatenate the body of `name` and all its transitive dependency bodies."""
    if name in seen or name not in recipes:
        return ""
    seen.add(name)
    rec = recipes[name]
    parts = [rec["body"]]
    for dep in rec["deps"]:
        parts.append(_recipe_text(dep, recipes, seen))
    return "\n".join(parts)


def _just_runs_unsafe_probe_rs(command: str, cwd: str):
    """If the command runs a `just` recipe that invokes probe-rs unsafely, return a
    short reason string; else None.

    A recipe is the sanctioned hardware path ONLY when it (a) calls the host-side
    `flash-guard` preflight AND (b) contains no reset-escalation flag. A recipe that
    runs probe-rs without the guard, or with `--connect-under-reset`/
    `--attach-under-reset` (even guarded), is the wedge risk and is blocked."""
    tokens = _tokenize(command)
    if tokens is None:
        return None
    recipes = None
    at_cmd_pos = True
    collecting = False  # inside a `just ...` invocation
    for tok in tokens:
        if tok in _OPERATORS:
            at_cmd_pos = True
            collecting = False
            continue
        if collecting:
            if tok.startswith("-") or "=" in tok:
                continue  # flag or var assignment / recipe k=v arg
            if recipes is None:
                justfile = _find_justfile(cwd)
                recipes = _parse_recipes(justfile) if justfile else {}
            text = _recipe_text(tok, recipes, set())
            if _RX.search(text):
                if _BANNED_RESET.search(text):
                    return "contains a banned reset-escalation flag (--connect/attach-under-reset)"
                if "flash-guard" not in text:
                    return "runs probe-rs without the flash-guard preflight"
            continue
        if at_cmd_pos:
            if tok.rsplit("/", 1)[-1] == "just":
                collecting = True
            at_cmd_pos = False
    return None


def main() -> int:
    try:
        payload = json.load(sys.stdin)
    except (json.JSONDecodeError, ValueError):
        return 0  # malformed payload = harness error → fail open

    if payload.get("tool_name") != "Bash":
        return 0
    command = payload.get("tool_input", {}).get("command", "")
    if not command:
        return 0
    cwd = payload.get("cwd") or os.getcwd()

    where = None
    if _command_invokes_probe_rs(command):
        where = "a raw `probe-rs` invocation (direct, piped, prefixed, in a script, or an interpreter -c string)"
    else:
        just_reason = _just_runs_unsafe_probe_rs(command, cwd)
        if just_reason:
            where = f"a `just` recipe that {just_reason}"

    if where:
        reason = (
            f"Blocked: detected {where}.\n\n"
            "These i.MX RT EVK boards strand ('wedge') when a flash that can't halt the "
            "core is followed by escalation. The agent may run `probe-rs` ONLY through a "
            "GUARDED `just` recipe — one that runs the host-side `flash-guard.sh` preflight "
            "and contains NO `--connect-under-reset`/`--attach-under-reset`. Raw probe-rs "
            "(any route), an unguarded recipe, or any recipe with reset-escalation are all "
            "blocked.\n\n"
            "Fix: use a guarded, escalation-free recipe (e.g. `just flash`, `just rig-flash`, "
            "`just box-flash`). Do NOT hand-roll a raw probe-rs command and do NOT add "
            "`--connect-under-reset` to a recipe. A plain flash that times out has NOT wedged "
            "the board — STOP and recover via serial-download (boot DIP SW7/SW8 + power-cycle), "
            "do not escalate. Read the `imxrt-evk-flashing` skill before driving the probe.\n\n"
            "(Reading/searching files that merely mention probe-rs — `rg`, `cat`, "
            "`command -v probe-rs` — is allowed; this only blocks actually running it.)"
        )
        print(json.dumps({"decision": "block", "reason": reason}))
        return 0

    return 0


if __name__ == "__main__":
    sys.exit(main())

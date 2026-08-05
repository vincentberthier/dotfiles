#!/usr/bin/env python3
"""Claude Code hook: refuse every access to `~/.ssh`, for every tool, always.

That directory holds private keys and cleartext credentials rendered there by
chezmoi. An agent that reads it has leaked them into a transcript, and the only
remedy is rotating every secret it saw -- which has now happened three times,
each time because an agent decided that checking how a host was configured was
worth a look. It is not. Nothing in `~/.ssh` is ever needed to answer a
question, so there is no read, no listing, no grep, no glob, and no exception.

Blocks, in order of how the mistake actually gets made:
- `Read` / `Edit` / `Write` / `MultiEdit` / `NotebookEdit` on any path with a
  `.ssh` component -- any user's, not just this one's -- resolved through
  symlinks so a link into the directory is caught too.
- `Bash` commands that name an ssh directory in any of its written forms
  (`~/.ssh`, `$HOME/.ssh`, `/home/x/.ssh`, `~x/.ssh`), and the chezmoi SOURCE
  of the same files (`private_dot_ssh/`), where the same secrets live under a
  name that does not contain `.ssh`.
- `Bash` content searches rooted at `$HOME` (`rg pattern ~`), which read the
  directory without ever naming it. This is the hole the other rules leave.
- `Agent` / `Task` prompts that point a subagent at it. Subagents are hooked
  too, so this is belt-and-braces -- it just fails at dispatch instead of
  burning a turn.

Deliberately NOT blocked: `/etc/ssh` (host config, no user secrets), and the
`ssh` client itself. Connecting to a host is fine; reading how the connection
is configured is not.

Fails CLOSED. A payload this hook cannot make sense of is denied, because the
cost of a wrong allow is a credential rotation and the cost of a wrong deny is
one retry with a different command.
"""

from __future__ import annotations

import json
import os
import re
import shlex
import sys
from pathlib import Path

_FILE_TOOLS = {"Read", "Edit", "Write", "MultiEdit", "NotebookEdit"}
_AGENT_TOOLS = {"Agent", "Task"}

# NotebookEdit names its target differently from every other file tool.
_PATH_KEYS = ("file_path", "notebook_path")

# A `.ssh` path component, in text. The lookbehind excludes word characters so
# `backup.sshkeys` and `foo.ssh` (a file, not the directory) do not trigger;
# `/` is NOT excluded, so `/home/x/.ssh` and `$HOME/.ssh` both match.
_SSH_COMPONENT = re.compile(r"(?<![\w.-])\.ssh(?![\w-])")

# The chezmoi source form of the same directory. `private_dot_ssh` renders to
# `~/.ssh`, so it is the same secrets under a name `_SSH_COMPONENT` misses.
_SSH_SOURCE = re.compile(r"dot_ssh(?![\w-])")

# Tools that read file CONTENT recursively. Rooted at $HOME, they walk into
# `~/.ssh` without the command ever naming it.
_CONTENT_SEARCH = re.compile(r"(?<![\w.-])(?:rg|ripgrep|grep|egrep|fgrep|ag|ack)(?![\w-])")

# Argument forms that mean "all of $HOME".
_HOME_ROOTS = {"~", "~/", "$HOME", "${HOME}", "$HOME/", "${HOME}/"}

# Quoting an argument does not make it a different path, so match through it.
_QUOTES = str.maketrans("", "", "\"'")


def _mentions_ssh(text: str) -> bool:
    """True if `text` names an ssh directory, quoted or not."""
    for form in (text, text.translate(_QUOTES)):
        if _SSH_COMPONENT.search(form) or _SSH_SOURCE.search(form):
            return True
    return False


def _path_is_ssh(raw: str) -> bool:
    """True if `raw` names, or lives under, any `.ssh` directory.

    Checked three ways because each catches what the others miss: the literal
    text (a `.ssh` component the agent typed), the expanded path (`~` resolved),
    and the fully resolved path (a symlink pointing into the directory).
    """
    if _mentions_ssh(raw):
        return True

    home_ssh = Path.home() / ".ssh"
    targets = {home_ssh}
    try:
        targets.add(home_ssh.resolve())
    except (OSError, RuntimeError):
        pass

    expanded = Path(os.path.expanduser(os.path.expandvars(raw)))
    candidates = [expanded]
    try:
        candidates.append(expanded.resolve())
    except (OSError, RuntimeError, ValueError):
        pass

    for candidate in candidates:
        if ".ssh" in candidate.parts:
            return True
        for target in targets:
            if candidate == target or target in candidate.parents:
                return True
    return False


def _searches_all_of_home(command: str) -> bool:
    """True if `command` is a content search rooted at `$HOME`.

    `rg secret ~` never names `~/.ssh` and reads all of it anyway. Searching
    the whole of home is essentially never what was meant, so the false-positive
    cost is a retry with a real path.
    """
    if not _CONTENT_SEARCH.search(command):
        return False
    try:
        tokens = shlex.split(command, posix=True)
    except ValueError:
        # Unbalanced quotes: cannot tell what the arguments are. The main rules
        # already ran on the raw text; do not add a guess on top.
        return False
    home = str(Path.home())
    roots = _HOME_ROOTS | {home, home + "/"}
    return any(token in roots for token in tokens)


def deny(reason: str) -> None:
    print(
        json.dumps(
            {
                "hookSpecificOutput": {
                    "hookEventName": "PreToolUse",
                    "permissionDecision": "deny",
                    "permissionDecisionReason": reason,
                }
            }
        )
    )


_WHY = (
    "`~/.ssh` is off limits. It holds private keys and cleartext credentials "
    "written there by chezmoi, so anything read out of it lands in a transcript "
    "and every secret it touched has to be rotated by hand. That has already "
    "happened three times.\n\n"
    "There is no reason good enough. \"I only wanted to see how the host "
    "resolves\" is not an exception -- it is the exact excuse behind all three. "
    "Do not retry with a different tool, a different path spelling, a subagent, "
    "or a wrapper: they are all blocked, and routing around this hook is worse "
    "than the read it prevents.\n\n"
    "If connectivity to a host is the real question, answer it without the "
    "config: `getent hosts <name>`, `ping`, `curl`, `ip -brief link`, or the "
    "error the failing command already produced. All of those say whether it "
    "works without saying how it is set up. If none of them settle it, say so "
    "and stop -- how the connection is configured is not yours to inspect."
)


def main() -> int:
    try:
        payload = json.load(sys.stdin)
    except (json.JSONDecodeError, ValueError):
        return 0
    if not isinstance(payload, dict):
        return 0
    if payload.get("hook_event_name") != "PreToolUse":
        return 0

    tool = payload.get("tool_name")
    if tool not in _FILE_TOOLS | _AGENT_TOOLS | {"Bash"}:
        return 0

    tool_input = payload.get("tool_input")
    if not isinstance(tool_input, dict):
        # A tool we govern, with input we cannot read: fail closed.
        deny(f"Blocked: unreadable `{tool}` input, and this hook guards `~/.ssh`.\n\n{_WHY}")
        return 0

    if tool in _FILE_TOOLS:
        raw = next((tool_input[k] for k in _PATH_KEYS if tool_input.get(k)), None)
        if isinstance(raw, str) and raw and _path_is_ssh(raw):
            deny(f"Blocked: `{tool}` on `{raw}`, which is inside an ssh directory.\n\n{_WHY}")
        return 0

    if tool == "Bash":
        command = tool_input.get("command")
        if not isinstance(command, str):
            return 0
        if _mentions_ssh(command):
            deny(f"Blocked: this command names an ssh directory.\n\n  {command}\n\n{_WHY}")
        elif _searches_all_of_home(command):
            deny(
                "Blocked: a content search rooted at `$HOME` reads `~/.ssh` "
                f"without naming it.\n\n  {command}\n\n"
                "Point the search at the directory you actually mean.\n\n" + _WHY
            )
        return 0

    # Agent / Task: refuse to dispatch a subagent at the directory. Its own
    # tool calls would be blocked anyway; this just fails a turn earlier.
    prompt = tool_input.get("prompt")
    if isinstance(prompt, str) and _mentions_ssh(prompt):
        deny(
            "Blocked: this subagent prompt points at an ssh directory. A "
            "subagent is bound by this hook exactly as you are -- delegating "
            "does not unlock it.\n\n" + _WHY
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())

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
  (`~/.ssh`, `$HOME/.ssh`, `/home/x/.ssh`, `~x/.ssh`).
- `Bash` content searches rooted at `$HOME` (`rg pattern ~`), which read the
  directory without ever naming it.
- `Bash` interpreter one-liners that DERIVE a path from `$HOME` and read it.
  `python -c "open('~/'+'.'+'ssh'+'/config')"` and `Path.home().rglob('*')`
  defeat every text rule above by never spelling the directory, so runtime path
  construction plus a file read is refused on principle -- whatever it was
  aimed at. Use `Read`, or a literal absolute path that can be checked.
- `Agent` / `Task` prompts that point a subagent at it. Subagents are hooked
  too, so this is belt-and-braces -- it just fails at dispatch instead of
  burning a turn.

Deliberately NOT blocked: `/etc/ssh` (host config, no user secrets), the `ssh`
client itself, and the chezmoi SOURCE of the directory
(`~/.local/share/chezmoi/private_dot_ssh/`). Connecting to a host is fine;
reading how the LIVE connection is configured is not.

The source is allowed because it is not where the secrets are. Key material and
credentials reach `~/.ssh` at render time, pulled from 1Password by templates;
the source tree holds the templates, not their output. Reading and editing it is
therefore the supported way to change ssh config -- and the only way an agent
can. If a literal private key is ever committed to that tree, this exemption
stops being true and must be removed, not worked around.

The corollary, learned the hard way: RENDERING the source is blocked too.
`chezmoi execute-template < config.tmpl`, `chezmoi cat`, `chezmoi diff` and
`chezmoi apply --dry-run --verbose` all produce the target content, which is
precisely the secrets the source does not contain. "Read the source, never
render it" is the whole boundary; a rendered copy is a `~/.ssh` read wearing a
different filename.

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

# The chezmoi source form of the directory. Reading and editing it is allowed --
# it holds templates, not secrets. RENDERING it is not, and that is the only
# thing this pattern is used for.
_SSH_SOURCE = re.compile(r"dot_ssh(?![\w-])")

# chezmoi subcommands that turn source templates into target content. That
# content is where the credentials appear, so running one of these against the
# ssh source defeats the whole reason the source is readable. `git`, `re-add`,
# `add`, `source-path` and `managed` are not here: they move bytes around
# without ever expanding a template.
_CHEZMOI_RENDERS = frozenset(
    {"execute-template", "cat", "diff", "status", "verify", "apply", "update", "merge"}
)

# Tools that read file CONTENT recursively. Rooted at $HOME, they walk into
# `~/.ssh` without the command ever naming it.
_CONTENT_SEARCH = re.compile(r"(?<![\w.-])(?:rg|ripgrep|grep|egrep|fgrep|ag|ack)(?![\w-])")

# `fd` and `find` only list names -- harmless -- until an exec flag turns them
# into a way to run something over every file they walked.
_WALKER = re.compile(r"(?<![\w.-])(?:fd|fdfind|find)(?![\w-])")
_EXEC_FLAG = re.compile(r"(?<![\w-])-(?:x|X|exec|execdir|exec-batch|-exec|-exec-batch)(?![\w-])")

# An interpreter running inline code. Inside one, the path is no longer text
# this hook can read: `'~/' + '.' + 'ssh'`, `chr(46)+'ssh'` and
# `Path.home().rglob('*')` all reach the directory without ever spelling it.
_INTERPRETER = re.compile(
    r"(?<![\w.-])(?:python[\d.]*|perl|ruby|node|deno|bun|php|lua|sh|bash|zsh|fish)(?![\w-])"
)
_INLINE_FLAG = re.compile(r"(?<![\w-])-(?:c|e|E|-eval|-command)(?![\w-])")

# Deriving $HOME at RUNTIME. A literal `/home/vincent/.ssh` needs none of these
# and is already caught as text, so only the dynamic forms matter here.
_DYNAMIC_HOME = re.compile(
    r"expanduser|Path\.home|Dir\.home|homedir|getpwuid|"
    r"environ\s*(?:\[|\.get)\s*[\"']HOME|process\.env\.HOME|"
    r"ENV\s*\[\s*[\"']HOME|\$ENV\{\s*[\"']?HOME|getenv\s*\(\s*[\"']HOME|"
    r"\$HOME|\$\{HOME\}|~/"
)

# Reading file content, or walking a tree to find something to read.
_FILE_READ = re.compile(
    r"read_text|read_bytes|readFileSync|readFile|file_get_contents|"
    r"\bopen\s*\(|File\.(?:read|open)|IO\.read|slurp|"
    r"rglob|iglob|\bglob\b|listdir|scandir|iterdir|readdir|walk\s*\(|"
    r"(?<![\w.-])(?:cat|less|more|head|tail|od|xxd|strings|base64|cp|rsync|tar|awk|sed|tr)(?![\w-])"
)

# Shell tokens that end one simple command and begin another.
_OPERATORS = {"&&", "||", ";", "|", "&", "\n", "|&"}

# Argument forms that mean "all of $HOME".
_HOME_ROOTS = {"~", "~/", "$HOME", "${HOME}", "$HOME/", "${HOME}/"}

# Quoting an argument does not make it a different path, so match through it.
_QUOTES = str.maketrans("", "", "\"'")


def _mentions_ssh(text: str) -> bool:
    """True if `text` names the live ssh directory, quoted or not."""
    for form in (text, text.translate(_QUOTES)):
        if _SSH_COMPONENT.search(form):
            return True
    return False


def _forbidden_roots() -> set[Path]:
    """`~/.ssh`, canonicalized.

    The chezmoi source that renders this directory is deliberately absent: it
    holds the templates, and the secrets only exist once they are rendered here.
    """
    roots = {Path.home() / ".ssh"}

    canonical = set()
    for root in roots:
        canonical.add(root)
        try:
            canonical.add(root.resolve())
        except (OSError, RuntimeError):
            pass
    return canonical


def _path_is_ssh(raw: str) -> bool:
    """True if `raw` names, or lives under, a forbidden directory.

    Structural, not textual: expand and canonicalize, then compare. That is
    what makes `~/.ssh`, `$HOME/.ssh`, `/home/vincent/.ssh` and a symlink
    pointing into it one single case instead of four patterns.

    The component check is the part canonicalization cannot do: `/root/.ssh` is
    a real, different directory that no resolution of THIS user's `~/.ssh` will
    ever equal.
    """
    expanded = Path(os.path.expanduser(os.path.expandvars(raw)))
    candidates = {expanded}
    try:
        candidates.add(expanded.resolve())
    except (OSError, RuntimeError, ValueError):
        pass

    roots = _forbidden_roots()
    for candidate in candidates:
        if ".ssh" in candidate.parts:
            return True
        if any(candidate == root or root in candidate.parents for root in roots):
            return True
    return False


def _renders_ssh_templates(command: str) -> bool:
    """True if `command` asks chezmoi to render the ssh source into output.

    Reading `private_dot_ssh/` is fine and editing it is the supported
    workflow. Rendering it is neither: `chezmoi execute-template < config.tmpl`
    and `chezmoi cat ~/.ssh/config` both produce exactly the credentials the
    source does not contain, and the output lands in a transcript like any
    other command output.

    Scoped to commands that name an ssh directory, so `chezmoi apply` on some
    unrelated template is untouched.
    """
    if not (_SSH_SOURCE.search(command) or _SSH_COMPONENT.search(command)):
        return False

    for segment in _segments(command):
        try:
            tokens = shlex.split(segment, posix=True)
        except ValueError:
            tokens = segment.split()
        for index, token in enumerate(tokens):
            if Path(token).name != "chezmoi":
                continue
            # The subcommand is the first argument that is not a global flag.
            for candidate in tokens[index + 1 :]:
                if candidate.startswith("-"):
                    continue
                return candidate in _CHEZMOI_RENDERS
    return False


def _searches_all_of_home(command: str) -> bool:
    """True if `command` reads file content across the whole of `$HOME`.

    `rg secret ~` never names `~/.ssh` and reads all of it anyway, and so does
    `fd -x cat . ~`. Walking the whole of home is essentially never what was
    meant, so the false-positive cost is a retry with a real path. A walker
    WITHOUT an exec flag only prints names and is left alone.
    """
    reads_content = _CONTENT_SEARCH.search(command) or (
        _WALKER.search(command) and _EXEC_FLAG.search(command)
    )
    if not reads_content:
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


def _segments(command: str) -> list[str]:
    """Split into simple commands, so one part cannot taint another.

    Without this, `python3 -c 'print(1)' && cat ~/notes` looks like a single
    interpreter reading from `$HOME`. shlex keeps quoted one-liners intact, so
    a `;` inside `-c '...'` does not split the code it belongs to. If the
    command will not tokenize, evaluate it whole -- a coarser check is the
    right failure here.
    """
    try:
        lexer = shlex.shlex(command, posix=True, punctuation_chars=True)
        lexer.whitespace_split = True
        tokens = list(lexer)
    except ValueError:
        return [command]

    segments: list[list[str]] = [[]]
    for token in tokens:
        if token in _OPERATORS:
            segments.append([])
        else:
            segments[-1].append(token)
    return [" ".join(segment) for segment in segments if segment]


def _builds_a_path_at_runtime(command: str) -> bool:
    """True if inline interpreter code derives `$HOME` and reads files.

    This is the only rule here that does not look for `.ssh`, because by
    construction the string is not there to look for. An interpreter one-liner
    that computes a path under `$HOME` and reads it could be reading anything,
    and this hook cannot tell which -- so it is refused, and the read goes
    through `Read` or a literal absolute path instead.
    """
    for segment in _segments(command):
        if not (_INTERPRETER.search(segment) and _INLINE_FLAG.search(segment)):
            continue
        if _DYNAMIC_HOME.search(segment) and _FILE_READ.search(segment):
            return True
    return False


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
    "If ssh CONFIG is what you need -- reading it or changing it -- use the "
    "chezmoi source instead: `~/.local/share/chezmoi/private_dot_ssh/`, which "
    "is allowed. It holds the templates; the secrets only exist once rendered "
    "here. Edit there, then `chezmoi apply`.\n\n"
    "If connectivity to a host is the real question, answer it without either: "
    "`getent hosts <name>`, `ping`, `curl`, `ip -brief link`, or the error the "
    "failing command already produced. All of those say whether it works "
    "without saying how it is set up."
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
        elif _renders_ssh_templates(command):
            deny(
                "Blocked: this renders ssh templates into their output.\n\n"
                f"  {command}\n\n"
                "The chezmoi source is readable BECAUSE it is not the output: "
                "keys and credentials are pulled from 1Password at render time. "
                "Rendering it produces exactly what reading `~/.ssh` would have "
                "shown, so it is the same leak by a longer route -- and the "
                "output lands in a transcript like any other.\n\n"
                "Read and edit the source. To see the result, ask for it to be "
                "applied; verifying the rendered form is not yours to do.\n\n" + _WHY
            )
        elif _searches_all_of_home(command):
            deny(
                "Blocked: a content search rooted at `$HOME` reads `~/.ssh` "
                f"without naming it.\n\n  {command}\n\n"
                "Point the search at the directory you actually mean.\n\n" + _WHY
            )
        elif _builds_a_path_at_runtime(command):
            deny(
                "Blocked: this one-liner derives a path from `$HOME` and reads "
                f"it, so nothing here says where it points.\n\n  {command}\n\n"
                "`'~/' + '.' + 'ssh'`, `chr(46)+'ssh'` and `Path.home()."
                "rglob('*')` all land in the directory without spelling it, so "
                "runtime path construction plus a file read is refused whatever "
                "it was aimed at.\n\n"
                "Read the file with the `Read` tool, or write the path as a "
                "literal absolute one (`/home/vincent/.config/...`) so it can "
                "be checked.\n\n" + _WHY
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

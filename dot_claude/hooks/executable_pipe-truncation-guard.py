#!/usr/bin/env python3
"""Claude Code PreToolUse hook: block piping a build/test/CI run into a filter.

The recurring failure, in one command:

    TMPDIR=/var/tmp CI_VARIANT=rust just ci 2>&1 | tail -50

Two bugs, and they hide each other:

1. The exit status belongs to `tail`, not to `just`. `tail` succeeds at printing
   nothing, so a failed build reports success and the agent calls the task done.
   `| rg error` is worse still — it exits 1 when the build was CLEAN.
2. Everything above the last fifty lines is gone. Not scrolled past, not
   collapsed — never written anywhere. The first error is usually up there, and
   when the summary turns out to be wrong there is nothing to go back to.

Keeping noise out of the session is right; making it unrecoverable is not. The
fix costs one redirect:

    LOG=/var/tmp/ci-$(date +%Y%m%d-%H%M%S).log
    just ci >"$LOG" 2>&1; echo "exit=$? log=$LOG"

Caught: a pipeline whose SOURCE is a build/test/CI runner and whose last stage
truncates or filters, unless the full output is preserved (a `tee` to a file, or
a redirect on the source stage) AND the real status is recovered (`pipefail` or
`PIPESTATUS`).

Deliberately narrow. `rg foo | head`, `git log | tail`, `cargo tree | rg serde`
and every other query pipeline stay untouched — this fires only where the full
output is the point of running the command.

Fails open (exit 0, no output) on anything it cannot parse: a guard that wedges
Bash is worse than the bug it guards against.
"""

from __future__ import annotations

import json
import re
import shlex
import sys

# Shell tokens that end one simple command and start another.
_OPERATORS = {"|", "||", "&&", ";", "&", "|&", "(", ")", "{", "}", "\n"}

# Operators that pipe stdout of the previous command into the next one.
_PIPES = {"|", "|&"}

# Commands whose full output is the reason you ran them: builds, test runs,
# linters, CI replays. Anything not in here is none of this hook's business.
_JOB_COMMANDS = {
    "just", "cargo", "make", "ninja", "cmake", "meson", "ctest", "bacon",
    "gradle", "mvn", "npm", "pnpm", "yarn", "bun", "go", "pytest", "tox",
    "nox", "uv", "swift", "dotnet", "typst", "nix",
}

# Container CLIs are mostly query tools; only their build/run verbs qualify.
_SUBCOMMAND_ONLY = {
    "docker": {"build", "buildx", "compose"},
    "podman": {"build", "buildx", "compose"},
}

# Read-only verbs that print a list and exit — piping those into a filter is
# exactly what they are for.
_QUERY_SUBCOMMANDS = {
    "help", "version", "list", "ls", "info", "view", "why", "outdated",
    "config", "env", "doc", "tree", "metadata", "pkgid", "locate-project",
    "search", "read-manifest", "describe", "check-config", "summary",
}

# Same, in flag costume: `just --list`, `cargo --version`.
_QUERY_FLAGS = {
    "--help", "-h", "--version", "-V", "--list", "--summary", "--evaluate",
    "--dump", "--show", "--variables", "--choose", "--groups", "--dry-run",
    "--just-print", "--question", "--print-data-base",
}

# Short flags are only query flags for the tool that spells them that way: `-q`
# is make's --question but pytest's --quiet, `-l` is just's --list but a long
# listing everywhere else. Global exemptions here would wave real runs through.
_QUERY_SHORT_FLAGS = {
    "just": {"-l", "-s"},
    "make": {"-n", "-q", "-p"},
    "ninja": {"-n", "-t"},
    "cmake": {"-N"},
}

# Stages that truncate the stream or drop most of it on the floor.
_SINKS = {
    "tail", "head", "less", "more", "most", "wc", "fzf", "cut", "sed", "awk",
    "jq", "yq", "rg", "grep", "egrep", "fgrep", "ag", "ack",
}

# Words that can sit in front of the real command word.
_PREFIXES = {
    "!", "until", "while", "if", "elif", "then", "do", "else", "time",
    "command", "builtin", "exec", "nohup", "setsid", "doas", "sudo", "env",
}
_ASSIGNMENT = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*=")

# `>` and `>>` open a file; `>&` duplicates a descriptor (`2>&1`), which sinks
# nothing to disk. shlex keeps `>&` as one token, so they never collide — and it
# splits `2>err.log` into `2`, `>`, `err.log`, so a bare `>` covers that too.
_FILE_REDIRECTS = {">", ">>", "&>", "&>>"}

REASON = """Blocked: piping `{job}` into `{sink}` loses the status AND the output.

1. The exit status you get back is `{sink}`'s, not `{job}`'s. `tail` succeeds at
   printing nothing, so a FAILED build comes back as exit 0 — and `| rg error`
   exits 1 when the build was CLEAN. Any success/failure call you make from that
   number is a coin flip.
2. Everything the filter dropped is gone. Not collapsed — never written
   anywhere. The first error is usually above the tail window, and when the
   summary turns out to be wrong there is nothing left to re-read.

Write the log, then look at it:

    LOG=/var/tmp/{stem}-$(date +%Y%m%d-%H%M%S).log
    {command} >"$LOG" 2>&1; echo "exit=$? log=$LOG"

then `rg -n 'error|warning|FAILED' "$LOG"`, or Read its tail. /var/tmp, never
/tmp, which is RAM-backed here. Long runs go to the background with the same
shape, so the log stays readable while it runs. Put the log path in your reply.

If you really want the live tail, keep the full copy and the real status:

    set -o pipefail
    {command} 2>&1 | tee "$LOG" | tail -50; echo "exit=$? log=$LOG"
"""


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

    Skips leading keywords and env assignments, so `TMPDIR=/var/tmp just ci`
    reports `just`.
    """
    for i, tok in enumerate(seg):
        if tok in _PREFIXES or _ASSIGNMENT.match(tok):
            continue
        return _basename(tok), seg[i + 1:]
    return None


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


def _is_job(cmd: str, args: list[str]) -> bool:
    """True for a build/test/CI run — not a query that merely shares the binary."""
    only = _SUBCOMMAND_ONLY.get(cmd)
    words = [a for a in args if not a.startswith("-")]
    if only is not None:
        return bool(words) and words[0] in only
    if cmd not in _JOB_COMMANDS:
        return False
    short = _QUERY_SHORT_FLAGS.get(cmd, set())
    if any(a in _QUERY_FLAGS or a in short for a in args):
        return False
    return not (words and words[0] in _QUERY_SUBCOMMANDS)


def _writes_a_file(seg: list[str]) -> bool:
    """True if this simple command redirects to a file, or tees into one."""
    for i, tok in enumerate(seg):
        if tok in _FILE_REDIRECTS and i + 1 < len(seg):
            return True
        if _basename(tok) == "tee" and any(
            not a.startswith("-") for a in seg[i + 1:]
        ):
            return True
    return False


def _status_is_recovered(command: str) -> bool:
    """True if the real exit status survives the pipe."""
    return "pipefail" in command or "PIPESTATUS" in command


def offending_pipeline(command: str) -> tuple[str, str] | None:
    """Return (job command, truncating stage) for the first bad pipeline."""
    tokens = _tokenize(command)
    if tokens is None:
        return None
    segments = _segments(tokens)
    if not any(op in _PIPES for op, _ in segments):
        return None

    preserved = any(_writes_a_file(seg) for _, seg in segments)
    recovered = _status_is_recovered(command)
    if preserved and recovered:
        return None

    for pipeline in _pipelines(segments):
        if len(pipeline) < 2:
            continue
        job, args = pipeline[0]
        if not _is_job(job, args):
            continue
        sink = pipeline[-1][0]
        if sink in _SINKS:
            return job, sink
    return None


def _deny(reason: str) -> None:
    print(json.dumps({
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "deny",
            "permissionDecisionReason": reason,
        }
    }))


# Trailing redirections on the source stage: `2>&1`, `>&2`, `>out`, `&>>out`.
# They are stripped before the suggestion is built, because the suggestion adds
# its own — leaving them turns `cmd 2>&1` into `cmd 2>&1 >"$LOG" 2>&1`, where
# the first dup points stderr at the OLD stdout and the log loses it.
_TRAILING_REDIRECT = re.compile(r"\s*(?:\d*>&\s*\d+|&?>>?\s*[^\s|;&]+)\s*$")


def _source_command(command: str) -> str:
    """The text up to the first pipe — what the log should be a log OF."""
    head = re.split(r"\|", command, maxsplit=1)[0].strip()
    head = head.rstrip("&;").strip()
    while True:
        stripped = _TRAILING_REDIRECT.sub("", head).strip()
        if stripped == head or not stripped:
            break
        head = stripped
    return head or command


def main() -> int:
    try:
        payload = json.load(sys.stdin)
    except (json.JSONDecodeError, ValueError):
        return 0
    if not isinstance(payload, dict):
        return 0
    if payload.get("tool_name") != "Bash":
        return 0
    tool_input = payload.get("tool_input")
    if not isinstance(tool_input, dict):
        return 0
    command = str(tool_input.get("command", ""))

    # Cheap pre-filter: no pipe, nothing to do.
    if "|" not in command:
        return 0
    hit = offending_pipeline(command)
    if hit is None:
        return 0
    job, sink = hit
    source = _source_command(command)
    _deny(REASON.format(
        job=job, sink=sink, command=source, stem=_basename(job),
    ))
    return 0


if __name__ == "__main__":
    sys.exit(main())

#!/usr/bin/env python3
"""Claude Code hook: confine a session's file writes to a single repository.

An agent editing a repo it was not pointed at is one of the most expensive
failure modes there is: the change lands in a working copy whose state nobody
inspected, under rules that were never loaded, inside a changeset described as
something else entirely. It is not caught by review, because nobody is
reviewing that repo in that session.

So: the FIRST repository a session writes to becomes that session's repository,
and every later write outside it is refused. There is no unlock. Working in a
different repo means a session started for that repo -- which is also what
makes the rules of that repo get loaded, and its working copy get looked at.

Behaviour:
- PreToolUse on Edit / Write / MultiEdit / NotebookEdit only. Reads are never
  touched: investigation must stay free to roam.
- The pin is keyed on `session_id`, which subagents share with their parent, so
  every subagent inherits the pin and cannot wander off on its own.
- Paths outside any repository are ungoverned and never pin: the scratchpad,
  /tmp work orders, ~/.claude, the flat checkout root itself.
- The chezmoi source directory is exempt. It is a git repo, but editing a
  template there is config management orthogonal to whatever project the
  session is about, and pinning to it would wedge the real work.
- Git worktrees and jj workspaces of the pinned repo resolve to the same
  identity as the main checkout, so an isolated-worktree agent still works.
- Submodules resolve to their own identity, because they are their own repo.

Refuses only when it is certain: a resolvable path, inside a real repository,
that is demonstrably not the pinned one. Anything unexpected -- malformed
payload, unreadable state, no path -- defers, because a broken guard must not
wedge every edit in the session.
"""

from __future__ import annotations

import json
import os
import re
import sys
import time
from pathlib import Path

_EDIT_TOOLS = {"Edit", "Write", "MultiEdit", "NotebookEdit"}

# NotebookEdit names its target differently from every other edit tool.
_PATH_KEYS = ("file_path", "notebook_path")

_STATE_DIR = Path.home() / ".cache" / "claude-code-repo-guard" / "pins"

# Retention for pin files. Not synchronisation -- purely how long a dead
# session's 200-byte record is kept before being swept.
_PIN_RETENTION_S = 14 * 24 * 3600

_SAFE_SESSION_ID = re.compile(r"\A[A-Za-z0-9._-]{1,128}\Z")


def _resolve(raw: str) -> Path | None:
    """Absolute, symlink-resolved path. The file need not exist yet."""
    try:
        return Path(os.path.expanduser(raw)).resolve()
    except (OSError, RuntimeError, ValueError):
        return None


def _chezmoi_source_dir() -> Path | None:
    """The chezmoi source directory, without shelling out to chezmoi.

    Reading the config beats invoking chezmoi: this runs on every single edit,
    and `chezmoi` renders state we have no use for here.
    """
    env = os.environ.get("CHEZMOI_SOURCE_DIR")
    if env:
        return _resolve(env)

    config = Path.home() / ".config" / "chezmoi" / "chezmoi.toml"
    try:
        text = config.read_text(encoding="utf-8", errors="replace")
    except OSError:
        text = ""
    # Only a top-level `sourceDir` counts; anything nested under a [table] is
    # something else that happens to share the name.
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("["):
            break
        match = re.match(r'\AsourceDir\s*=\s*["\'](.+)["\']\s*\Z', stripped)
        if match:
            return _resolve(match.group(1))

    return _resolve("~/.local/share/chezmoi")


def _exempt_roots() -> list[Path]:
    roots = []
    source = _chezmoi_source_dir()
    if source is not None:
        roots.append(source)
    return roots


def _read(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8", errors="replace").strip()
    except OSError:
        return ""


def _resolve_from(base: Path, raw: str) -> Path | None:
    pointed = Path(raw)
    if not pointed.is_absolute():
        pointed = base / pointed
    try:
        return pointed.resolve()
    except (OSError, RuntimeError):
        return None


def _jj_main_root(marker: Path) -> Path | None:
    """Main working-copy root behind a `.jj` marker, or None if undecidable.

    A secondary workspace stores `.jj/repo` as a FILE pointing at the primary
    workspace's `.jj/repo` -- usually by a RELATIVE path, resolved against the
    `.jj` directory. Climbing back out of `<primary>/.jj/repo` gives the
    primary root, so a workspace and its primary are one repo.
    """
    repo = marker / "repo"
    if repo.is_dir():
        return marker.parent
    if repo.is_file():
        raw = _read(repo)
        if raw:
            pointed = _resolve_from(marker, raw)
            if (
                pointed is not None
                and pointed.name == "repo"
                and pointed.parent.name == ".jj"
            ):
                return pointed.parent.parent
    return None


def _git_main_root(marker: Path) -> Path | None:
    """Main working-copy root behind a `.git` marker, or None if undecidable.

    A linked worktree's `.git` is a FILE holding `gitdir: <path>` pointing at
    `<main>/.git/worktrees/<name>`; climbing out of that lands on the main
    checkout, so a worktree agent counts as the same repo. A submodule's
    `.git` file instead points into `<super>/.git/modules/<name>`, which does
    not match that shape -- so the submodule keeps its own identity, which is
    correct: a submodule is a different repository.
    """
    if marker.is_dir():
        return marker.parent
    if not marker.is_file():
        return None
    for line in _read(marker).splitlines():
        if not line.startswith("gitdir:"):
            continue
        raw = line.split(":", 1)[1].strip()
        if not raw:
            continue
        pointed = _resolve_from(marker.parent, raw)
        if pointed is None:
            return None
        if pointed.parent.name == "worktrees" and pointed.parent.parent.name == ".git":
            return pointed.parent.parent.parent
        # Submodule, or anything else unrecognised: its own repo.
        return marker.parent
    return None


def repo_of(path: Path) -> tuple[Path, Path] | None:
    """Nearest enclosing repository as `(checkout, identity)`, or None.

    `identity` is the MAIN working-copy root, so every view of one repository
    -- the colocated checkout itself, a jj workspace of it, a git worktree of
    it -- collapses to the same value. Normalising on the main root rather
    than on whichever marker happened to be found is what makes a colocated
    repo (`.git` AND `.jj`, which is every checkout here) agree with its own
    jj workspace, where only `.jj` exists.
    """
    for candidate in (path, *path.parents):
        jj = candidate / ".jj"
        git = candidate / ".git"
        if not jj.is_dir() and not git.exists():
            continue
        identity = _jj_main_root(jj) if jj.is_dir() else None
        if identity is None and git.exists():
            identity = _git_main_root(git)
        return candidate, identity if identity is not None else candidate
    return None


def _sweep(state_dir: Path) -> None:
    """Drop pin files from long-dead sessions. Best effort, never fatal."""
    cutoff = time.time() - _PIN_RETENTION_S
    try:
        entries = list(state_dir.iterdir())
    except OSError:
        return
    for entry in entries:
        try:
            if entry.is_file() and entry.stat().st_mtime < cutoff:
                entry.unlink()
        except OSError:
            continue


def pin_path(session_id: str) -> Path | None:
    if not _SAFE_SESSION_ID.match(session_id):
        return None
    return _STATE_DIR / f"{session_id}.json"


def read_pin(pin: Path) -> dict | None:
    try:
        data = json.loads(pin.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError, ValueError):
        return None
    if not isinstance(data, dict) or "identity" not in data:
        return None
    return data


def claim(pin: Path, root: Path, identity: Path, path: Path) -> dict | None:
    """Claim the session for `identity`, or return the winning claim.

    O_CREAT|O_EXCL makes the claim atomic, so two subagents writing at the same
    instant cannot end up with different ideas of which repo is theirs.
    """
    record = {
        "identity": str(identity),
        "root": str(root),
        "claimed_by": str(path),
        "claimed_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
    }
    payload = json.dumps(record, indent=2).encode("utf-8")
    try:
        pin.parent.mkdir(parents=True, exist_ok=True)
        fd = os.open(pin, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    except FileExistsError:
        return read_pin(pin)
    except OSError:
        return None
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(payload)
    except OSError:
        return None
    _sweep(pin.parent)
    return record


def deny(path: Path, foreign_root: Path, pinned_root: str, is_subagent: bool) -> None:
    who = "This subagent" if is_subagent else "This session"
    reason = (
        f"Blocked: `{path}` is in a repository this session does not own.\n\n"
        f"  session's repo: {pinned_root}\n"
        f"  write targeted: {foreign_root}\n\n"
        f"{who} is pinned to the first repo it wrote to, and that pin does not "
        "lift. Editing another repo means landing a change in a working copy "
        "nobody inspected, under rules that were never loaded, inside a "
        "changeset described as something else. That is exactly what this hook "
        "exists to stop -- do not try to route around it.\n\n"
        "What to do instead:\n"
        f"  - Report it: exact file, lines, and the change {pinned_root} needs "
        "from it. Do not ask for permission to make the edit -- the answer is "
        "no.\n"
        "  - If it deserves real work, write a work order with "
        "`/tyrex-core:work-order` so a fresh agent does it in that repo, with "
        "that repo's rules loaded.\n"
        "  - Reads are not blocked. Read anything you need there to write an "
        "accurate report."
    )
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


def main() -> int:
    try:
        payload = json.load(sys.stdin)
    except (json.JSONDecodeError, ValueError):
        return 0
    if not isinstance(payload, dict):
        return 0
    if payload.get("hook_event_name") != "PreToolUse":
        return 0
    if payload.get("tool_name") not in _EDIT_TOOLS:
        return 0

    tool_input = payload.get("tool_input")
    if not isinstance(tool_input, dict):
        return 0
    raw = next((tool_input[k] for k in _PATH_KEYS if tool_input.get(k)), None)
    if not isinstance(raw, str) or not raw:
        return 0

    path = _resolve(raw)
    if path is None:
        return 0

    found = repo_of(path)
    if found is None:
        # Not in a repository: scratchpad, /tmp, ~/.claude, checkout root.
        return 0
    root, identity = found

    for exempt in _exempt_roots():
        if root == exempt or exempt in root.parents:
            return 0

    session_id = payload.get("session_id")
    if not isinstance(session_id, str):
        return 0
    pin = pin_path(session_id)
    if pin is None:
        return 0

    record = read_pin(pin)
    if record is None:
        record = claim(pin, root, identity, path)
        if record is None:
            # Could not establish a pin, so nothing to compare against.
            return 0

    if record.get("identity") == str(identity):
        return 0

    deny(
        path,
        root,
        record.get("root") or record.get("identity", "<unknown>"),
        bool(payload.get("agent_id")),
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())

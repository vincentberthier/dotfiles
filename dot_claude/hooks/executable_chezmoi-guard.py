#!/usr/bin/env python3
"""Claude Code hook: keep chezmoi edits on the edit-in-place -> re-add path.

The working process for chezmoi-managed config on this machine is:

    1. edit the TARGET in place (~/.claude/CLAUDE.md, ~/.config/..., ...)
    2. `chezmoi re-add <target>` to capture it back into the source

Step 2 is not bookkeeping. `~/.config/chezmoi/chezmoi.toml` sets
`autoCommit = true` and `autoPush = true`, and those fire on source-state
commands like `re-add` -- so `re-add` is the step that actually commits and
pushes. Hand-editing the source file and running `chezmoi apply` moves the
bytes into place but commits nothing: the change sits dirty in the source
repo, invisible, and diverges from what the other machines push. Edits left
in that limbo are barely better than never having synced at all.

Behaviour:
- PreToolUse on Edit / Write / NotebookEdit: block edits to files inside the
  chezmoi source directory when a real target exists to edit instead, and
  name that target.
- PostToolUse on the same tools: after a managed target is edited, hand back
  the exact `chezmoi re-add` command needed to land it.
- Never blocks where the source is the only editable copy: templates
  (`*.tmpl`), scripts (`run_*`), `.chezmoitemplates/`, and anything whose
  target does not exist on disk.
- On any trouble (chezmoi missing, slow, unexpected payload) defers silently
  with exit 0 -- fail open, never wedge editing.
"""

import json
import os
import subprocess
import sys
from pathlib import Path

_EDIT_TOOLS = {"Edit", "Write", "NotebookEdit", "MultiEdit"}

# chezmoi is fast (tens of ms); this bound only exists so a hung binary cannot
# block every edit in the session.
_TIMEOUT_S = 5

# Source entries with no target file to edit in place.
_SOURCE_ONLY_PREFIXES = ("run_", ".chezmoi")
_SOURCE_ONLY_SUFFIXES = (".tmpl",)


def _run_chezmoi(args: list[str]) -> str | None:
    """Return stdout of a chezmoi invocation, or None if it failed."""
    try:
        result = subprocess.run(
            ["chezmoi", *args],
            capture_output=True,
            text=True,
            timeout=_TIMEOUT_S,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    if result.returncode != 0:
        return None
    out = result.stdout.strip()
    return out or None


def source_dir() -> Path | None:
    out = _run_chezmoi(["source-path"])
    return Path(out) if out else None


def source_only(source: Path, src_dir: Path) -> bool:
    """True if `source` has no in-place target: template, script, metadata."""
    if source.name.endswith(_SOURCE_ONLY_SUFFIXES):
        return True
    try:
        relative = source.relative_to(src_dir)
    except ValueError:
        return True
    # A `run_` script anywhere in the tree, or chezmoi metadata at any level.
    return any(part.startswith(_SOURCE_ONLY_PREFIXES) for part in relative.parts)


def target_for(source: Path) -> Path | None:
    """Return the live target for a source file, or None if there isn't one.

    Round-trips through `target-path` and back through `source-path`: chezmoi
    happily invents a target for any path under the source dir, so the only
    proof that `source` really is the source of `target` is that the reverse
    lookup lands back where it started.
    """
    out = _run_chezmoi(["target-path", str(source)])
    if out is None:
        return None
    target = Path(out)
    if not target.is_file():
        return None
    back = _run_chezmoi(["source-path", str(target)])
    if back is None or Path(back) != source:
        return None
    return target


def managed_target(path: Path, src_dir: Path) -> Path | None:
    """Return `path` itself if it is a chezmoi-managed target, else None."""
    if src_dir == path or src_dir in path.parents:
        return None
    return path if _run_chezmoi(["source-path", str(path)]) else None


def block_source_edit(source: Path, target: Path) -> None:
    reason = (
        f"Blocked: `{source}` is a chezmoi SOURCE file.\n\n"
        "The process on this machine is edit-in-place, then re-add. Editing "
        "the source and applying leaves the change uncommitted and unpushed "
        "in the source repo -- autoCommit/autoPush only fire on source-state "
        "commands like `re-add`.\n\n"
        "Edit the live file instead:\n"
        f"  {target}\n\n"
        "Then land it -- this commits and pushes:\n"
        f"  chezmoi re-add {target}"
    )
    print(json.dumps({"decision": "block", "reason": reason}))


def remind_re_add(target: Path) -> None:
    context = (
        f"`{target}` is chezmoi-managed. The edit is live but not yet in the "
        "source repo. Before this task is done, land it with:\n"
        f"  chezmoi re-add {target}\n"
        "That is what commits and pushes it (autoCommit/autoPush). Leaving it "
        "unlanded strands the change on this machine only."
    )
    print(
        json.dumps(
            {
                "hookSpecificOutput": {
                    "hookEventName": "PostToolUse",
                    "additionalContext": context,
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

    if payload.get("tool_name") not in _EDIT_TOOLS:
        return 0

    raw = payload.get("tool_input", {}).get("file_path", "")
    if not raw:
        return 0

    try:
        path = Path(os.path.expanduser(raw)).resolve()
    except OSError:
        return 0

    src_dir = source_dir()
    if src_dir is None:
        # chezmoi unavailable or not initialised -- nothing to protect.
        return 0

    if payload.get("hook_event_name") == "PostToolUse":
        target = managed_target(path, src_dir)
        if target is not None:
            remind_re_add(target)
        return 0

    # PreToolUse: steer source edits back to the target.
    if src_dir != path and src_dir not in path.parents:
        return 0
    if source_only(path, src_dir):
        return 0
    target = target_for(path)
    if target is None:
        return 0
    block_source_edit(path, target)
    return 0


if __name__ == "__main__":
    sys.exit(main())

#!/usr/bin/env python3
"""Claude Code PreToolUse hook: block edits to chezmoi-managed files.

Config files under ~/.claude, ~/.config and friends are managed by chezmoi.
Editing the target directly looks like it worked — until the next
`chezmoi apply` silently reverts it, because the source of truth is the file
under the chezmoi source directory, not the one in place.

Behaviour:
- Fires on Edit / Write / NotebookEdit.
- Resolves the target path through `chezmoi source-path`.
- If the file is managed, blocks and names the source path to edit instead.
- Never fires for paths already inside the chezmoi source directory — editing
  the source is the correct action.
- On any trouble (chezmoi missing, slow, unexpected payload) defers silently
  with exit 0 — fail open, never wedge editing.
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


def source_path_for(target: Path) -> Path | None:
    """Return the chezmoi source path for `target`, or None if unmanaged."""
    out = _run_chezmoi(["source-path", str(target)])
    return Path(out) if out else None


def main() -> int:
    try:
        payload = json.load(sys.stdin)
    except (json.JSONDecodeError, ValueError):
        return 0

    if payload.get("tool_name") not in _EDIT_TOOLS:
        return 0

    raw = payload.get("tool_input", {}).get("file_path", "")
    if not raw:
        return 0

    try:
        target = Path(os.path.expanduser(raw)).resolve()
    except OSError:
        return 0

    src_dir = source_dir()
    if src_dir is None:
        # chezmoi unavailable or not initialised — nothing to protect.
        return 0

    # Editing the source itself is exactly what this hook wants to happen.
    if src_dir in target.parents or src_dir == target:
        return 0

    managed_source = source_path_for(target)
    if managed_source is None:
        return 0

    reason = (
        f"Blocked: `{target}` is managed by chezmoi.\n\n"
        "Editing the target directly does not stick — the next "
        "`chezmoi apply` overwrites it from the source, and the work is lost "
        "silently.\n\n"
        "Edit the source instead:\n"
        f"  {managed_source}\n\n"
        "Then apply it:\n"
        f"  chezmoi apply {target}\n\n"
        "If the target is deliberately ahead of the source (edits already made "
        f"in place), capture them first with `chezmoi re-add {target}`, then "
        "continue editing the source."
    )
    print(json.dumps({"decision": "block", "reason": reason}))
    return 0


if __name__ == "__main__":
    sys.exit(main())

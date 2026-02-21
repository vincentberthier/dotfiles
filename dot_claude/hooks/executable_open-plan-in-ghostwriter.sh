#!/usr/bin/env bash
# Hook: open plan files in Ghostwriter when Claude reads them.
# Triggers on PostToolUse(Read) for files under known plans directories.

INPUT=$(cat)
FILE_PATH=$(printf '%s' "$INPUT" | jq -r '.tool_input.file_path // empty')
CWD=$(printf '%s' "$INPUT" | jq -r '.cwd // empty')

[[ -z "$FILE_PATH" ]] && exit 0
[[ ! -f "$FILE_PATH" ]] && exit 0

# Project-local plan directory
if [[ -z "$CWD" || "$FILE_PATH" != "$CWD/.claude/plans/"* ]]; then
    exit 0
fi

if [[ "$is_plan" == true ]]; then
    if command -v ghostwriter &>/dev/null; then
        ghostwriter "$FILE_PATH" &>/dev/null &
        disown
    fi
fi

exit 0

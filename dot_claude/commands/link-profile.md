---
allowed-tools: Bash
description: Sync symlinks in a Claude profile dir to ~/.claude/ shared config
---

Sync the Claude profile directory `$ARGUMENTS` by creating symlinks to `~/.claude/` for all shared config, skipping account-specific files. Also merges shared MCP server definitions into the profile's `.claude.json`.

Run this bash script:

```bash
target="$ARGUMENTS"

if [ -z "$target" ]; then
    echo "Usage: /link-profile <profile-dir>" >&2
    exit 1
fi

if [ ! -d "$target" ]; then
    echo "Error: '$target' is not a directory" >&2
    exit 1
fi

skip=".credentials.json .claude.json projects cache debug history.jsonl"
count=0

for item in ~/.claude/* ~/.claude/.*; do
    name=$(basename "$item")
    [ "$name" = "." ] || [ "$name" = ".." ] && continue
    echo "$skip" | grep -qw "$name" && continue
    case "$name" in .claude.json.backup*) continue ;; esac

    ln -sf "$item" "$target/$name"
    echo "  linked: $name"
    count=$((count + 1))
done

echo "Done: $count symlinks created in $target"

# Merge shared MCP servers into the profile's .claude.json
mcp_source="$HOME/.claude/mcp-servers.json"
state_file="$target/.claude.json"

if [ -f "$mcp_source" ] && [ -f "$state_file" ]; then
    tmp=$(mktemp)
    if jq --slurpfile mcp "$mcp_source" '.mcpServers = $mcp[0]' "$state_file" > "$tmp"; then
        mv "$tmp" "$state_file"
        echo "  merged: mcpServers from mcp-servers.json"
    else
        rm -f "$tmp"
        echo "Error: failed to merge MCP servers into $state_file" >&2
    fi
elif [ -f "$mcp_source" ] && [ ! -f "$state_file" ]; then
    echo "Warning: $state_file not found, skipping MCP merge (run claude once first)" >&2
fi
```

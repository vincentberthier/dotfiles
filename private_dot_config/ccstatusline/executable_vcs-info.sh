#!/usr/bin/env bash
cwd=$(jq -r '.cwd // empty')
[ -z "$cwd" ] && exit 0
cd "$cwd" 2>/dev/null || exit 0

# Try jj first
if jj root >/dev/null 2>&1; then
    raw=$(jj log --no-graph --ignore-working-copy -r @ \
        -T 'concat(
            if(bookmarks, bookmarks.join(","), change_id.shortest(4)),
            "\t",
            empty
        )' --color never 2>/dev/null)

    IFS=$'\t' read -r ref is_empty <<< "$raw"

    if [ "$is_empty" = "true" ]; then
        echo "$ref ✓"
    else
        echo "$ref ●"
    fi
# Fall back to git
elif git rev-parse --git-dir >/dev/null 2>&1; then
    branch=$(git branch --show-current 2>/dev/null)
    [ -z "$branch" ] && branch=$(git rev-parse --short HEAD 2>/dev/null)

    if git status --porcelain 2>/dev/null | head -1 | grep -q .; then
        echo "$branch ●"
    else
        echo "$branch ✓"
    fi
fi

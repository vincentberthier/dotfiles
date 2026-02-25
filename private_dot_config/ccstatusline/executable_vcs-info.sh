#!/usr/bin/env bash
cwd=$(jq -r '.cwd // empty')
[ -z "$cwd" ] && exit 0
cd "$cwd" 2>/dev/null || exit 0

# Catppuccin Mocha palette
c_paren='\e[38;2;108;112;134m'   # overlay0 — parentheses
c_ref='\e[38;2;203;166;247m'     # mauve — change ref
c_desc='\e[38;2;166;173;200m'    # subtext0 — description
c_clean='\e[38;2;166;227;161m'   # green — clean indicator
c_dirty='\e[38;2;249;226;175m'   # yellow — dirty indicator
c_reset='\e[0m'

# Try jj first
if jj root >/dev/null 2>&1; then
    raw=$(jj log --no-graph --ignore-working-copy -r @ \
        -T 'concat(
            if(bookmarks, bookmarks.join(","), change_id.shortest(4)),
            "\t",
            description.first_line(),
            "\t",
            empty
        )' --color never 2>/dev/null)

    ref=$(printf '%s' "$raw" | cut -d$'\t' -f1)
    desc=$(printf '%s' "$raw" | cut -d$'\t' -f2)
    is_empty=$(printf '%s' "$raw" | cut -d$'\t' -f3)

    # In squash workflow, @ is undescribed — show @-'s description instead
    if [ -z "$desc" ]; then
        desc=$(jj log --no-graph --ignore-working-copy -r @- \
            -T 'description.first_line()' --color never 2>/dev/null)
    fi

    if [ "$is_empty" = "true" ]; then
        indicator="${c_clean}✓${c_reset}"
    else
        indicator="${c_dirty}●${c_reset}"
    fi

    out="${c_paren}(${c_reset}${c_ref}${ref}${c_reset}${c_paren})${c_reset}"
    [ -n "$desc" ] && out="${out} ${c_desc}${desc}${c_reset}"
    printf '%b %b\n' "$out" "$indicator"

# Fall back to git
elif git rev-parse --git-dir >/dev/null 2>&1; then
    branch=$(git branch --show-current 2>/dev/null)
    [ -z "$branch" ] && branch=$(git rev-parse --short HEAD 2>/dev/null)

    if git status --porcelain 2>/dev/null | head -1 | grep -q .; then
        indicator="${c_dirty}●${c_reset}"
    else
        indicator="${c_clean}✓${c_reset}"
    fi

    out="${c_paren}(${c_reset}${c_ref}${branch}${c_reset}${c_paren})${c_reset}"
    printf '%b %b\n' "$out" "$indicator"
fi

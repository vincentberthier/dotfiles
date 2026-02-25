#!/usr/bin/env fish

# Minimal git prompt for non-jj repos
# Shows: branch + clean/dirty indicator

set -l icon_branch \ue0a0

set -l branch (git branch --show-current 2>/dev/null)
if test -z "$branch"
    set branch (git rev-parse --short HEAD 2>/dev/null)
    test -z "$branch"; and exit 1
end

set_color cba6f7 # mauve
echo -n "$icon_branch $branch"
set_color normal

if git status --porcelain 2>/dev/null | string length -q
    echo -n " "
    set_color f9e2af # yellow
    echo -n "●"
    set_color normal
else
    echo -n " "
    set_color a6e3a1 # green
    echo -n "✓"
    set_color normal
end

echo -n " "

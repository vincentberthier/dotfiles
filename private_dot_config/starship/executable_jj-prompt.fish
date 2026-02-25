#!/usr/bin/env fish

# jj prompt for starship
# Shows: bookmark (+distance), change ID (bold prefix + dim rest), conflicts, file changes

# Nerd font icons (must be unquoted for fish \u escape)
set -l icon_branch \ue0a0
set -l icon_conflict \uf071

set -l raw (jj log --no-graph --ignore-working-copy -r @ \
    -T 'concat(
        change_id.shortest(4).prefix(), "\t",
        change_id.shortest(4).rest(), "\t",
        if(bookmarks, bookmarks.join(","), ""), "\t",
        conflict, "\t",
        empty
    )' --color never 2>/dev/null)

test -z "$raw"; and exit 1

set -l f (string split \t -- $raw)
set -l cid_hi $f[1]
set -l cid_lo $f[2]
set -l bm_here $f[3]
set -l has_conflict $f[4]
set -l is_empty $f[5]

# --- Bookmark ---
set -l bookmark $bm_here
set -l bm_dist 0

if test -z "$bookmark"
    set -l rev 'heads(::@- & bookmarks())'
    set bookmark (jj log --no-graph --ignore-working-copy --limit 1 -r "$rev" \
        -T 'bookmarks.join(",")' --color never 2>/dev/null)
    if test -n "$bookmark"
        set bm_dist (jj log --no-graph --ignore-working-copy \
            -r "$rev..@" -T '"x"' --color never 2>/dev/null | wc -c | string trim)
    end
end

if test -n "$bookmark"
    set_color 74c7ec # sapphire
    echo -n "$icon_branch $bookmark"
    set_color normal
    if test "$bm_dist" -gt 0
        set_color 6c7086 # overlay0
        echo -n " (+$bm_dist)"
        set_color normal
    end
    echo -n " "
end

# --- Change ID (bold unique prefix, dim rest) ---
set_color --bold cba6f7 # mauve
echo -n "$cid_hi"
set_color normal
if test -n "$cid_lo"
    set_color 6c7086 # overlay0
    echo -n "$cid_lo"
    set_color normal
end

# --- Conflict ---
if test "$has_conflict" = true
    echo -n " "
    set_color --bold f38ba8 # red
    echo -n "$icon_conflict conflict"
    set_color normal
end

# --- State ---
if test "$is_empty" = true
    echo -n " "
    set_color a6e3a1 # green
    echo -n "✓"
    set_color normal
else
    set -l added 0
    set -l modified 0
    set -l deleted 0
    for line in (jj diff --summary --ignore-working-copy --color never 2>/dev/null)
        switch (string sub -l 1 -- $line)
            case A
                set added (math $added + 1)
            case M R
                set modified (math $modified + 1)
            case D
                set deleted (math $deleted + 1)
        end
    end
    if test $added -gt 0
        echo -n " "
        set_color a6e3a1 # green
        echo -n "+$added"
        set_color normal
    end
    if test $modified -gt 0
        echo -n " "
        set_color f9e2af # yellow
        echo -n "~$modified"
        set_color normal
    end
    if test $deleted -gt 0
        echo -n " "
        set_color f38ba8 # red
        echo -n "-$deleted"
        set_color normal
    end
end

echo -n " "

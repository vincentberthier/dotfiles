function ff --wraps fd --description "Look into 1, for files with extension 2, matching 3"
    # `shift` is not a fish builtin — the old version died on it before doing any work.
    if test (count $argv) -lt 3
        echo "usage: ff <root> <extension> <pattern> [fd options…]" >&2
        return 1
    end

    set -l root $argv[1]
    set -l extension $argv[2]
    set -l pattern $argv[3]
    set -l fd_opts $argv[4..-1]

    echo "Looking for $pattern in $root with extension $extension"
    fd --extension $extension $fd_opts . $root \
        --exec rg --color=always --with-filename --line-number -- $pattern
end

function clean-corrbolg --description 'Delete Siril process/ dirs and .history files on Corrbolg (regenerable astro intermediates)'
    set -l root /run/media/vincent/Corrbolg
    set -l dry_run false

    for arg in $argv
        switch $arg
            case --dry-run -n
                set dry_run true
            case '*'
                echo "clean-corrbolg: unknown argument '$arg' (use --dry-run)" >&2
                return 2
        end
    end

    # Scope strictly to the Siril data tree. NEVER scan all of $root: it also
    # holds a home backup with source dirs named "process" (rust/tokio/cmake)
    # and an npm "process" package — a blind name-match would delete those.
    set -l scan $root/Astro
    if not test -d $scan
        echo "clean-corrbolg: $scan not found (drive mounted?)" >&2
        return 1
    end

    # Collect targets via NUL-delimited fd so paths with spaces survive.
    # -I: ignore .gitignore/.fdignore;  -H: include hidden (.history).
    set -l targets
    while read -lz d
        set -a targets $d
    end <(fd -0 -I --type d --glob process $scan | psub)
    while read -lz f
        set -a targets $f
    end <(fd -0 -I -H --type f --glob '.history' $scan | psub)

    if test (count $targets) -eq 0
        echo "clean-corrbolg: nothing to clean under $scan"
        return 0
    end

    # Safety net: never delete anything outside the Astro tree, no matter what
    # the search returned. Belt-and-suspenders against a future scope change.
    for t in $targets
        if not string match -q -- "$scan/*" $t
            echo "clean-corrbolg: ABORT — '$t' is outside $scan" >&2
            return 1
        end
    end

    printf '%s\n' $targets
    echo "-> "(count $targets)" item(s) to delete"

    if $dry_run
        echo "(dry run — nothing deleted)"
        return 0
    end

    echo "WARNING: this is a permanent rm -rf, not trash (target drive is full)."
    read -l -P "Permanently delete all of the above? [y/N] " ans
    if not string match -qi y -- $ans
        echo "aborted"
        return 1
    end

    rm -rf -- $targets
    and echo "Done. Space reclaimed on $root."
end

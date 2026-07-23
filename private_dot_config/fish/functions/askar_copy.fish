function askar_copy --description "Park the mount, pull N.I.N.A images off the Gaius, then shut it down"
    argparse --name=askar_copy h/help park no-park shutdown no-shutdown -- $argv
    or return 1

    if set -q _flag_help
        echo "usage: askar_copy [--park|--no-park] [--shutdown|--no-shutdown]"
        echo
        echo "  Pulls the N.I.N.A images off the Gaius into Raws/, deleting the source"
        echo "  frames as they sync, prunes the cloud-check snapshots, normalises the"
        echo "  target folder names to lowercase ASCII, and hardlinks the night's flats"
        echo "  into every target that shot lights."
        echo
        echo "  --park / --no-park          park the mount first     (default: $askar_copy_park)"
        echo "  --shutdown / --no-shutdown  shut the Gaius down after (default: $askar_copy_shutdown)"
        echo
        echo "  The defaults come from \$askar_copy_park and \$askar_copy_shutdown; set"
        echo "  either to 'no' (e.g. in conf.d/alias_askar.fish) to flip it session-wide."
        return 0
    end

    # Defaults live in the global variables, flags override them for one call.
    set -l park $askar_copy_park
    set -l shutdown $askar_copy_shutdown
    test -z "$park"; and set park yes
    test -z "$shutdown"; and set shutdown yes
    set -q _flag_park; and set park yes
    set -q _flag_no_park; and set park no
    set -q _flag_shutdown; and set shutdown yes
    set -q _flag_no_shutdown; and set shutdown no

    for pair in "park:$park" "shutdown:$shutdown"
        set -l name (string split -f1 : $pair)
        set -l value (string split -f2 : $pair)
        if not contains -- "$value" yes no
            echo "askar_copy: \$askar_copy_$name must be 'yes' or 'no', got '$value'" >&2
            return 2
        end
    end

    set -l src gaius:/cygdrive/c/Users/RBFocus/Documents/N.I.N.A/Images/
    set -l dst /run/media/vincent/Corrbolg/dso/data/
    if not test -d $dst
        echo "askar_copy: destination $dst not mounted — aborting" >&2
        return 1
    end

    # The post-copy helpers live in the astro-pipeline repo, not on the data disk.
    set -l astro_pipeline $HOME/Projets/astro-pipeline
    for helper in normalize_target_dirs.py collect_flats.py link_flats.py
        if not test -x $astro_pipeline/tools/$helper
            echo "askar_copy: missing $astro_pipeline/tools/$helper — aborting" >&2
            return 1
        end
    end

    # Park first. OnStep auto-starts tracking when the Gaius powers it up, so the
    # RA axis walks away from home for as long as the machine is on; power it off
    # unparked and the next boot cold-starts on a wrong position (hence the resync).
    # Parking stops tracking and stores the position in NV: the mount wakes parked.
    if test $park = yes
        askar_parked >/dev/null 2>&1
        set -l parked $status
        switch $parked
            case 0
                echo "askar_copy: mount already parked."
            case 10
                echo "askar_copy: mount is tracking — parking it first…"
                if not askar_park
                    echo "askar_copy: WARNING — park failed; copying anyway" >&2
                end
            case '*'
                echo "askar_copy: WARNING — cannot read mount park state (exit $parked); copying anyway" >&2
        end
    else
        echo "askar_copy: --no-park — leaving the mount alone."
    end

    # SNAPSHOTS are the Pre-Run cloud-check frames: a live view of the sky during the
    # session, never data. N.I.N.A cannot be told not to save them (TakeExposure always
    # enqueues the save; there is no FilePatternSNAPSHOT), and since the wait loops sit
    # outside a target container, $$TARGETNAME$$ is empty and they land in a stray
    # Images\<date>\SNAPSHOTS\. Don't copy them — they're deleted on the Gaius below.
    set -l rc 1
    for attempt in (seq 1 100)
        command rsync -ahP --info=progress2 --partial \
            --exclude='SNAPSHOTS/' \
            --remove-source-files --bwlimit=30m --timeout=300 \
            $src $dst
        set rc $status
        if test $rc -eq 0
            break
        end
        echo "askar_copy: rsync attempt $attempt failed (exit $rc) — retrying remaining files…" >&2
    end

    if test $rc -ne 0
        echo "askar_copy: rsync never completed (last exit $rc) — not pruning, not shutting down" >&2
        return $rc
    end

    # Drop the cloud-check snapshots (excluded above, so rsync left them behind).
    askar_ps prune_snapshots.ps1

    # --remove-source-files leaves empty dirs behind; prune them on the Gaius itself.
    # (The old `find … -mindepth 1 -type d -empty -delete` never ran: the remote shell
    # is cmd.exe, where `find` is Windows FIND.EXE, and its error went to /dev/null.)
    askar_ps prune_empty_dirs.ps1

    # Same leftover on this side: SNAPSHOTS is excluded from the rsync but its parent
    # Images\<date>\ is not, so every run deposits an empty YYYY-MM-DD dir at the data
    # root. normalize_target_dirs.py deliberately skips bare date dirs — a non-empty
    # one may hold frames from a block that ran outside a target container, and that
    # needs a human — so only the empty ones go here. rmdir is the guard itself: it
    # refuses a non-empty directory, so this cannot eat data even if the match widens.
    # Match the date with `string match -r`, not a `????-??-??` glob: fish dropped `?`
    # as a single-character wildcard in 3.0, so that glob silently matches nothing.
    for stray in $dst/*
        test -d $stray; or continue
        string match -qr '^\d{4}-\d{2}-\d{2}$' -- (basename $stray); or continue
        if command rmdir $stray 2>/dev/null
            echo "askar_copy: removed empty snapshot-date dir "(basename $stray)
        end
    end

    # N.I.N.A names folders after the target as typed into the sequence, so rsync
    # keeps depositing "M 51" / "NGC 7023" next to the normalised "m-51" / "ngc-7023"
    # already on disk. Fold them down before anything else touches the tree: exit 2
    # means "merged, but some paths collided and were left in place" — worth a shout,
    # not worth aborting the night's ingest over.
    $astro_pipeline/tools/normalize_target_dirs.py
    set -l norm $status
    if test $norm -eq 2
        echo "askar_copy: WARNING — target normalisation left conflicts (see above)" >&2
    else if test $norm -ne 0
        echo "askar_copy: WARNING — target normalisation failed (exit $norm)" >&2
    end

    # Flats are shot once per night, from the sequence's End container, so they
    # have no target parent and rsync deposits them in N.I.N.A's raw layout at
    # data/Calibration/FLATS/<night>/. Two steps get them where the Siril pipeline
    # wants them — each night self-contained as <target>/<night>/{LIGHTS,FLATS}:
    #
    #   1. collect_flats.py MOVES data/Calibration/FLATS/<night>/ into the canonical
    #      store calibration/flats/<night>/. The 2026-07-20 reorg relocated the store
    #      out of the data tree but left rsync depositing new nights in the old spot;
    #      without this step link_flats looked in an up-to-date store, never saw the
    #      new night, found no work, and exited 0 — a silent no-FLATS night, not
    #      discovered until someone sat down to stack (sh2-157, 2026-07-20).
    #   2. link_flats.py hardlinks the store's flats into every target that shot
    #      lights that night. XFS: the hardlink costs no extra bytes.
    #
    # Both run after normalisation so the flats land beside the final folder names.
    #
    # Check both exit codes. When the scripts were extracted into their own repo,
    # link_flats resolved its data root as <repo>/tools/Raws and aborted on every
    # run -- and because nothing here looked at $status, the failure was invisible
    # from both ends. A night with no <target>/<night>/FLATS/ simply does not
    # process, and that is not discovered until you sit down to stack.
    $astro_pipeline/tools/collect_flats.py
    set -l collected $status
    if test $collected -ne 0
        echo "askar_copy: WARNING — flat collection failed (exit $collected); the store may be missing this night" >&2
    end

    $astro_pipeline/tools/link_flats.py
    set -l linked $status
    if test $linked -ne 0
        echo "askar_copy: WARNING — flat linking failed (exit $linked); this night's targets have no FLATS" >&2
    end

    if test $shutdown = yes
        echo "askar_copy: shutting the Gaius down…"
        ssh gaius 'shutdown /s /t 0'
    else
        echo "askar_copy: --no-shutdown — leaving the Gaius up."
    end
end

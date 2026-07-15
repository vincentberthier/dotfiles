function askar_shutdown --description "Park the mount, then shut the Gaius down"
    # Never power the Gaius off with the mount unparked: OnStep loses the RA axis
    # position and the next session needs a fresh sync.
    if not askar_park
        echo "askar_shutdown: WARNING — park failed; shutting down anyway" >&2
    end
    ssh gaius 'shutdown /s /t 0'
end

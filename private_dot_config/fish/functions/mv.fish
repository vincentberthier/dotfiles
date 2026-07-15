function mv --wraps mv --description "Move with rsync progress"
    command rsync -ah --info=progress2 --remove-source-files $argv
    # Clean up empty directories left behind by rsync
    for arg in $argv[1..-2]
        if test -d "$arg"
            command find "$arg" -type d -empty -delete 2>/dev/null
        end
    end
end

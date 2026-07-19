function rmv --wraps rsync --description "Remote move with rsync + compression"
    command rsync -azh --info=progress2 --remove-source-files $argv
    or return $status
    for arg in $argv[1..-2]
        if test -d "$arg"
            command find "$arg" -type d -empty -delete 2>/dev/null
        end
    end
end

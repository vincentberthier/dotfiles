function rcp --wraps rsync --description "Remote copy with rsync + compression"
    command rsync -azh --info=progress2 --update $argv
end

function cp --wraps cp --description "Copy with rsync progress (skips newer files on dest)"
    command rsync -ah --info=progress2 --update $argv
end

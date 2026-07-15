function rsync --wraps rsync --description "rsync with archive, compression and progress by default"
    if contains -- --server $argv
        command rsync $argv # remote --server: stay pristine
    else
        command rsync -azv --progress $argv
    end
end

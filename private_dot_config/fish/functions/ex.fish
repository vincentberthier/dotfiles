function ex --description "Extract common archives"
    if [ -f $argv[1] ]
        switch $argv[1]
            case "*.tar.bz2"
                tar -jxf $argv[1]
            case "*.tar.gz"
                tar -zxf $argv[1]
            case "*.tar.xz"
                tar -xf $argv[1]
            case "*.bz2"
                bunzip2 $argv[1]
            case "*.rar"
                unrar -x $argv[1]
            case "*.gz"
                gunzip $argv[1]
            case "*.tar"
                tar -xf $argv[1]
            case "*.tbz2"
                tar -jxf $argv[1]
            case "*.tgz"
                tar -zxf $argv[1]
            case "*.zip"
                unzip $argv[1]
            case "*.Z"
                uncompress $argv[1]
            case "*.7z"
                7z -x $argv[1]
            case "*"
                echo "'$argv[1]' cannot be extracted via ex()"
        end
    else
        echo "'$argv[1]' is not a valid file."
    end
end

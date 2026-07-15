function mkcd --wraps mkdir --description "Create a folder and cd into it"
    mkdir -pv $argv[1]
    cd $argv[1]
end

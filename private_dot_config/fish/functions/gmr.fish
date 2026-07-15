function gmr --wraps git --description "Performs an interactive rebase"
    git rebase -i "HEAD~$argv[1]"
end

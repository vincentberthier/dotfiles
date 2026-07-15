function za --wraps zellij --description "Attaches on an existing session or relaunches one"
    set sessions_list (zellij list-sessions)
    switch $sessions_list
        case "*$hostname*"
            zellij attach $hostname
        case "*"
            zellij --layout $HOME/.config/zellij/layouts/default.kdl -s $hostname
    end
end

function dev-workspace --description "Spawn the wezterm dev layout (btop, editor+shell, 2x2 bacon) for the current project"
    # Store current working directory and original tab ID
    set cwd (pwd)
    set project_name (basename $cwd)
    set original_pid %self

    # Start a background job that will close this pane after a delay
    fish -c "sleep 2; kill -9 $original_pid" &

    # Create new tab for btop
    set btop_pane (wezterm cli spawn --cwd $cwd)
    sleep 0.1
    wezterm cli send-text --pane-id $btop_pane "wezterm cli set-tab-title '󱐋'"
    wezterm cli send-text --pane-id $btop_pane --no-paste (printf '\r')
    sleep 0.1
    wezterm cli send-text --pane-id $btop_pane btop
    wezterm cli send-text --pane-id $btop_pane --no-paste (printf '\r')

    # Create new tab for editor/shell
    set editor_pane (wezterm cli spawn --cwd $cwd)
    sleep 0.1
    wezterm cli set-tab-title --pane-id $editor_pane " $project_name"
    wezterm cli send-text --pane-id $editor_pane --no-paste (printf '\r')
    sleep 0.1
    wezterm cli send-text --pane-id $editor_pane hx
    wezterm cli send-text --pane-id $editor_pane --no-paste (printf '\r')

    # Split and add fish shell
    set shell_pane (wezterm cli split-pane --pane-id $editor_pane --cwd $cwd)
    sleep 0.1
    wezterm cli send-text --pane-id $shell_pane fish
    wezterm cli send-text --pane-id $shell_pane --no-paste (printf '\r')

    # Create new tab for bacon commands (2x2 grid)
    set bacon_pane1 (wezterm cli spawn --cwd $cwd)
    sleep 0.1
    wezterm cli set-tab-title --pane-id $bacon_pane1 " Bacon"
    wezterm cli send-text --pane-id $bacon_pane1 --no-paste (printf '\r')
    sleep 0.1
    wezterm cli send-text --pane-id $bacon_pane1 "bacon clippy-all"
    wezterm cli send-text --pane-id $bacon_pane1 --no-paste (printf '\r')

    # Split horizontally to create top-right pane
    set bacon_pane2 (wezterm cli split-pane --pane-id $bacon_pane1 --horizontal --cwd $cwd)
    sleep 0.1
    wezterm cli send-text --pane-id $bacon_pane2 "bacon nextest"
    wezterm cli send-text --pane-id $bacon_pane2 --no-paste (printf '\r')

    # Split first pane vertically to create bottom-left pane
    set bacon_pane3 (wezterm cli split-pane --pane-id $bacon_pane1 --cwd $cwd)
    sleep 0.1
    wezterm cli send-text --pane-id $bacon_pane3 "bacon doctests"
    wezterm cli send-text --pane-id $bacon_pane3 --no-paste (printf '\r')

    # Split second pane vertically to create bottom-right pane
    set bacon_pane4 (wezterm cli split-pane --pane-id $bacon_pane2 --cwd $cwd)
    sleep 0.1
    wezterm cli send-text --pane-id $bacon_pane4 "bacon spellcheck"
    wezterm cli send-text --pane-id $bacon_pane4 --no-paste (printf '\r')

    # Focus on the editor pane (second tab)
    wezterm cli activate-pane --pane-id $editor_pane

    # The background sleep+exit will now close the original pane after 1 second
end

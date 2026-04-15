# Emit OSC 7 on every prompt so wezterm knows the current working directory.
# This lets `SpawnTab` / `SplitPane` / new ssh-domain tabs inherit the cwd
# of the current pane. Harmless outside wezterm — other terminals ignore it.

if set -q WEZTERM_PANE
    function __wezterm_osc7_update --on-variable PWD --description "Emit OSC 7 on cwd change"
        # URL-encode the path (fish string escape handles the spaces/specials)
        printf '\e]7;file://%s%s\e\\' (hostname) (string escape --style=url -- $PWD)
    end

    # Fire once at shell startup so the initial cwd is tracked.
    __wezterm_osc7_update
end

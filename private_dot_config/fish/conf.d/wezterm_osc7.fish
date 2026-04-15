# Emit OSC 7 on every cwd change so wezterm knows where the pane is.
# This lets `SpawnTab` / `SplitPane` / new exec-domain tabs inherit the cwd
# of the current pane.
#
# No WEZTERM_PANE guard: OSC 7 is harmless in non-wezterm terminals (unknown
# OSC sequences are ignored), and we need it active inside ssh sessions too
# so remote-pane cwd tracking works — ssh does not forward WEZTERM_PANE.
#
# The is-interactive guard IS load-bearing: without it, non-interactive
# `fish -c` subshells (ssh's ProxyCommand chain ends up in one) would
# prepend the escape to the subshell's stdout and corrupt readers.

if status --is-interactive
    function __wezterm_osc7_update --on-variable PWD --description "Emit OSC 7 on cwd change"
        printf '\e]7;file://%s%s\e\\' (hostname) (string escape --style=url -- $PWD)
    end

    __wezterm_osc7_update
end

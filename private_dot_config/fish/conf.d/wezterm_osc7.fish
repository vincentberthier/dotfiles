# Emit OSC 7 on every prompt so wezterm knows the current working directory.
# This lets `SpawnTab` / `SplitPane` / new ssh-domain tabs inherit the cwd
# of the current pane.
#
# The is-interactive guard is load-bearing: without it, non-interactive
# `fish -c` subshells (including anything that ends up invoking fish as a
# subshell in a pipeline — e.g. ssh's ProxyCommand chain) would prepend the
# escape sequence to the subshell's stdout and corrupt whatever reads it.

if status --is-interactive; and set -q WEZTERM_PANE
    function __wezterm_osc7_update --on-variable PWD --description "Emit OSC 7 on cwd change"
        printf '\e]7;file://%s%s\e\\' (hostname) (string escape --style=url -- $PWD)
    end

    __wezterm_osc7_update
end

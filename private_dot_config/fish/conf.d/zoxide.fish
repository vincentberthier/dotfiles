# Initialize zoxide in ALL fish shells (interactive and non-interactive).
#
# This used to live inside config.fish's `status is-interactive` block,
# which meant `fish -c "..."` invocations (e.g. `ssh host 'cmd'`) never
# defined zoxide's `z` wrapper. Combined with the alias cd='z' in
# alias.fish, that fell through to the old jethrokuan/z plugin — now
# uninstalled — which had divergent versions across machines and
# recursed through the cd alias.
#
# Keep zoxide init here (conf.d is always sourced) so `z` is defined
# for every shell shape.

if command -q zoxide
    zoxide init fish | source
end

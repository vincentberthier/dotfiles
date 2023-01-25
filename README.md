See https://www.chezmoi.io on how to use.
```console
$ sh -c "$(curl -fsLS get.chezmoi.io)" -- init --apply VincentBerthier
```

To get the bindkeys on zsh:
```console
# ZSH
$ bindkey -l # gives the list of maps
$ bindkey -M <keymap> # gives the current keybinds for the given map
# Tmux
$ tmux list-keys
```

For neovim, use *:nmap*, *:vmap* and *:imap* for the n/v/i modes (*:help map* for more).

For chatsheets:

- Neovim: viemu.com/vi-vim-cheat.gif
- Tmux: tmuxcheatsheet.com
- Zsh: devhints.io/zsh


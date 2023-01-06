# Setup fzf
# ---------
if [[ ! "$PATH" == *$XDG_CONFIG_HOME/zsh/plugins/fzf/bin* ]]; then
  PATH="${PATH:+${PATH}:}$XDG_CONFIG_HOME/zsh/plugins/fzf/bin"
fi

# Auto-completion
# ---------------
[[ $- == *i* ]] && source "$XDG_CONFIG_HOME/zsh/plugins/fzf/shell/completion.zsh" 2> /dev/null

# Key bindings
# ------------
source "$XDG_CONFIG_HOME/zsh/plugins/fzf/shell/key-bindings.zsh"


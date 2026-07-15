### Files and directories
#
# The rsync-backed cp/mv/rcp/rmv live in functions/, not here.

# ls, via eza
alias ls="eza --classify --icons"
alias la="ls --all"
alias ll="ls --header --long --binary --git"
alias le="ll --sort=mod"
alias lll="ll --group --created --modified --accessed --total-size"
alias lla="ll --all"
alias lst="eza --long --tree --level=2"

# Safety rails
alias ln="ln -i"
alias rm="rm -I --preserve-root"
alias rms="shred -uz" # Shred (remove + overwrite) files

# Don’t mess with /
alias chown="chown --preserve-root"
alias chmod="chmod --preserve-root"
alias chgrp="chgrp --preserve-root"

alias mkdir="mkdir -pv"
alias cat="bat"
alias less="cat"

# Easier to read disk usage
alias df="duf" # human-readable sizes
alias du="dust"

# Colour on grep, even though I’m using rg
alias grep="grep --color=auto"
alias egrep="egrep --color=auto"
alias fgrep="fgrep --color=auto"

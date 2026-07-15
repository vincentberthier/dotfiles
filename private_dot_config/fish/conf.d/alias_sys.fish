### System / processes

alias htop="btop"
alias top="htop"
alias free="free -m" # show sizes in MB
alias meminfo="free -m -l -t"

# Top processes by memory
alias psmem="ps auxf | sort -nr -k 4"
alias psmem10="ps auxf | sort -nr -k 4 | head -10"

# Top processes by CPU
alias pscpu="ps auxf | sort -nr -k 3"
alias pscpu10="ps auxf | sort -nr -k 3 | head -10"

alias cpuinfo="lscpu"

# Packages
alias pkgsize="expac -H M '%m\t%n' | sort -h | nl"

alias docker="podman"

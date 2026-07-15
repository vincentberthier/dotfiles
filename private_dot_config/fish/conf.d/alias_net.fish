### Network

alias ping="ping -c 5"
alias wget="wget -c" # Resume wget by default
alias scp="command rsync -azv --progress"

alias ports="doas lsof -i -P -n | grep LISTEN"
alias myip="curl ifconfig.me"
alias ipinfo="curl ipinfo.io"
alias pubip="dig +short myip.opendns.com @resolver1.opendns.com"

# Hephaistos
alias hssh="ssh hephaistos"
alias hst="hephaistos-status"
alias hon="hephaistos-up"
alias hoff="hephaistos-off"
alias hmnt="mount-hephaistos"
alias humnt="umount-hephaistos"
alias hstream="stream-hephaistos"

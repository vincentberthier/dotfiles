# Default applications
set -Ux EDITOR "nvim"
set -Ux TERMINAL "foot"
set -Ux BROWSER "firefox"
set -Ux SHELL "fish"

# XDG config paths
set -Ux XDG_CONFIG_HOME "$HOME/.config"
set -Ux XDG_CACHE_HOME "$HOME/.cache"
set -Ux XDG_DATA_HOME "$HOME/.local/share"

# Locales
set -Ux LC_ALL "fr_FR.UTF-8"

# Add some folders into the path
fish_add_path $HOME/bin
fish_add_path $HOME/.local/bin

if [ -f "$HOME/.cargo/env" ]
    fish_add_path "$HOME/cargo/env"
end

# SSH Agent
if status is-login
    and status is-interactive
    set -Ua SSH_KEYS_TO_AUTOLOAD $HOME/.ssh/default
    keychain --eval $SSH_KEYS_TO_AUTOLOAD | source
end

# For when keys break
function archlinux-fix-keys
    doas pacman-key --init 
    doas pacman-key --populate archlinux
    doas pacman-key --refresh-keys
end

# Colorisze ls
alias ls="colorls --gs --sd --dark"

# Miscellaneous
alias diff='colordiff'

function compdb --description "Builds compilation guide from build2"
    b -vn clean update 2>&1 | compiledb
end

alias yay='paru'
alias pacman='paru'
function maj --description "Updates the system"
    paru -Syu --noconfirm
    paru -Sc --noconfirm
    rustup update
end
alias calc="qcalc"
alias snx_start='doas modprobe tun && doas snx'
alias regen_initramfs='doas mkinitcpio --config /etc/mkinitcpio.conf --generate /boot/initramfs-custom.img --kernel $(\ls /usr/lib/modules/)'
alias htop='btop'

# Cassandra
alias cassandra_start='doas systemctl start cassandra'
alias cassandra_status='doas systemctl status cassandra'
alias cassandra_stop='doas systemctl stop cassandra'

# Postgress
alias pg='doas -u postgres'


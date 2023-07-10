alias nvimrc='nvim ~/.config/nvim'

# Don’t use vim but nvim
alias vi="nvim"
alias vim="nvim"
alias svi="doas vi"
alias vdev='nvim --cmd "set rtp+=./" .'

# Colorize grep output (good for log files)
alias grep='grep --color=auto'
alias egrep='egrep --color=auto'
alias fgrep='fgrep --color=auto'

# Find
function find --wraps find --description "Don't output errors"
    find $argv -print 2> /dev/null
end

function ff --wraps find --description "Look into 1, for files with extension 2, matching 3"
    set root $1; shift
    set extension $1; shift
    set pattern "$1"; shift
    echo -e "Looking for $pattern in $root with extension $extension"
    find $root -name "*.$extension" $argv -exec grep --color="auto" -Hn $pattern {} \;
end

# confirm before overwriting something
alias cp="cp -i"
alias mv='mv -i'
alias ln='ln -i'
alias rm='rm -I --preserve-root'

# Don’t mess with /
alias chown='chown --preserve-root'
alias chmod='chmod --preserve-root'
alias chgrp='chgrp --preserve-root'

# easier to read disk
alias df='df -h'     # human-readable sizes
alias free='free -m' # show sizes in MB

# Generic useful aliases
alias mkdir='mkdir -pv'
alias cat='bat'
alias less='cat'
alias lls='lsd -lh --total-size'
alias ll='ls -l'
alias la='ls -A'
alias le='ls -l -t -r'
alias lst='ls --tree=3'
alias rms='shred -uz' # Shred (remove + overwrite) files
alias ping='ping -c 5'
alias rsync='rsync -azv --progress'
alias scp="rsync"
alias wget='wget -c' # Resume wget by default
alias df='df -H'
alias du='du -ch'
alias top='htop'
alias cpv='rsync -ah --info=progress2'  # copy with a progress bar
alias c='clear'
alias gdb='gdb --ex run --args'
alias weather='clear && curl wttr.in'
alias t='tail -f'
function mkcd --wraps mkdir --description "Create a folder and cd into it"
    mkdir -pv $1
    cd $1
end

function cut_wallpaper --description "cuts an image into regular 1920x1080 pieces"
    set filename (path basename $1)
    set extension (path extension $filename)
    set filename (string split -r -m1 . $filename)[1]
    mkdir -p {$HOME}/Images/Wallpapers
    convert -crop 1920x1080 $1 {$HOME}/Images/Wallpapers/{$filename}-%d.{$extension}
end

# Extract archives
function ex --description "Extract common archives"
    if [ -f $1 ]
        switch $1
            case "*.tar.bz2" 
                tar -jxf   $1
            case "*.tar.gz"  
                tar -zxf   $1
            case "*.tar.xz"  
                tar -xf   $1
            case "*.bz2"     
                bunzip2    $1
            case "*.rar"     
                unrar -x   $1
            case "*.gz"      
                gunzip     $1
            case "*.tar"     
                tar -xf    $1
            case "*.tbz2"    
                tar -jxf   $1
            case "*.tgz"     
                tar -zxf   $1
            case "*.zip"     
                unzip      $1
            case "*.Z"       
                uncompress $1
            case "*.7z"      
                7z -x      $1
            case "*"         
                echo "'$1' cannot be extracted via ex()"
        end
    else
        echo "'$1' is not a valid file."
    end
end

# Improve cd with zoxide
#alias cd='z'
#alias cd..='z ..'
alias ..='z ../'
alias ...='z ../../..'
alias ....='z ../../../..'

# Change terminal language
alias set_en='export LC_ALL=en_GB.UTF-8'
alias set_fr='export LC_ALL=fr_FR.UTF-8'

# Reboot / halt / poweroff
alias reboot='doas /sbin/reboot'
alias poweroff='doas /sbin/poweroff'
alias halt='doas /sbin/halt'
alias shutdown='doas /sbin/shutdown'

## pass options to free ##
alias meminfo='free -m -l -t'

## get top process eating memory
alias psmem='ps auxf | sort -nr -k 4'
alias psmem10='ps auxf | sort -nr -k 4 | head -10'

## get top process eating cpu ##
alias pscpu='ps auxf | sort -nr -k 3'
alias pscpu10='ps auxf | sort -nr -k 3 | head -10'

## Get server cpu info ##
alias cpuinfo='lscpu'

## older system use /proc/cpuinfo ##
##alias cpuinfo='less /proc/cpuinfo' ##
## get GPU ram on desktop / laptop##
# alias gpumeminfo='grep -i --color memory /var/log/Xorg.0.log'

# Git
alias gac='git add . && git commit -a -m '

# Chezmoi
alias cme='chezmoi edit'
alias cmu='chezmoi update'
alias cmd='chezmoi diff'
alias cma='chezmoi apply'
alias cmA='chezmoi add'
alias cmAC='chezmoi add --encrypt'

# Tmux
alias t='tmux'
alias ta='t a -t'
alias tn='t new -s'
alias tls='t ls'

# Kitty custom
if [ "$TERM" = "xterm-kitty" ]
    alias ssh='kitty +kitten ssh'
    alias si='kitty +kitten icat'
end

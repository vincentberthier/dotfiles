### Abbreviations
# Git
abbr --add gac git commit -a
abbr --add ga git add
abbr --add gca git commit --amend
abbr --add gcb git checkout -b
abbr --add gc git commit
abbr --add gco git checkout
abbr --add gd git diff --word-diff
abbr --add gpf git push --force-with-lease
abbr --add grd git rebase --committer-date-is-author-date --root
abbr --add grh "git reset --hard HEAD^"
abbr --add gri git rebase -i
abbr --add gs git status

# jujutsu
abbr --add jja jj abandon
abbr --add jjbc jj bookmark create -r
abbr --add jjb jj bookmark set -r
abbr --add jjd jj desc -m
abbr --add jje jj edit
abbr --add jjf jj git fetch
abbr --add jjn jj new
abbr --add jjp jj git push
abbr --add jjr jj rebase
abbr --add jjs jj squash
abbr --add jjt jj tug

# chezmoi
abbr --add cme chezmoi edit --apply
abbr --add cmu chezmoi update
abbr --add cma chezmoi apply
abbr --add cz chezmoi
abbr --add ccd 'cd (chezmoi source-path)'
abbr --add cls 'chezmoi managed'
abbr --add cdiff chezmoi diff

# Cargo / rust
abbr --add cb cargo build
abbr --add cbr cargo build --release
abbr --add cr cargo run
abbr --add crr cargo run --release
abbr --add ct cargo nextest run
abbr --add ccl cargo clippy
abbr --add cfmt cargo fmt
abbr --add cdoc cargo doc --open
abbr --add cclean cargo clean
abbr --add cbench cargo bench
abbr --add cwatch 'cargo watch -x check'
abbr --add cbsize 'cargo build --release && du -h target/release/* | sort -h'
abbr --add cinit 'cargo init --vcs=none'
abbr --add cadd cargo add
abbr --add crm cargo rm
abbr --add cup cargo update
abbr --add rshow 'rustup show'
abbr --add rupdate 'rustup update && rustup show'
abbr --add cwbuild 'cargo build --workspace'
abbr --add cwtest 'cargo test --workspace'
abbr --add caudit 'cargo audit'
abbr --add cbloat 'cargo bloat --release --crates'
abbr --add cnx 'cargo nextest run'

# Lint + Format all at once
function ccheck
    cargo fmt --all
    cargo clippy --all-targets --all-features -- -D warnings
end

# Hyprland
abbr --add hc hyprctl clients
abbr --add hr hyprctl reload
abbr --add hw hyprctl workspaces
abbr --add hd hyprctl dispatch

# Standard aliases
# cd stuff
alias cd='z'
alias ..="cd .."
alias ...="cd ../.."
alias ....="cd ../../.."
alias czf="cd (zoxide query -l | fzf)" # Fuzzy jump with zoxide + fzf
alias cls="clear; ls"

# Colour on grep, even though I’m using rg
alias grep="grep --color=auto"
alias egrep="egrep --color=auto"
alias fgrep="fgrep --color=auto"

# confirm before overwriting something
alias cp="cp -i"
alias mv="mv -i"
alias ln="ln -i"
alias rm="rm -I --preserve-root"

# Don’t mess with /
alias chown="chown --preserve-root"
alias chmod="chmod --preserve-root"
alias chgrp="chgrp --preserve-root"

# ls
alias ls="eza --classify --icons"
alias la="ls --all"
alias ll="ls --header --long --binary --git"
alias le="ll --sort=mod"
alias lll="ll --group --created --modified --accessed"
alias lla="ll --all"
alias lst="eza --long --tree --level=2"

# easier to read disk
alias df="duf" # human-readable sizes
alias du="dust"
alias free="free -m" # show sizes in MB

# Generic useful aliases
alias z="zoxide"
alias mkdir="mkdir -pv"
alias cat="bat"
alias less="cat"
alias rms="shred -uz" # Shred (remove + overwrite) files
alias ping="ping -c 5"
alias rsync="rsync -azv --progress"
alias scp="rsync"
alias wget="wget -c" # Resume wget by default
alias top="htop"
alias cpv="rsync -ah --info=progress2" # copy with a progress bar
alias c="clear"
alias weather="clear && curl wttr.in/nice"
alias t="tail -f"
alias htop="btop"

## pass options to free ##
alias meminfo="free -m -l -t"

## get top process eating memory
alias psmem="ps auxf | sort -nr -k 4"
alias psmem10="ps auxf | sort -nr -k 4 | head -10"

## get top process eating cpu ##
alias pscpu="ps auxf | sort -nr -k 3"
alias pscpu10="ps auxf | sort -nr -k 3 | head -10"

## Get server cpu info ##
alias cpuinfo="lscpu"

# Set local config even when using helix with doas
alias hx="helix"
alias editf="hx (fzf)"

# Don’t use vim but nvim
alias svi="doas nvim"
alias vdev='nvim --cmd "set rtp+=./" .'

# Web stuff
alias ports="doas lsof -i -P -n | grep LISTEN"
alias myip="curl ifconfig.me"
alias ipinfo="curl ipinfo.io"
alias pubip="dig +short myip.opendns.com @resolver1.opendns.com"

# Packages
alias pkgsize="expac -H M '%m\t%n' | sort -h | nl"

# Change terminal language
alias set_en='export LC_ALL=en_GB.UTF-8'
alias set_fr='export LC_ALL=fr_FR.UTF-8'

# Git
alias gd='git diff'
alias gdt='git difftool'
alias gl='git log'
alias gll='git log -1 HEAD --stat'

# Docker
alias docker="podman"

# Screen record
alias record='wl-screenrec -f "/home/vincent/Vidéos/$(date +%Y-%m-%d-T-%H%M%S).mp4" -g "$(slurp)"'

# Copy RBFocus files
alias astro_copy="cpv RBFocus@192.168.1.2:/cygdrive/c/Users/RBFocus/Documents/N.I.N.A/Images/ /run/media/vincent/Corrbolg/Astro/Raws/"

function shx --wraps helix --description "Execute helix as root with user config"
    doas helix --config $XDG_CONFIG_HOME/helix/config.toml $argv
end

function gmr --wraps git --description "Performs an interactive rebase"
    git rebase -i "HEAD~$argv[1]"
end
function gcb --wraps git --description "Creates and checkout a new branch"
    git checkout -b $argv[1]
end

# Zellij
function za --wraps zellij --description "Attaches on an existing session or relaunches one"
    set sessions_list (zellij list-sessions)
    switch $sessions_list
        case "*$hostname*"
            zellij attach $hostname
        case "*"
            zellij --layout $HOME/.config/zellij/layouts/default.kdl -s $hostname
    end
end

function ff --wraps find --description "Look into 1, for files with extension 2, matching 3"
    set root $argv[1]
    shift
    set extension $argv[1]
    shift
    set pattern "$argv[1]"
    shift
    echo -e "Looking for $pattern in $root with extension $extension"
    fd $argv "*.$extension" $root -x grep --color="auto" -Hn $pattern {} \;
end

function mkcd --wraps mkdir --description "Create a folder and cd into it"
    mkdir -pv $argv[1]
    cd $argv[1]
end

function cut_wallpaper --description "cuts an image into regular 1920x1080 pieces"
    set filename (path basename $argv[1])
    set extension (path extension $filename)
    set filename (string split -r -m1 . $filename)[1]
    mkdir -p {$HOME}/Images/Wallpapers
    convert -crop 1920x1080 $argv[1] {$HOME}/Images/Wallpapers/{$filename}-%d.{$extension}
end

# Switch wifi connection
function switch_wifi --description "Switches to another network. wpa_cli list_networks to get the list"
    wpa_cli select_network $argv[1]
end

# Extract archives
function ex --description "Extract common archives"
    if [ -f $argv[1] ]
        switch $argv[1]
            case "*.tar.bz2"
                tar -jxf $argv[1]
            case "*.tar.gz"
                tar -zxf $argv[1]
            case "*.tar.xz"
                tar -xf $argv[1]
            case "*.bz2"
                bunzip2 $argv[1]
            case "*.rar"
                unrar -x $argv[1]
            case "*.gz"
                gunzip $argv[1]
            case "*.tar"
                tar -xf $argv[1]
            case "*.tbz2"
                tar -jxf $argv[1]
            case "*.tgz"
                tar -zxf $argv[1]
            case "*.zip"
                unzip $argv[1]
            case "*.Z"
                uncompress $argv[1]
            case "*.7z"
                7z -x $argv[1]
            case "*"
                echo "'$argv[1]' cannot be extracted via ex()"
        end
    else
        echo "'$argv[1]' is not a valid file."
    end
end

function maj --description "Update the system and cleanup"
    while ! ping -c1 www.google.fr >/dev/null 2>&1
        sleep 1
    end
    paru -Syu
    paru -Rns
end

function dev-workspace
    # Store current working directory and original tab ID
    set cwd (pwd)
    set project_name (basename $cwd)
    set original_pid %self

    # Start a background job that will close this pane after a delay
    fish -c "sleep 2; kill -9 $original_pid" &

    # Create new tab for btop
    set btop_pane (wezterm cli spawn --cwd $cwd)
    sleep 0.1
    wezterm cli send-text --pane-id $btop_pane "wezterm cli set-tab-title '󱐋'"
    wezterm cli send-text --pane-id $btop_pane --no-paste (printf '\r')
    sleep 0.1
    wezterm cli send-text --pane-id $btop_pane btop
    wezterm cli send-text --pane-id $btop_pane --no-paste (printf '\r')

    # Create new tab for editor/shell
    set editor_pane (wezterm cli spawn --cwd $cwd)
    sleep 0.1
    wezterm cli set-tab-title --pane-id $editor_pane " $project_name"
    wezterm cli send-text --pane-id $editor_pane --no-paste (printf '\r')
    sleep 0.1
    wezterm cli send-text --pane-id $editor_pane hx
    wezterm cli send-text --pane-id $editor_pane --no-paste (printf '\r')

    # Split and add fish shell
    set shell_pane (wezterm cli split-pane --pane-id $editor_pane --cwd $cwd)
    sleep 0.1
    wezterm cli send-text --pane-id $shell_pane fish
    wezterm cli send-text --pane-id $shell_pane --no-paste (printf '\r')

    # Create new tab for bacon commands (2x2 grid)
    set bacon_pane1 (wezterm cli spawn --cwd $cwd)
    sleep 0.1
    wezterm cli set-tab-title --pane-id $bacon_pane1 " Bacon"
    wezterm cli send-text --pane-id $bacon_pane1 --no-paste (printf '\r')
    sleep 0.1
    wezterm cli send-text --pane-id $bacon_pane1 "bacon clippy-all"
    wezterm cli send-text --pane-id $bacon_pane1 --no-paste (printf '\r')

    # Split horizontally to create top-right pane
    set bacon_pane2 (wezterm cli split-pane --pane-id $bacon_pane1 --horizontal --cwd $cwd)
    sleep 0.1
    wezterm cli send-text --pane-id $bacon_pane2 "bacon nextest"
    wezterm cli send-text --pane-id $bacon_pane2 --no-paste (printf '\r')

    # Split first pane vertically to create bottom-left pane
    set bacon_pane3 (wezterm cli split-pane --pane-id $bacon_pane1 --cwd $cwd)
    sleep 0.1
    wezterm cli send-text --pane-id $bacon_pane3 "bacon doctests"
    wezterm cli send-text --pane-id $bacon_pane3 --no-paste (printf '\r')

    # Split second pane vertically to create bottom-right pane
    set bacon_pane4 (wezterm cli split-pane --pane-id $bacon_pane2 --cwd $cwd)
    sleep 0.1
    wezterm cli send-text --pane-id $bacon_pane4 "bacon spellcheck"
    wezterm cli send-text --pane-id $bacon_pane4 --no-paste (printf '\r')

    # Focus on the editor pane (second tab)
    wezterm cli activate-pane --pane-id $editor_pane

    # The background sleep+exit will now close the original pane after 1 second
end

# function grp --description "Merges origin/dev or a given branch into the current branch then pushes everything"
#     if count $argv >/dev/null
#         set branch $argv
#     else
#         set branch origin/dev
#     end
#     git pull
#     git rebase --committer-date-is-author-date $branch
#     git push --force-with-lease
# end

# function cwt --description "Run cargo watch tests"
#     argparse --name=cwt h/help v/verbose -- $argv
#     if set -q _flag_help
#         echo "cwt [-h|--help] [-v|--verbose] [tests]"
#         exit 0
#     end

#     if set -q _flag_verbose
#         set -x RUST_LOG "info,bangk_data=trace,bangk_rpc=trace,bangk_dashboard=trace"
#     end

#     set -l nargs (count $argv)
#     if test (echo (hostname)) = athena
#         if test $nargs -eq 0
#             CARGO_BUILD_JOBS=4 cargo watch -q -c -x "nextest run --all-features --nocapture --build-jobs 4 -E 'not binary_id(bangk-dashboard::app_suite)'"
#         else if test $nargs -eq 1
#             CARGO_BUILD_JOBS=4 cargo watch -q -c -x "nextest run --all-features --nocapture --build-jobs 4 -E '$argv[1] and not binary_id(bangk-dashboard::app_suite)'"
#         else
#             echo "one argument max"
#             exit 1
#         end
#     else
#         if test $nargs -eq 0
#             cargo watch -q -c -x "nextest run --all-features --nocapture -E 'not binary_id(bangk-dashboard::app_suite)'"
#         else if test $nargs -eq 1
#             cargo watch -q -c -x "nextest run --all-features --no-capture -E '$argv[1] and not binary_id(bangk-dashboard::app_suite)'"
#         else
#             echo "one argument max"
#             exit 1
#         end

#     end
# end

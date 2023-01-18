#!/bin/bash

iscmd() {
    command -v >&- "$@"
}

if [ ! -d ~/tmp ]; then
    mkdir -p ~/tmp
    delete_tmp=true
else
    delete_tmp=false
fi
export TMPDIR=~/tmp/

# If zsh is not installed, do it
iscmd "zsh" || {
    echo "Installing ZSH"
    cd ~/tmp
    rm -f zsh*.tar.xz
    wget https://www.zsh.org/pub/zsh-{5..9}.{0..9}.tar.xz 2> /dev/null
    mkdir -p zsh && unxz zsh-*.tar.xz && tar -xvf zsh-*.tar -C zsh --strip-components 1
    cd zsh

    ./configure --prefix=$HOME/.local
    make -j
    make install
}

export XDG_CONFIG_HOME=$HOME/.config
export XDG_CACHE_HOME=$HOME/.cache
export XDG_DATA_HOME=$HOME/.local/share

# Install fonts
update_font=false
mkdir -p $XDG_DATA_HOME/fonts/nerd-fonts/
cd $XDG_DATA_HOME/fonts/nerd-fonts/
if [ ! -f "Hack Bold Italic Nerd Font Complete.ttf" ]; then
    echo "Downloading Hack Bold Italic"
    update_font=true
    curl --silent https://raw.githubusercontent.com/ryanoasis/nerd-fonts/master/patched-fonts/Hack/BoldItalic/complete/Hack%20Bold%20Italic%20Nerd%20Font%20Complete.ttf -o 'Hack Bold Italic Nerd Font Complete.ttf'
fi
if [ ! -f "Hack Bold Nerd Font Complete.ttf" ]; then
    echo "Downloading Hack Bold"
    update_font=true
    curl --silent https://raw.githubusercontent.com/ryanoasis/nerd-fonts/master/patched-fonts/Hack/Bold/complete/Hack%20Bold%20Nerd%20Font%20Complete.ttf -o 'Hack Bold Nerd Font Complete.ttf'
fi
if [ ! -f "Hack Italic Nerd Font Complete.ttf" ]; then
    echo "Downloading Hack Italic"
    update_font=true
    curl --silent https://raw.githubusercontent.com/ryanoasis/nerd-fonts/master/patched-fonts/Hack/Italic/complete/Hack%20Italic%20Nerd%20Font%20Complete.ttf -o 'Hack Italic Nerd Font Complete.ttf'
fi
if [ ! -f "Hack Regular Nerd Font Complete.ttf" ]; then
    echo "Downloading Hack Regular"
    update_font=true
    curl --silent https://raw.githubusercontent.com/ryanoasis/nerd-fonts/master/patched-fonts/Hack/Regular/complete/Hack%20Regular%20Nerd%20Font%20Complete.ttf -o 'Hack Regular Nerd Font Complete.ttf'
fi
cd $HOME

if $update_font; then
    echo "Updating font cache"
    fc-cache -vf > /dev/null
fi

# Install zoxide
iscmd "zoxide" || {
    echo "Installing zoxide"
    mkdir -p $XDG_CONFIG_HOME/zsh/plugins/
    curl -sS https://raw.githubusercontent.com/ajeetdsouza/zoxide/main/install.sh | bash
}
if [ ! -d "$XDG_CONFIG_HOME/zsh/plugins/fzf" ]; then
    echo "Installing fzf"
    git clone --depth 1 https://github.com/junegunn/fzf.git $XDG_CONFIG_HOME/zsh/plugins/fzf
    $XDG_CONFIG_HOME/zsh/plugins/fzf/install
    mv ~/.fzf.zsh $XDG_CONFIG_HOME/zsh/fzf.zsh
fi

# Install neovim
iscmd "nvim" || {
    cd ~/tmp
    echo "Installing neovim"
    git clone https://github.com/neovim/neovim
    cd neovim && make CMAKE_BUILD_TYPE=RelWithDebInfo CMAKE_INSTALL_PREFX=~/.local/
    make install
}

if [ ! -d "$XDG_DATA_HOME/zsh/plugings/zsh-history-substring-search" ]; then
    mkdir -p "$XDG_DATA_HOME/zsh/plugings/zsh-history-substring-search"
    git clone https://github.com/zsh-users/zsh-history-substring-search "$XDG_DATA_HOME/zsh/plugings/zsh-history-substring-search"
fi

cd ~
if $delete_tmp; then
    rm -rf ~/tmp
else
    rm -rf ~/tmp/zsh*
    rm -rf ~/tmp/neovim
fi


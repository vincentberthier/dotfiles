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

iscmd hostname || {
    hostname() {
        uname -n
    }
}

if [[ $(hostname) != "visu01.sis.cnes.fr" ]]; then
    iscmd "kitty" || {
        echo "Installing kitty"
        cd ~/tmp
        curl -L https://sw.kovidgoyal.net/kitty/installer.sh | sh /dev/stdin
        ln -s ~/.local/kitty.app/bin/kitty ~/.local/bin
        cp ~/.local/kitty.app/share/applications/kitty.desktop ~/.local/share/applications
    }
fi

# If zsh is not installed, do it
iscmd "zsh" || {
    echo "Installing ZSH"
    cd ~/tmp
    rm -f zsh*.tar.xz
    wget https://www.zsh.org/pub/zsh-{5..9}.{0..9}.tar.xz 2> /dev/null
    mkdir -p zsh && unxz zsh-*.tar.xz && tar -xvf zsh-*.tar -C zsh --strip-components 1
    cd zsh

    ./configure --prefix="$HOME"/.local
    make -j
    make install
    cd "$HOME"
}

iscmd "tmux" || {
    echo "Installing tmux"
    cd ~/tmp/
    rm -rf tmux* libevent*
    wget https://github.com/libevent/libevent/releases/download/release-2.1.12-stable/libevent-2.1.12-stable.tar.gz 2> /dev/null
    tar -zxf libevent*.tar.gz && rm libevent*.tar.gz && cd libevent-*
    ./configure --prefix="$HOME"/.local --enable-shared
    make -j 8 && make -j 8 install
    cd ..

    wget https://github.com/tmux/tmux/releases/download/3.3a/tmux-3.3a.tar.gz 2> /dev/null
    tar -zxf tmux*.tar.gz && rm tmux*.tar.gz && mv tmux* tmux && cd tmux
    ./configure --prefix="$HOME"/.local CFLAGS="-I${HOME}/.local/include" LDFLAGS="-L${HOME}/.local/lib"
    make -j 8 && make -j 8 install

    git clone https://github.com/tmux-plugins/tpm "$HOME"/.tmux/plugins/tpm
    cd "$HOME"
}

# iscmd "lsd" || {
#     echo "Installing LSD"
#     cd ~/tmp/
#     rm -rf lsd-*
#     wget  https://github.com/Peltoche/lsd/releases/download/0.23.1/lsd-0.23.1-x86_64-unknown-linux-gnu.tar.gz 2> /dev/null
#     tar -xzf lsd*.tar.gz && rm lsd-*.tar.gz && cd lsd*
#     cp lsd ~/.local/bin
#     cd "$HOME"
# }

iscmd "colorls" || {
    echo "Installing colorls"
    if [[ "$(hostname)" == "visu01" ]]; then module load ruby; fi
    gem install colorls 2> /dev/null
    dir=$(ls -t -1 ~/.local/share/gem/ruby/ | head -n 1)
    ln -s "${HOME}/.local/share/gem/ruby/${dir}/bin/colorls" ~/.local/bin/colorls
}

iscmd "bat" || {
    echo "Installing Bat"
    cd ~/tmp
    rm -rf bat*
    wget https://github.com/sharkdp/bat/releases/download/v0.22.1/bat-v0.22.1-x86_64-unknown-linux-gnu.tar.gz 2> /dev/null
    tar -zxf bat-*tar.gz && rm bat*.tar.gz && cd bat*
    cp bat ~/.local/bin/
    cd "$HOME"
}

export XDG_CONFIG_HOME=$HOME/.config
export XDG_CACHE_HOME=$HOME/.cache
export XDG_DATA_HOME=$HOME/.local/share

# Install fonts
update_font=false
mkdir -p "$XDG_DATA_HOME"/fonts/nerd-fonts/
cd "$XDG_DATA_HOME"/fonts/nerd-fonts/

if [ ! -f "Inconsolata Bold Nerd Font Complete.otf" ]; then
    echo "Downloading Inconsolata"
    update_font=true
    wget https://github.com/ryanoasis/nerd-fonts/releases/download/v2.3.0/Inconsolata.zip 2> /dev/null
    unzip -n Inconsolata.zip
fi

if [ ! -f "Hack Regular Nerd Font Complete.ttf" ]; then
    echo "Downloading Hack"
    update_font=true
    wget https://github.com/ryanoasis/nerd-fonts/releases/download/v2.3.0/Hack.zip 2> /dev/null
    unzip -n Hack.zip
fi

if [ ! -f "Code New Roman Nerd Font Complete.otf" ]; then
    echo "Downloading Code New Roman"
    update_font=true
    wget https://github.com/ryanoasis/nerd-fonts/releases/download/v2.3.0/CodeNewRoman.zip 2> /dev/null
    unzip -n CodeNewRoman.zip
fi

cd "$HOME"

if "$update_font"; then
    echo "Updating font cache"
    fc-cache -vf > /dev/null
fi

# Install zoxide
iscmd "zoxide" || {
    echo "Installing zoxide"
    mkdir -p "$XDG_CONFIG_HOME"/zsh/plugins/
    curl -sS https://raw.githubusercontent.com/ajeetdsouza/zoxide/main/install.sh | bash
}
if [ ! -d "$XDG_CONFIG_HOME/zsh/plugins/fzf" ]; then
    echo "Installing fzf"
    git clone --depth 1 https://github.com/junegunn/fzf.git "$XDG_CONFIG_HOME"/zsh/plugins/fzf
    "$XDG_CONFIG_HOME"/zsh/plugins/fzf/install
    mv ~/.fzf.zsh "$XDG_CONFIG_HOME"/zsh/fzf.zsh
fi

# Install neovim
iscmd "nvim" || {
    cd ~/tmp
    echo "Installing neovim"
    git clone https://github.com/neovim/neovim
    cd neovim && make CMAKE_BUILD_TYPE=RelWithDebInfo CMAKE_INSTALL_PREFX="$HOME"/.local/
    make install
    cd "$HOME"
}

# install xclip
iscmd "xsel" || {
    cd ~/tmp
    echo "Installing xsel"
    
    git clone https://github.com/kfish/xsel.git && cd xsel
    ./autogen.sh && ./configure --prefix="$HOME"/.local
    make -j 8 && make -j 8 install
    cd "$HOME"
}
    

cd "$HOME"
if "$delete_tmp"; then
    rm -rf "$HOME"/tmp
else
    rm -rf "$HOME"/tmp/zsh*
    rm -rf "$HOME"/tmp/neovim
fi

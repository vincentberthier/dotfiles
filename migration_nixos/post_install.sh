#!/usr/bin/env bash
set -euo pipefail

# Post-Installation Package Setup for Vincent's Arch Migration
# Run this script after the base installation as your user

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

print_status() { echo -e "${BLUE}[INFO]${NC} $1"; }
print_success() { echo -e "${GREEN}[SUCCESS]${NC} $1"; }
print_warning() { echo -e "${YELLOW}[WARNING]${NC} $1"; }
print_error() { echo -e "${RED}[ERROR]${NC} $1"; }

# Package arrays organized by priority
declare -a PRIORITY_1=(
    # Essential system and development
    "pipewire" "pipewire-alsa" "pipewire-pulse" "pipewire-jack" "wireplumber"
    "mesa" "lib32-mesa" "vulkan-radeon" "lib32-vulkan-radeon" "xf86-video-amdgpu"

    # Desktop environments
    "hyprland" "waybar" "hyprpaper" "hypridle" "hyprlock" "wofi" "mako"
    "xdg-desktop-portal" "xdg-desktop-portal-hyprland"
    "wl-clipboard" "grim" "slurp" 

    # Plasma desktop (fallback)
    "plasma-meta" "kde-applications-meta"
    "xdg-desktop-portal-kde"
    
    # Essential CLI tools
    "starship" "eza" "bat" "fd" "ripgrep" "sd" "dust" "duf" "btop" "zoxide" "fzf"
    "git" "lazygit" "difftastic" "meld"  "git-delta"
    "tree" "unzip" "wget" "curl" "rsync" "fastfetch" "tldr"
    
    # VPN and work essentials (HIGH PRIORITY)
    "openconnect" "iproute2" "iptables"
    
    # Development core
    "rust" "cargo" "clang" "lldb" "python" "python-pip"
    "typescript-language-server" 
    
    # Security and keys
    "keychain" "gnupg" "pass"
    
    # Terminals
    "wezterm" "kitty" "foot"
    
    # Audio/video
    "playerctl" "pavucontrol"
)

declare -a PRIORITY_2=(
    # Gaming
    "gamemode" "lib32-gamemode" "mangohud" "lib32-mangohud" "radeontop" "corectrl"
    "steam" "lutris" "wine-staging"
    
    # Applications
    "thunderbird" "discord" "signal-desktop" "telegram-desktop" "element-desktop"
    "teams-for-linux"  "libreoffice-fresh" "obsidian" "qbittorrent"
    "mpv" "vlc" "gimp"
    
    # Python scientific stack
    "python-numpy" "python-matplotlib" "python-pandas" "python-seaborn"
    "python-scikit-image" "python-opencv" "python-pillow" "python-requests"
    "ipython" "python-black" "python-isort" "python-flake8"
    "python-lsp-server"
    
    # Development tools
    "vscode-langservers-extracted" "eslint"  "prettier"
)

declare -a AUR_PRIORITY_1=(
    # Essential AUR packages
    "dprint"                # formatter
    "jujutsu-git"           # Your primary VCS
    "zen-browser-bin"       # Your primary browser
    "spotify"               # Daily use
    "paru"                  # AUR helper (install first)
    "wl-screenrec"          # screen record for Wayland
    "watchman-bin"          # inotify-like
    "webcord"               # Discord alternative
    "ltex-ls-bin"           # LS for LaTeX
)

declare -a AUR_PRIORITY_2=(
    # Secondary AUR packages
    "duplicacy"            # Backup tool
    "zellij"               # Terminal multiplexer
    "postman-bin"          # Development
    "teams-for-linux-bin"  # Work communication
)

declare -a PYTHON_PACKAGES=(
    "astropy" "astroquery" "sirilpy" "ipython"
)

install_paru() {
    if command -v paru &> /dev/null; then
        print_success "paru already installed"
        return
    fi
    
    print_status "Installing paru from pre-compiled binary"
    
    # Download latest paru release
    cd /tmp
    curl -L -o paru.tar.zst $(curl -s https://api.github.com/repos/Morganamilo/paru/releases/latest | grep "browser_download_url.*x86_64.*tar.zst" | cut -d '"' -f 4)
    
    # Extract and install
    tar -xf paru.tar.zst
    doas mv paru /usr/local/bin/
    chmod +x /usr/local/bin/paru
        
    print_success "paru installed"
}

install_fisher() {
    print_status "Installing Fisher (Fish plugin manager)"
    
    # Ensure fish config directory exists
    mkdir -p ~/.config/fish/functions
    
    # Download and install Fisher
    curl -sL https://raw.githubusercontent.com/jorgebucaran/fisher/main/functions/fisher.fish -o ~/.config/fish/functions/fisher.fish
    
    # Make it executable
    chmod +x ~/.config/fish/functions/fisher.fish
    
    print_success "Fisher installed"
}

install_fish_plugins() {
    print_status "Installing Fish plugins"
    
    # Create a fish script to install plugins
    cat > /tmp/install_fish_plugins.fish << 'FISH_SCRIPT_EOF'
#!/usr/bin/env fish

# Install Fisher plugins
fisher install jorgebucaran/autopair.fish
fisher install PatrickF1/fzf.fish
fisher install franciscolourenco/done
fisher install mattgreen/lucid.fish
fisher install jorgebucaran/replay.fish
fisher install gazorby/fish-abbreviation-tips
fisher install jethrokuan/z
FISH_SCRIPT_EOF

    # Run the script with fish
    fish /tmp/install_fish_plugins.fish
    
    # Clean up
    rm /tmp/install_fish_plugins.fish
    
    print_success "Fish plugins installed"
}

update_system() {
    print_status "Updating system packages"
    sudo pacman -Syu --noconfirm
    print_success "System updated"
}

install_priority_packages() {
    local priority=$1
    shift
    local packages=("$@")
    
    print_status "Installing Priority $priority packages (${#packages[@]} packages)"
    
    # Split into chunks to avoid command line length issues
    local chunk_size=20
    for ((i=0; i<${#packages[@]}; i+=chunk_size)); do
        local chunk=("${packages[@]:i:chunk_size}")
        print_status "Installing chunk: ${chunk[*]}"
        
        if ! sudo pacman -S --needed --noconfirm "${chunk[@]}"; then
            print_warning "Some packages in chunk failed to install, continuing..."
        fi
    done
    
    print_success "Priority $priority packages installation completed"
}

install_aur_packages() {
    local priority=$1
    shift
    local packages=("$@")
    
    print_status "Installing Priority $priority AUR packages (${#packages[@]} packages)"
    
    for package in "${packages[@]}"; do
        print_status "Installing $package from AUR"
        if ! paru -S --needed --noconfirm "$package"; then
            print_warning "Failed to install $package, continuing..."
        fi
    done
    
    print_success "Priority $priority AUR packages installation completed"
}

install_python_packages() {
    print_status "Installing Python packages via pip"
    
    # Create virtual environment for scientific packages
    python -m venv ~/.local/share/python-env
    source ~/.local/share/python-env/bin/activate
    
    pip install --upgrade pip
    for package in "${PYTHON_PACKAGES[@]}"; do
        print_status "Installing Python package: $package"
        pip install "$package" || print_warning "Failed to install $package"
    done
    
    deactivate
    print_success "Python packages installed"
}

setup_systemd_services() {
    print_status "Setting up systemd user services"
    
    # Enable user services
    systemctl --user enable pipewire
    systemctl --user enable pipewire-pulse
    systemctl --user enable wireplumber
    
    # Create update timer
    mkdir -p ~/.config/systemd/user
    
    # Daily update service
    cat > ~/.config/systemd/user/daily-update.service << 'EOF'
[Unit]
Description=Daily system update
Wants=network-online.target
After=network-online.target

[Service]
Type=oneshot
ExecStart=/usr/bin/paru -Syu --noconfirm
ExecStart=/usr/bin/flatpak update -y

[Install]
WantedBy=default.target
EOF

    # Daily update timer (5 minutes after boot, then daily)
    cat > ~/.config/systemd/user/daily-update.timer << 'EOF'
[Unit]
Description=Daily system update timer
Requires=daily-update.service

[Timer]
OnBootSec=5min
OnCalendar=daily
Persistent=true

[Install]
WantedBy=timers.target
EOF

    # Enable the timer
    systemctl --user daemon-reload
    systemctl --user enable daily-update.timer
    
    print_success "Systemd services configured"
}

create_vpn_scripts() {
    print_status "Creating VPN scripts for work"
    
    mkdir -p ~/.local/bin
    
    # VPN connect script
    cat > ~/.local/bin/vpn-connect << 'EOF'
#!/usr/bin/env bash
# Work VPN connection script

# Backup current resolv.conf
sudo cp /etc/resolv.conf /etc/resolv.conf.pre-vpn

# Connect to VPN (adjust as needed for your setup)
echo "Connecting to work VPN..."
echo "You may need to configure this script with your specific VPN details"
sudo openconnect --background --protocol=gp YOUR_VPN_SERVER --user=YOUR_USERNAME

# Wait for connection
echo "Waiting for VPN connection..."
sleep 5

# Configure MTU if needed
if ip link show tun0 &>/dev/null; then
    echo "Configuring VPN interface..."
    sudo ip link set dev tun0 mtu 1360
    echo "VPN connected successfully"
else
    echo "VPN connection failed"
    exit 1
fi
EOF

    # VPN disconnect script
    cat > ~/.local/bin/vpn-disconnect << 'EOF'
#!/usr/bin/env bash
# Work VPN disconnect script

echo "Disconnecting VPN..."
sudo pkill -f openconnect

# Restore DNS
if [[ -f /etc/resolv.conf.pre-vpn ]]; then
    sudo cp /etc/resolv.conf.pre-vpn /etc/resolv.conf
fi

# Restart NetworkManager to clean up
sudo systemctl restart NetworkManager

echo "VPN disconnected"
EOF

    chmod +x ~/.local/bin/vpn-*
    
    print_success "VPN scripts created at ~/.local/bin/"
    print_warning "Please edit ~/.local/bin/vpn-connect with your actual VPN details"
}

setup_directories() {
    print_status "Setting up user directories"
    
    # Create standard directories
    mkdir -p ~/Documents ~/Downloads ~/Pictures ~/Videos ~/Music
    mkdir -p ~/code ~/pcloud ~/vault
    mkdir -p ~/.config ~/.local/bin ~/.local/share
    
    # Create directories for your workflow
    mkdir -p ~/.config/{hypr,waybar,wezterm,kitty,helix,fish}
    mkdir -p ~/.local/share/fonts
    
    print_success "Directories created"
}

setup_display_manager() {
    print_status "Setting up display manager"
    
    # Configure SDDM
    doas mkdir -p /etc/sddm.conf.d
    doas tee /etc/sddm.conf.d/wayland.conf << 'SDDM_EOF'
[General]
DisplayServer=wayland-user

[Autologin]
User=vincent
Session=hyprland.desktop

[Wayland]
CompositorCommand=Hyprland
SDDM_EOF
    
    # Enable SDDM now that desktop environments are installed
    doas systemctl enable sddm
    
    print_success "SDDM configured and enabled"
}

main() {
    echo -e "${BLUE}"
    echo "=================================================="
    echo "  Post-Installation Package Setup"
    echo "  Vincent's NixOS to Arch Migration"
    echo "=================================================="
    echo -e "${NC}"
    
    # Check if running as user (not root)
    if [[ $EUID -eq 0 ]]; then
        print_error "Do not run this script as root"
        exit 1
    fi
    
    print_status "Starting package installation process..."
    
    # Phase 1: Essential setup
    setup_directories
    update_system
    install_paru
    
    # Phase 2: Priority 1 packages (work-critical)
    install_priority_packages "1" "${PRIORITY_1[@]}"
    install_aur_packages "1" "${AUR_PRIORITY_1[@]}"

    # Phase 2.5: Set up display manager now that desktop is installed
    setup_display_manager
    
    # Phase 3: Shell setup
    install_fisher
    install_fish_plugins
    
    # Phase 4: System services
    setup_systemd_services
    create_vpn_scripts
    
    # Phase 5: Priority 2 packages (nice-to-have)
    print_status "Installing Priority 2 packages..."
    read -p "Continue with Priority 2 packages? (y/n): " continue_p2
    if [[ "$continue_p2" == "y" ]]; then
        install_priority_packages "2" "${PRIORITY_2[@]}"
        install_aur_packages "2" "${AUR_PRIORITY_2[@]}"
        install_python_packages
    fi
    
    print_success "Package installation completed!"
    echo
    echo -e "${GREEN}Installation Summary:${NC}"
    echo "✓ System packages installed"
    echo "✓ AUR helper (paru) configured"
    echo "✓ Fish shell with plugins configured"
    echo "✓ VPN scripts created (need configuration)"
    echo "✓ Systemd services set up"
    echo "✓ User directories created"
    echo
    echo -e "${YELLOW}Next Steps:${NC}"
    echo "1. Configure VPN scripts with your work details"
    echo "2. Set up chezmoi: chezmoi init --apply"
    echo "3. Install Dank Mono fonts to ~/.local/share/fonts/"
    echo "4. Configure 1Password integration"
    echo "5. Log out and back in to apply all changes"
    echo
    echo -e "${BLUE}Manual tasks remaining:${NC}"
    echo "- Astronomy apps (GraXpert, Siril, StarNet++) - can wait"
    echo "- Wine applications (Sequator) - can wait"
    echo "- Fine-tune Hyprland configuration"
    
    # Offer to reboot
    echo
    read -p "Reboot now to apply all changes? (y/n): " reboot_now
    if [[ "$reboot_now" == "y" ]]; then
        sudo reboot
    fi
}

# Run main function
main "$@"

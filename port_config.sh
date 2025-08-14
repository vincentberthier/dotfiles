#!/usr/bin/env bash
# Simple configuration extraction script - manually copy resolved symlinks
set -euo pipefail

CHEZMOI_SOURCE="$HOME/.local/share/chezmoi"
CONFIG_DIR="$HOME/.config"

echo "Extracting configurations for chezmoi (handling symlinks)..."

# Ensure we're in the chezmoi directory
cd "$CHEZMOI_SOURCE"

# Function to copy file and handle symlinks
copy_config() {
    local src="$1"
    local dest="$2"
    local is_template="${3:-false}"
    
    if [[ -L "$src" ]]; then
        # It's a symlink, resolve it
        local target=$(readlink -f "$src")
        echo "Copying $src -> $target to $dest"
        mkdir -p "$(dirname "$dest")"
        cp "$target" "$dest"
        # Fix permissions (Nix store files are readonly)
        chmod 644 "$dest"
    elif [[ -e "$src" ]]; then
        # Regular file
        echo "Copying $src to $dest"
        mkdir -p "$(dirname "$dest")"
        cp "$src" "$dest"
        # Ensure writable permissions
        chmod 644 "$dest"
    else
        echo "⚠ Not found: $src"
        return 1
    fi
    
    if [[ "$is_template" == "true" && "$dest" != *.tmpl ]]; then
        mv "$dest" "${dest}.tmpl"
        # Ensure template file is writable
        chmod 644 "${dest}.tmpl"
        echo "✓ Marked as template: ${dest}.tmpl"
    else
        echo "✓ Copied: $dest"
    fi
}

# Function to copy directory and handle symlinks
copy_dir() {
    local src="$1"
    local dest="$2"
    
    if [[ -L "$src" ]]; then
        local target=$(readlink -f "$src")
        echo "Copying directory $src -> $target to $dest"
        mkdir -p "$dest"
        cp -r "$target"/* "$dest/" 2>/dev/null || true
        # Fix permissions for all copied files
        find "$dest" -type f -exec chmod 644 {} \;
        find "$dest" -type d -exec chmod 755 {} \;
    elif [[ -d "$src" ]]; then
        echo "Copying directory $src to $dest"
        mkdir -p "$dest"
        cp -r "$src"/* "$dest/" 2>/dev/null || true
        # Fix permissions for all copied files
        find "$dest" -type f -exec chmod 644 {} \;
        find "$dest" -type d -exec chmod 755 {} \;
    else
        echo "⚠ Directory not found: $src"
        return 1
    fi
    echo "✓ Directory copied: $dest"
}

echo "Copying essential configurations..."

# Fish shell configuration
copy_config "$CONFIG_DIR/fish/config.fish" "private_dot_config/fish/config.fish" true
copy_dir "$CONFIG_DIR/fish/functions" "private_dot_config/fish/functions"

# Git configuration (check both locations)
if [[ -f "$CONFIG_DIR/git/config" ]]; then
    copy_config "$CONFIG_DIR/git/config" "private_dot_config/git/config" true
    copy_config "$CONFIG_DIR/git/message" "private_dot_config/git/message"
    copy_config "$CONFIG_DIR/git/allowed_signers" "private_dot_config/git/allowed_signers" true
    echo "✓ Added git config from ~/.config/git/"
else
    copy_config "$HOME/.gitconfig" "dot_gitconfig" true
    echo "✓ Added git config from ~/.gitconfig"
fi

# SSH configuration (if exists)
if [[ -f "$HOME/.ssh/config" ]]; then
    copy_config "$HOME/.ssh/config" "private_dot_ssh/config" true
fi

# Helix editor
copy_dir "$CONFIG_DIR/helix" "private_dot_config/helix"

# Starship
copy_config "$CONFIG_DIR/starship.toml" "private_dot_config/starship.toml"

# Hyprland
copy_config "$CONFIG_DIR/hypr/hyprland.conf" "private_dot_config/hypr/hyprland.conf" true
copy_config "$CONFIG_DIR/hypr/hyprpaper.conf" "private_dot_config/hypr/hyprpaper.conf"
copy_config "$CONFIG_DIR/hypr/hyprlock.conf" "private_dot_config/hypr/hyprlock.conf"
copy_dir "$CONFIG_DIR/hypr/scripts" "private_dot_config/hypr/scripts"

# Waybar
copy_config "$CONFIG_DIR/waybar/config" "private_dot_config/waybar/config" true
copy_config "$CONFIG_DIR/waybar/style.css" "private_dot_config/waybar/style.css"
copy_dir "$CONFIG_DIR/waybar/scripts" "private_dot_config/waybar/scripts"

# Terminals
copy_dir "$CONFIG_DIR/wezterm" "private_dot_config/wezterm"
copy_dir "$CONFIG_DIR/kitty" "private_dot_config/kitty"
copy_config "$CONFIG_DIR/foot/foot.ini" "private_dot_config/foot/foot.ini" true

# Other applications
copy_dir "$CONFIG_DIR/mako" "private_dot_config/mako"
copy_dir "$CONFIG_DIR/wofi" "private_dot_config/wofi"
copy_dir "$CONFIG_DIR/btop" "private_dot_config/btop"
copy_dir "$CONFIG_DIR/yazi" "private_dot_config/yazi"
copy_dir "$CONFIG_DIR/zellij" "private_dot_config/zellij"

# Development tools
copy_config "$CONFIG_DIR/jj/config.toml" "private_dot_config/jj/config.toml" true

# Dotfiles
copy_config "$HOME/.clang-format" "dot_clang-format"
copy_config "$HOME/.gdbinit" "dot_gdbinit"

echo ""
echo "Manual configuration extraction complete!"
echo ""
echo "Files copied to: $CHEZMOI_SOURCE"
echo ""
echo "Next steps:"
echo "1. Review the copied files"
echo "2. Convert templates from Nix syntax to chezmoi syntax"
echo "3. Set up 1Password integration"
echo "4. Test with 'chezmoi apply --dry-run'"

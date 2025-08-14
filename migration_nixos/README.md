# Complete Migration Guide: NixOS to Arch Linux

This guide walks you through migrating from your sophisticated NixOS setup to Arch Linux while preserving all functionality.

## Overview

**System Design:**
- **Root**: 250GB btrfs with snapshots (7 daily + 4 weekly)
- **Home**: 750GB btrfs (separate, no snapshots)
- **Boot**: 512MB FAT32 EFI
- **Bootloader**: Limine with snapshot integration
- **Desktop**: Hyprland with all your customizations
- **Secrets**: 1Password via chezmoi integration

## Phase 1: Base Installation

### 1.1 Prepare Installation Media
```bash
# Download Arch ISO and create bootable USB
dd if=archlinux.iso of=/dev/sdX bs=4M status=progress
```

### 1.2 Boot and Run Installation Script
```bash
# Boot from USB, then:
# Save the arch_install_script.sh and make executable
chmod +x arch_install_script.sh
./arch_install_script.sh
```

**What this does:**
- Creates optimized btrfs layout with proper subvolumes
- Sets up Snapper with your retention policy (7 daily + 4 weekly)
- Installs Limine bootloader with snapshot support
- Configures AMD graphics drivers
- Sets up French locale and BÉPO keyboard
- Creates user with proper groups

### 1.3 First Boot
After installation completes:
1. Remove USB and reboot
2. Log in as `vincent` 
3. Set your password: `passwd`
4. Test basic functionality

## Phase 2: Package Installation

### 2.1 Run Post-Installation Script
```bash
# Run the post-installation package script
chmod +x post-install.sh
./post-install.sh
```

**What this installs:**
- **Priority 1**: Work-critical (VPN, development tools, Hyprland)
- **Priority 2**: Applications and nice-to-have packages
- **AUR Helper**: paru for AUR package management
- **Fish Plugins**: Fisher + your essential plugins
- **System Services**: Auto-update timer, audio services

### 2.2 VPN Configuration (Work Critical)
```bash
# Edit VPN script with your work details
hx ~/.local/bin/vpn-connect

# Replace placeholders:
# YOUR_VPN_SERVER -> your actual VPN server
# YOUR_USERNAME -> your work username

# Test VPN connection
~/.local/bin/vpn-connect
```

## Phase 3: Dotfiles and Configuration

### 3.1 Install 1Password
```bash
# Install 1Password from AUR
paru -S 1password

# Install 1Password CLI
paru -S 1password-cli

# Sign in to 1Password
op signin
```

### 3.2 Install Dank Mono Font
```bash
# Copy your Dank Mono font files to:
mkdir -p ~/.local/share/fonts/DankMono
cp /path/to/your/dank-mono-files/* ~/.local/share/fonts/DankMono/

# Refresh font cache
fc-cache -fv
```

### 3.3 Set Up Chezmoi with 1Password
```bash
# Initialize chezmoi (replace with your actual dotfiles repo)
chezmoi init https://github.com/VincentBerthier/dotfiles.git

# Copy the chezmoi configuration
mkdir -p ~/.config/chezmoi
# Copy the chezmoi.toml configuration provided

# Apply dotfiles
chezmoi apply
```

### 3.4 Configure SSH Keys via 1Password
```bash
# SSH keys will be templated through chezmoi + 1Password
# Your SSH config should now work with both personal and work keys

# Test SSH key setup
ssh-add -l

# Test git signing
git commit --allow-empty -m "test commit"
```

## Phase 4: Desktop Environment

### 4.1 Hyprland Configuration
After chezmoi apply, your Hyprland setup should be ready:

```bash
# Test Hyprland launch
Hyprland

# If issues, check logs:
journalctl --user -f
```

### 4.2 Waybar and Components
Your Waybar should automatically:
- Show workspaces correctly per hostname
- Display custom modules (VPN, backup status, etc.)
- Handle multi-monitor setup

### 4.3 Terminal Setup
All terminals should be configured:
- **Wezterm**: Primary with Lua config and startup sessions
- **Kitty**: Secondary with transparency and custom keybinds  
- **Foot**: Fallback terminal
- **Ghostty**: Modern option

## Phase 5: Development Environment

### 5.1 Jujutsu Configuration
Your jj setup should be complete via chezmoi:
- Complex aliases and workflows
- SSH signing with work/personal keys
- Repository-specific configurations

```bash
# Test jujutsu setup
jj status
jj config list
```

### 5.2 Helix Editor
Your Helix configuration includes:
- BÉPO keybindings
- Language servers for all your languages
- Custom themes and snippets

```bash
# Test Helix with language servers
hx test.rs  # Should show Rust LSP working
hx test.py  # Should show Python LSP working
```

### 5.3 Python Environment
Scientific Python stack should be available:
```bash
# Test Python setup
python -c "import numpy, matplotlib, pandas, astropy; print('Scientific stack ready')"
```

## Phase 6: System Services

### 6.1 Backup System
Your duplicacy backup should be configured:
```bash
# Check backup service
systemctl --user status duplicacy-backup.timer

# Test backup manually
systemctl --user start duplicacy-backup.service
```

### 6.2 Auto-Updates
Daily update timer is configured:
```bash
# Check update timer
systemctl --user status daily-update.timer

# View update logs
journalctl --user -u daily-update.service
```

### 6.3 Snapper Snapshots
```bash
# List snapshots
sudo snapper list

# Create manual snapshot
sudo snapper create --description "Migration complete"

# Boot from snapshot (via Limine menu)
```

## Phase 7: Applications and Workflow

### 7.1 Communication Apps
Your communication stack should auto-start:
- **Discord/WebCord**: Workspace 1 (chat)
- **Signal**: Workspace 1 (chat)
- **Telegram**: Workspace 6 (work)
- **Teams**: Workspace 6 (work)
- **Thunderbird**: Workspace 1 (chat)

### 7.2 Development Workspace
- **Browser (Zen)**: General browsing
- **Code editors**: Helix primary, with full LSP support
- **Terminals**: Multi-terminal setup with session management

### 7.3 Productivity Apps
- **Obsidian**: Workspace 7
- **Spotify**: Workspace 9  
- **LibreOffice**: Available
- **GIMP**: Available

## Phase 8: Specialized Tools (Later)

### 8.1 Astronomy Applications (Can Wait)
When ready for astronomy work:
```bash
# Install astronomy tools
paru -S siril darktable stellarium

# Manual installations:
# - GraXpert (download Linux binary)
# - StarNet++ (download from website)
# - Configure Wine for Sequator
```

### 8.2 Gaming Setup
Gaming should work out of the box:
- **Steam**: Configured with AMD optimizations
- **Lutris**: For non-Steam games
- **GameMode**: Automatic performance optimization
- **MangoHud**: Performance overlay

## Verification Checklist

### ✅ Essential Functionality
- [ ] Boot from Limine
- [ ] Hyprland starts correctly
- [ ] All monitors detected
- [ ] BÉPO keyboard working
- [ ] Audio (pipewire) working
- [ ] Network/WiFi connected

### ✅ Work Functionality  
- [ ] VPN connects successfully
- [ ] SSH keys working (personal + work)
- [ ] Git signing operational
- [ ] Jujutsu workflow functional
- [ ] Development tools accessible

### ✅ Desktop Environment
- [ ] Waybar shows correctly on all monitors
- [ ] Window rules working (apps go to correct workspaces)
- [ ] Screenshots and screen recording work
- [ ] Notifications (mako) working
- [ ] All terminals launch correctly

### ✅ Applications
- [ ] Communication apps launch and auto-place
- [ ] Browsers working (Zen primary)
- [ ] Code editors fully functional
- [ ] Backup system operational
- [ ] Auto-updates configured

## Troubleshooting

### Common Issues

**Hyprland won't start:**
```bash
# Check graphics drivers
lspci -k | grep -A 2 -E "(VGA|3D)"

# Check Hyprland logs
journalctl --user -u hyprland
```

**SSH keys not working:**
```bash
# Check 1Password CLI connection
op account list

# Manually load SSH keys
ssh-add ~/.ssh/vincent ~/.ssh/tyrex
```

**VPN connection fails:**
```bash
# Check VPN script configuration
cat ~/.local/bin/vpn-connect

# Test openconnect manually
sudo openconnect --protocol=gp YOUR_VPN_SERVER
```

**Font not loading:**
```bash
# Verify font installation
fc-list | grep -i "dank"

# Rebuild font cache
fc-cache -fv
```

### Getting Help

1. **Arch Wiki**: Comprehensive documentation
2. **Hyprland Wiki**: Desktop environment specifics  
3. **Your NixOS config**: Reference for any missing functionality
4. **Chezmoi docs**: For dotfiles template issues

## Post-Migration Optimization

### Performance Tuning
```bash
# Enable zram (if desired)
sudo pacman -S zram-generator

# Optimize SSD (already configured in install)
sudo systemctl enable fstrim.timer
```

### Security Hardening
```bash
# Enable firewall
sudo ufw enable

# Review and secure SSH config
hx ~/.ssh/config
```

### Backup Verification
```bash
# Test restore functionality
# (Always test backups!)
systemctl --user start duplicacy-prune.service
```

## Success Metrics

Your migration is complete when:
1. **Work productivity**: VPN, development, communication all functional
2. **Desktop experience**: Matches or exceeds your NixOS setup
3. **System reliability**: Snapshots, backups, updates all automated
4. **Performance**: AMD graphics, gaming, audio all optimized
5. **Workflow preservation**: All your custom keybinds and workflows intact

---

## Summary

This migration preserves all the sophisticated functionality of your NixOS setup while gaining:
- **Faster package updates** (no compilation)
- **Better gaming performance** (optimized packages)
- **Simpler system maintenance** (standard Arch tools)
- **Same level of customization** (via chezmoi + 1Password)

The key insight is using **chezmoi + 1Password** to replace Home Manager's functionality while maintaining the same level of declarative configuration and secret management you had with NixOS.

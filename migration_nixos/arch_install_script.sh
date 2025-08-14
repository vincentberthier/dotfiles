#!/usr/bin/env bash
set -euo pipefail

# Arch Linux Installation Script with Btrfs + Snapper + Limine
# Optimized for Vincent's NixOS migration

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

print_status() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

print_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Configuration
HOSTNAME=""
USERNAME="vincent"
USER_EMAIL="vincent.berthier@posteo.org"
TIMEZONE="Europe/Paris"
LOCALE="fr_FR.UTF-8"
KEYBOARD="fr"
KEYBOARD_VARIANT="bepo"

# Disk configuration
TARGET_DISK=""
BOOT_SIZE="512M"
ROOT_SIZE="250G"
SWAP_SIZE="16G"

# Subvolume configuration
declare -A SUBVOLS=(
    ["@"]="/"
    ["@var_log"]="/var/log"
    ["@var_cache"]="/var/cache"
    ["@var_tmp"]="/var/tmp"
    ["@snapshots"]="/.snapshots"
    ["@swap"]="/swap"
)

# Functions
check_uefi() {
    if [[ ! -d /sys/firmware/efi ]]; then
        print_error "This script requires UEFI boot mode"
        exit 1
    fi
    print_success "UEFI boot mode detected"
}

check_internet() {
    if ! ping -c 1 www.google.fr &> /dev/null; then
        print_error "No internet connection"
        exit 1
    fi
    print_success "Internet connection verified"
}

get_user_input() {
    echo -e "${BLUE}=== Arch Linux Installation Configuration ===${NC}"
    
    # Hostname
    while [[ -z "$HOSTNAME" ]]; do
        read -p "Enter hostname: " HOSTNAME
        if [[ ! "$HOSTNAME" =~ ^[a-zA-Z0-9-]+$ ]]; then
            print_warning "Invalid hostname. Use only letters, numbers, and hyphens."
            HOSTNAME=""
        fi
    done
    
    # Target disk
    echo
    print_status "Available disks:"
    lsblk -d -o NAME,SIZE,TYPE | grep disk
    echo
    
    while [[ -z "$TARGET_DISK" ]]; do
        read -p "Enter target disk (e.g., /dev/sda): " TARGET_DISK
        if [[ ! -b "$TARGET_DISK" ]]; then
            print_warning "Invalid disk. Please enter a valid block device."
            TARGET_DISK=""
        fi
    done
    
    # Confirmation
    echo
    echo -e "${YELLOW}=== Configuration Summary ===${NC}"
    echo "Hostname: $HOSTNAME"
    echo "Target disk: $TARGET_DISK"
    echo "Root partition: 250GB (for system + snapshots)"
    echo "Home partition: ~750GB (remaining space)"
    echo "Username: $USERNAME"
    echo "Timezone: $TIMEZONE"
    echo "Locale: $LOCALE"
    echo "Keyboard: $KEYBOARD ($KEYBOARD_VARIANT)"
    echo
    print_warning "This will COMPLETELY ERASE $TARGET_DISK"
    read -p "Continue? (yes/no): " confirm
    if [[ "$confirm" != "yes" ]]; then
        print_error "Installation cancelled"
        exit 1
    fi
}

prepare_disk() {
    print_status "Preparing disk $TARGET_DISK"
    
    # Unmount any existing mounts
    umount -R /mnt 2>/dev/null || true
    
    # Wipe disk
    wipefs -af "$TARGET_DISK"
    sgdisk --zap-all "$TARGET_DISK"
    
    # Create partitions
    print_status "Creating partitions"
    sgdisk --new=1:0:+${BOOT_SIZE} --typecode=1:ef00 --change-name=1:"EFI System" "$TARGET_DISK"
    sgdisk --new=2:0:+${ROOT_SIZE} --typecode=2:8300 --change-name=2:"Linux filesystem" "$TARGET_DISK"
    sgdisk --new=3:0:0 --typecode=3:8300 --change-name=3:"Home" "$TARGET_DISK"
    
    # Get partition names
    if [[ "$TARGET_DISK" =~ nvme ]]; then
        BOOT_PART="${TARGET_DISK}p1"
        ROOT_PART="${TARGET_DISK}p2"
        HOME_PART="${TARGET_DISK}p3"
    else
        BOOT_PART="${TARGET_DISK}1"
        ROOT_PART="${TARGET_DISK}2"
        HOME_PART="${TARGET_DISK}3"
    fi
    
    print_success "Partitions created: $BOOT_PART (boot), $ROOT_PART (root), $HOME_PART (home)"
}

format_partitions() {
    print_status "Formatting partitions"
    
    # Format boot partition
    mkfs.fat -F32 -n "BOOT" "$BOOT_PART"
    
    # Format root partition with btrfs
    mkfs.btrfs -f -L "ARCH" "$ROOT_PART"
    
    # Format home partition with btrfs  
    mkfs.btrfs -f -L "HOME" "$HOME_PART"
    
    print_success "Partitions formatted"
}

create_subvolumes() {
    print_status "Creating btrfs subvolumes"
    
    # Mount root to create subvolumes
    mount "$ROOT_PART" /mnt
    
    # Create subvolumes
    for subvol in "${!SUBVOLS[@]}"; do
        btrfs subvolume create "/mnt/$subvol"
        print_status "Created subvolume: $subvol"
    done
    
    # Unmount
    umount /mnt
    
    print_success "Subvolumes created"
}

mount_filesystem() {
    print_status "Mounting filesystem"
    
    local mount_opts="noatime,compress=zstd:1,space_cache=v2,discard=async"
    
    # Mount root subvolume (no @home subvolume needed)
    mount -o "$mount_opts,subvol=@" "$ROOT_PART" /mnt
    
    # Create mount points and mount system subvolumes only
    for subvol in "${!SUBVOLS[@]}"; do
        if [[ "$subvol" != "@" && "$subvol" != "@home" ]]; then  # Skip @home
            local mount_point="/mnt${SUBVOLS[$subvol]}"
            mkdir -p "$mount_point"
            mount -o "$mount_opts,subvol=$subvol" "$ROOT_PART" "$mount_point"
            print_status "Mounted $subvol -> $mount_point"
        fi
    done
    
    # Mount separate home partition (no subvolumes)
    mkdir -p /mnt/home
    mount -o "$mount_opts" "$HOME_PART" /mnt/home
    
    # Mount boot partition
    mkdir -p /mnt/boot
    mount "$BOOT_PART" /mnt/boot
    
    # Create swapfile
    print_status "Creating swapfile"
    btrfs filesystem mkswapfile --size "$SWAP_SIZE" /mnt/swap/swapfile
    swapon /mnt/swap/swapfile
    
    print_success "Filesystem mounted"
}

install_base_system() {
    print_status "Installing base system"
    
    # Update mirrors
    # reflector --country France --latest 5 --sort rate --save /etc/pacman.d/mirrorlist
    
    # Install base packages
    pacstrap -K /mnt \
        base base-devel linux-zen linux-zen-headers linux-firmware amd-ucode \
        btrfs-progs snapper grub-btrfs \
        networkmanager bluez bluez-utils \
        git chezmoi fish \
        nano helix \
        man-db man-pages \
        reflector cargo sddm
    
    print_success "Base system installed"
}

configure_system() {
    print_status "Configuring system"
    
    # Generate fstab
    genfstab -U /mnt >> /mnt/etc/fstab
    
    # Configure system in chroot
    arch-chroot /mnt /bin/bash << EOF
# Set timezone
ln -sf /usr/share/zoneinfo/$TIMEZONE /etc/localtime
hwclock --systohc

# Configure locale
echo "$LOCALE UTF-8" >> /etc/locale.gen
locale-gen
echo "LANG=$LOCALE" > /etc/locale.conf

# Configure keyboard
echo "KEYMAP=$KEYBOARD" > /etc/vconsole.conf

# Set hostname
echo "$HOSTNAME" > /etc/hostname

# Configure hosts
cat > /etc/hosts << HOSTS_EOF
127.0.0.1   localhost
::1         localhost
127.0.1.1   $HOSTNAME.localdomain $HOSTNAME
HOSTS_EOF

# Enable services
systemctl enable NetworkManager
systemctl enable bluetooth
systemctl enable systemd-timesyncd
systemctl enable reflector.timer
systemctl enable fstrim.timer

# Create user
useradd -m -G wheel,audio,video,optical,storage -s /bin/fish $USERNAME
echo "$USERNAME:$USERNAME" | chpasswd

# Install and configure doas as primary
pacman -S --noconfirm opendoas

# Configure doas (NO PASSWORD)
cat > /etc/doas.conf << DOAS_EOF
# Allow wheel group to execute commands as root without password
permit nopass :wheel
DOAS_EOF

# Set proper permissions on doas.conf
chown root:root /etc/doas.conf
chmod 600 /etc/doas.conf

# Configure sudo ONLY for snapper and other broken tools
cat > /etc/sudoers.d/broken-software << SUDO_EOF
# ONLY for software that hardcodes sudo like idiots
%wheel ALL=(ALL) NOPASSWD: /usr/bin/snapper, /usr/bin/btrfs
SUDO_EOF
chmod 440 /etc/sudoers.d/broken-software

# Create sudo wrapper that calls doas
ln -sf /usr/bin/doas /usr/local/bin/sudo

# Make sure /usr/local/bin is in PATH before /usr/bin
echo 'export PATH="/usr/local/bin:$PATH"' >> /etc/profile

# Configure pacman
sed -i 's/#Color/Color/' /etc/pacman.conf
sed -i 's/#ParallelDownloads/ParallelDownloads/' /etc/pacman.conf
sed -i '/\[multilib\]/,/Include/s/^#//' /etc/pacman.conf

# Sync databases after enabling multilib
pacman -Sy

# Configure keyboard for console/TTY
echo "KEYMAP=fr-bepo" > /etc/vconsole.conf

# Configure keyboard for X11/Wayland
mkdir -p /etc/X11/xorg.conf.d
cat > /etc/X11/xorg.conf.d/00-keyboard.conf << 'KEYBOARD_EOF'
Section "InputClass"
    Identifier "system-keyboard"
    MatchIsKeyboard "on"
    Option "XkbLayout" "fr"
    Option "XkbVariant" "bepo"
EndSection
KEYBOARD_EOF

# For Wayland compositors that don't read X11 config, set environment
echo 'export XKB_DEFAULT_LAYOUT=fr' >> /etc/environment
echo 'export XKB_DEFAULT_VARIANT=bepo' >> /etc/environment

# Disable TPM
systemctl mask systemd-tpm2-setup-early.service
systemctl mask systemd-tpm2-setup.service
systemctl mask tpm2.target

EOF

    print_success "System configured with doas"
}

setup_snapper() {
    print_status "Setting up Snapper"
    
    arch-chroot /mnt /bin/bash << 'EOF'
# Create snapper config for root
snapper -c root create-config /

# Delete the default subvolume created by snapper
btrfs subvolume delete /.snapshots

# Create the snapshots directory
mkdir /.snapshots

# Remount the snapshots subvolume
mount -a

# Set snapper configuration
cat > /etc/snapper/configs/root << 'SNAPPER_EOF'
SUBVOLUME="/"
FSTYPE="btrfs"
QGROUP=""
SPACE_LIMIT="0.5"
FREE_LIMIT="0.2"
ALLOW_USERS=""
ALLOW_GROUPS=""
SYNC_ACL="no"
BACKGROUND_COMPARISON="yes"
NUMBER_CLEANUP="yes"
NUMBER_MIN_AGE="1800"
NUMBER_LIMIT="50"
NUMBER_LIMIT_IMPORTANT="10"
TIMELINE_CREATE="yes"
TIMELINE_CLEANUP="yes"
TIMELINE_MIN_AGE="1800"
TIMELINE_LIMIT_HOURLY="5"
TIMELINE_LIMIT_DAILY="7"
TIMELINE_LIMIT_WEEKLY="4"
TIMELINE_LIMIT_MONTHLY="0"
TIMELINE_LIMIT_YEARLY="0"
SNAPPER_EOF

# Enable snapper services
systemctl enable snapper-timeline.timer
systemctl enable snapper-cleanup.timer

# Create pacman hooks with doas instead of snap-pac
mkdir -p /etc/pacman.d/hooks

# Boot backup hook (fixed to use doas)
cat > /etc/pacman.d/hooks/50-bootbackup.hook << 'HOOK_EOF'
[Trigger]
Operation = Upgrade
Operation = Install
Operation = Remove
Type = Path
Target = boot/*

[Action]
Depends = rsync
Description = Backing up /boot...
When = PreTransaction
Exec = /usr/bin/doas /usr/bin/rsync -a --delete /boot /.bootbackup
HOOK_EOF

# Pre-transaction snapshot hook (replaces snap-pac)
cat > /etc/pacman.d/hooks/00-snapper-pre.hook << 'HOOK_EOF'
[Trigger]
Operation = Upgrade
Operation = Install
Operation = Remove
Type = Package
Target = *

[Action]
Description = Creating pre-transaction snapshot...
When = PreTransaction
Exec = /usr/bin/doas /usr/bin/snapper create --type=pre --cleanup-algorithm=number --print-number --description="pacman pre-transaction"
HOOK_EOF

# Post-transaction snapshot hook (replaces snap-pac)
cat > /etc/pacman.d/hooks/99-snapper-post.hook << 'HOOK_EOF'
[Trigger]
Operation = Upgrade
Operation = Install
Operation = Remove
Type = Package
Target = *

[Action]
Description = Creating post-transaction snapshot...
When = PostTransaction
Exec = /usr/bin/doas /usr/bin/snapper create --type=post --cleanup-algorithm=number --print-number --description="pacman post-transaction"
HOOK_EOF

EOF

    print_success "Snapper configured with doas"
}

install_limine() {
    print_status "Installing Limine bootloader"
    
    arch-chroot /mnt /bin/bash << 'EOF'
# Update package database
pacman -Sy
# Install limine from official repos
pacman -S --noconfirm limine

# Install limine to disk  
TARGET_DISK_LIMINE=$(lsblk -no PKNAME $(findmnt -no SOURCE /) | head -1)
limine bios-install /dev/${TARGET_DISK_LIMINE}

# Create limine configuration
mkdir -p /boot/EFI/BOOT
cat > /boot/limine.conf << 'LIMINE_EOF'
timeout: 5
graphics: yes
default_entry: 1

/Arch Linux
    comment: Arch Linux (linux-zen)
    protocol: linux
    kernel_path: boot():/vmlinuz-linux-zen
    kernel_cmdline: root=LABEL=ARCH rootflags=subvol=@ rw quiet loglevel=3 rd.systemd.show_status=auto rd.udev.log_level=3
    module_path: boot():/amd-ucode.img
    module_path: boot():/initramfs-linux-zen.img

/Arch Linux Fallback
    comment: Arch Linux Fallback (linux-zen)
    protocol: linux
    kernel_path: boot():/vmlinuz-linux-zen
    kernel_cmdline: root=LABEL=ARCH rootflags=subvol=@ rw
    module_path: boot():/amd-ucode.img
    module_path: boot():/initramfs-linux-zen-fallback.img
LIMINE_EOF

# Copy limine files
cp /usr/share/limine/BOOTX64.EFI /boot/EFI/BOOT/
cp /usr/share/limine/limine-bios.sys /boot/

EOF

    print_success "Limine installed"
}

copy_post_install() {
    print_status "Copying post-install script"
    
    # Copy the actual post_install.sh script to user's home
    if [[ -f "migration_nixos/post_install.sh" ]]; then
        cp migration_nixos/post_install.sh /mnt/home/$USERNAME/
        # chown $USERNAME:$USERNAME /mnt/home/$USERNAME/post_install.sh
        chmod +x /mnt/home/$USERNAME/post_install.sh
        print_success "Post-install script copied to /home/$USERNAME/"
    else
        print_warning "post_install.sh not found in current directory"
        print_warning "You'll need to download it manually after installation"
    fi
}

main() {
    echo -e "${BLUE}"
    echo "=================================================="
    echo "  Arch Linux Installation with Btrfs + Snapper"
    echo "  Optimized for Vincent's NixOS Migration"
    echo "=================================================="
    echo -e "${NC}"
    
    check_uefi
    check_internet
    get_user_input
    
    prepare_disk
    format_partitions
    create_subvolumes
    mount_filesystem
    install_base_system
    configure_system
    setup_snapper
    install_limine
    copy_post_install
    
    print_success "Installation completed!"
    echo
    echo -e "${GREEN}Next steps:${NC}"
    echo "1. Reboot into the new system"
    echo "2. Log in as $USERNAME"
    echo "3. Run ~/post-install.sh to install AUR helper and basic packages"
    echo "4. Set up chezmoi with your dotfiles"
    echo "5. Configure 1Password integration"
    echo
    echo -e "${YELLOW}Important:${NC}"
    echo "- Set user password: passwd"
    echo "- Configure chezmoi: chezmoi init --apply"
    echo "- Install Dank Mono fonts"
    echo
    read -p "Press Enter to reboot or Ctrl+C to stay in live environment..."
    reboot
}

# Run main function
main "$@"

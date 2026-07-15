function maj --description "Update the system and cleanup"
    while ! ping -c1 www.google.fr >/dev/null 2>&1
        sleep 1
    end
    doas pacman -Syu --noconfirm
    paru -Syu --noconfirm
    claude update
    /usr/bin/flatpak update -y
    paru -Qdtq | paru -Rns --noconfirm -
end

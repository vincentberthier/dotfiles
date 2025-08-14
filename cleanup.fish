#!/usr/bin/env fish

cd ~/.local/share/chezmoi

# For scripts where neither is templated, remove the executable_ version and rename the other to executable_

# Hypr scripts
rm private_dot_config/hypr/scripts/executable_fix_slow_launch.sh
mv private_dot_config/hypr/scripts/fix_slow_launch.sh private_dot_config/hypr/scripts/executable_fix_slow_launch.sh

rm private_dot_config/hypr/scripts/executable_grimblast.sh
mv private_dot_config/hypr/scripts/grimblast.sh private_dot_config/hypr/scripts/executable_grimblast.sh

rm private_dot_config/hypr/scripts/executable_kill_window.sh
mv private_dot_config/hypr/scripts/kill_window.sh private_dot_config/hypr/scripts/executable_kill_window.sh

rm private_dot_config/hypr/scripts/executable_menu.sh
mv private_dot_config/hypr/scripts/menu.sh private_dot_config/hypr/scripts/executable_menu.sh

rm private_dot_config/hypr/scripts/executable_setup_environment.sh
mv private_dot_config/hypr/scripts/setup_environment.sh private_dot_config/hypr/scripts/executable_setup_environment.sh

# Waybar scripts  
rm private_dot_config/waybar/scripts/executable_backup.sh
mv private_dot_config/waybar/scripts/backup.sh private_dot_config/waybar/scripts/executable_backup.sh

rm private_dot_config/waybar/scripts/executable_track_spotify.sh
mv private_dot_config/waybar/scripts/track_spotify.sh private_dot_config/waybar/scripts/executable_track_spotify.sh

rm private_dot_config/waybar/scripts/executable_waybar-wttr.py
mv private_dot_config/waybar/scripts/waybar-wttr.py private_dot_config/waybar/scripts/executable_waybar-wttr.py

# Special case: vpn.sh has "empty_" prefix, so handle it separately
rm private_dot_config/waybar/scripts/empty_executable_vpn.sh
mv private_dot_config/waybar/scripts/vpn.sh private_dot_config/waybar/scripts/executable_vpn.sh

echo "Manual fixes complete! Now check:"
echo "chezmoi diff"

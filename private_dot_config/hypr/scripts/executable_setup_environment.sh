#!/usr/bin/env bash
set -e

function move_librewolf {
    readarray -t windows < <(hyprctl clients -j | jq -r '[.[] | select((.title | startswith("'"$1"'")) and (.class=="LibreWolf"))]' | jq -r '.[].address')
    for w in "${windows[@]}"; do
        hyprctl dispatch movetoworkspacesilent name:"$2",address:"$w"
    done
}

# sleep 5
move_librewolf "General" general
move_librewolf "Dev’" webdev
move_librewolf "Work" work
move_librewolf "New Window" misc

# sleep 10
# hyprctl dispatch movetoworkspacesilent name:chat,discord

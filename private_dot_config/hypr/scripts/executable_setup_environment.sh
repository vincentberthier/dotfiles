#!/usr/bin/env bash
set -e

function move_librewolf {
    readarray -t windows < <(hyprctl clients -j | jq -r '[.[] | select((.title | startswith("'"$1"'")) and (.class=="LibreWolf"))]' | jq -r '.[].address')
    for w in "${windows[@]}"; do
        hyprctl dispatch movetoworkspacesilent name:"$2",address:"$w"
    done
}

function move_foot {
    echo "$1"
    hyprctl dispatch movetoworkspacesilent name:"$2",pid:"$1"
}


foots="$(hyprctl clients -j | jq -r '[.[] | select(.class=="foot")]' | jq -r '.[].pid')"
readarray -t <<< "$foots"
move_foot "${MAPFILE[0]}" dev
move_foot "${MAPFILE[1]}" dev
move_foot "${MAPFILE[2]}" misc
sleep 5
move_librewolf "General" general
move_librewolf "Dev’" webdev
move_librewolf "Work" work
move_librewolf "New Window" misc

# sleep 10
# hyprctl dispatch movetoworkspacesilent name:chat,discord

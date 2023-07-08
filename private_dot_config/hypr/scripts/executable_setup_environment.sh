#!/bin/bash
set -e

function move_firefox {
    window=$(hyprctl clients -j | jq -r '[.[] | select((.title | startswith("'"$1"'")) and (.class=="firefox"))]' | jq -r '.[].address')
    hyprctl dispatch movetoworkspacesilent name:"$2",address:"$window"
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
move_firefox "General" general
move_firefox "Dev’" webdev
move_firefox "Work" work
move_firefox "New Window" misc

sleep 10
hyprctl dispatch movetoworkspacesilent name:chat,discord

#!/bin/bash
set -e

function move_firefox {
    window=$(hyprctl clients -j | jq -r '[.[] | select((.title | startswith("'"$1"'")) and (.class=="firefox"))]' | jq -r '.[].address')
    hyprctl dispatch movetoworkspacesilent name:"$2",address:"$window"
}

function move_foot {
    window=$(hyprctl clients -j | jq -r '[.[] | select(.class=="foot")]' | jq -r '.[].address')
    hyprctl dispatch movetoworkspacesilent name:"$2",address:"$window"
}

foot
move_foot dev
foot
move_foot dev
foot
move_foot misc
sleep 2
move_firefox "General" default
move_firefox "Dev’" dev
move_firefox "New Window" misc

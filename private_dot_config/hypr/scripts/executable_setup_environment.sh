#!/usr/bin/env bash
set -e

function move_libreWolf {
    window=$(hyprctl clients -j | jq -r '[.[] | select((.title | startswith("'"$1"'")) and (.class=="LibreWolf"))]' | jq -r '.[].address')
    hyprctl dispatch movetoworkspacesilent name:"$2",address:"$window"
}

sleep 5
move_librewolf "General" general
move_libreWolf "Dev’" webdev
move_librewolf "Work" work
move_librewolf "New Window" misc

sleep 10
hyprctl dispatch movetoworkspacesilent name:chat,discord

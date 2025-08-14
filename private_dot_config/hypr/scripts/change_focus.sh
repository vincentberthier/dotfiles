#!/usr/bin/env bash
set -e

if [ "$(hyprctl activewindow -j | jq -r ".fullscreen")" == "true" ]; then
    hyprctl dispatch focusmonitor "$1"
else
    hyprctl dispatch movefocus "$1"
fi

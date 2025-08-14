#!/usr/bin/env bash

CONFIG_FILE="$HOME/.config/hypr/hyprland.conf"
REGEX="kb_variant = ([a-z]+)  # binding physical map"

function notify() {
    notify-send --app-name="Hyprland" --expire-time=4000 --icon="" "$1"
}

target_line=$(grep -oE "$REGEX" "$CONFIG_FILE")
if [[ -z $target_line ]]; then
    notify "couldn’t find the current layout."
    exit 255
fi

# should always be true
if [[ $target_line =~ $REGEX ]]; then
    CURRENT="${BASH_REMATCH[1]}"
else
    exit 255
fi


if [[ $# == 1 ]]; then
    NEW_LAYOUT=$1
else
    if [[ $CURRENT == "bepo" ]]; then
        NEW_LAYOUT="azerty"
    else
        NEW_LAYOUT="bepo"
    fi
fi

notify "Switching from ${CURRENT} mappings to ${NEW_LAYOUT}"
sed -i "s/kb_variant = ${CURRENT}  # binding physical map/kb_variant = ${NEW_LAYOUT}  # binding physical map/g" "$CONFIG_FILE"

#!/usr/bin/env bash

WOFI_HOME="$HOME/.config/hypr/wofi"
CONFIG="$WOFI_HOME/config"
STYLE="$WOFI_HOME/style.css"
COLORS="$WOFI_HOME/colors"

echo "$CONFIG $STYLE $COLORS"
if [[ ! $(pidof wofi) ]]; then
    wofi --show drun --prompt "Search..." --conf "$CONFIG" --style "$STYLE" --color "$COLORS"
else
    pkill wofi
fi

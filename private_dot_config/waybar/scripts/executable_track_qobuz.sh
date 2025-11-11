#!/usr/bin/env bash

TARGET="/tmp/qobuz_currently_playing.txt"

if [[ ! -f $TARGET ]]; then
    touch "$TARGET"
fi

STATUS=$(playerctl -p com.github.sofusa-quboz-player status 2> /dev/null)
TRACK=$(playerctl -p com.github.sofusa-quboz-player metadata --format "[{{ artist }}] {{ album }} - {{ title }}")
RES=""

if [[ $STATUS == "Playing" ]]; then
    RES="󰽰 $TRACK "
elif [[ $STATUS == "Paused" ]]; then
    RES="󰽰 $TRACK "
else
    RES="󰽰 ----- "
fi

echo "$RES"

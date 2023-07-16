#!/usr/bin/env bash

TARGET="/tmp/spotify_currently_playing.txt"

if [[ ! -f $TARGET ]]; then
    touch "$TARGET"
fi

STATUS=$(playerctl -p spotifyd status 2> /dev/null)
TRACK=$(cat /tmp/spotify_currently_playing.txt)
RES=""

if [[ $STATUS == "Playing" ]]; then
    RES="󰽰 $TRACK "
elif [[ $STATUS == "Paused" ]]; then
    RES="󰽰 $TRACK "
else
    RES="󰽰 ----- "
fi

echo "$RES"

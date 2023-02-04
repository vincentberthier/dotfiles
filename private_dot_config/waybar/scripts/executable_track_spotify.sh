#!/bin/bash

STATUS=$(playerctl -p spotifyd status 2> /dev/null)
TRACK=$(cat /tmp/spotify_currently_playing.txt)
RES=""

if [[ $STATUS == "Playing" ]]; then
    RES="󰽰 $TRACK "
elif [[ $STATUS == "Paused" ]]; then
    RES="󰽰 $TRACK "
elif [[ "$STATUS" == "Stopped" ]]; then
    RES="󰽰 ----- "
fi

echo "$RES"

#!/bin/bash

STATUS=$(playerctl -p spotifyd status)
TRACK=$(cat /tmp/spotify_currently_playing.txt)
RES=""

if [[ $STATUS == "Playing" ]]; then
    RES="$TRACK "
elif [[ $STATUS == "Stopped" ]]; then
    RES="$TRACK "
fi

echo "$RES"

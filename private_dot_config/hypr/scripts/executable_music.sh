#!/bin/bash

daemon=$(pidof spotifyd)
if [[ -z $daemon ]]; then
    spotifyd --on-song-change-hook "/home/vincent/.config/waybar/scripts/spotify.sh"
fi

spt

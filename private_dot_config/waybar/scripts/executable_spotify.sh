#!/bin/bash

metadata=$(playerctl -p spotifyd metadata 2> /dev/null)

ART_RE="spotifyd mpris:artUrl\s+([0-9A-Za-z_/\:\.-]+)"
TITLE_RE="spotifyd xesam:title\s+([0-9A-Za-z'’, \.\:-]+)"
ALBUM_RE="spotifyd xesam:album\s+([0-9A-Za-z'’, \.\:-]+)"
ARTIST_RE="spotifyd xesam:albumArtist\s+([0-9A-Za-z'’, \.\:-]+)"

ART=""
if [[ $metadata =~ $ART_RE ]]; then
    ART="${BASH_REMATCH[1]}"
fi
TITLE=""
if [[ $metadata =~ $TITLE_RE ]]; then
    TITLE="${BASH_REMATCH[1]}"
fi
ALBUM=""
if [[ $metadata =~ $ALBUM_RE ]]; then
    ALBUM="${BASH_REMATCH[1]}"
fi
ARTIST=""
if [[ $metadata =~ $ARTIST_RE ]]; then
    ARTIST="${BASH_REMATCH[1]}"
fi

if [[ "$ARTIST - $TITLE" == $(cat /tmp/spotify_currently_playing) ]]
exit 0
fi

wget -O /tmp/spotify_art "$ART" 2> /dev/null
notify-send -u low -a Spotify -i /tmp/spotify_art "$ARTIST" "[$ALBUM] $TITLE"
echo "$ARTIST - $TITLE" > /tmp/spotify_currently_playing.txt

#!/usr/bin/env bash

metadata=$(playerctl -p hifirs metadata 2> /dev/null)
TARGET="/tmp/qobuz_currently_playing.txt"

if [[ ! -f $TARGET ]]; then
    touch "$TARGET"
fi

ART_RE="hifirs mpris:artUrl\s+([0-9A-Za-z_/\:\.-]+)"
TITLE_RE="hifirs xesam:title\s+([0-9A-Za-z'’, \.\:-]+)"
ALBUM_RE="hifirs xesam:album\s+([0-9A-Za-z'’, \.\:-]+)"
ARTIST_RE="hifirs xesam:albumArtist\s+([0-9A-Za-z'’, \.\:-]+)"

ART=""
if [[ $metadata =~ $ART_RE ]]; then
    ART="${BASH_REMATCH[1]}"
fi
TITLE=""
if [[ $metadata =~ $TITLE_RE ]]; then
    TITLE=$(echo "${BASH_REMATCH[1]}" | xargs)
fi
ALBUM=""
if [[ $metadata =~ $ALBUM_RE ]]; then
    ALBUM=$(echo "${BASH_REMATCH[1]}" | xargs)
fi
ARTIST=""
if [[ $metadata =~ $ARTIST_RE ]]; then
    ARTIST=$(echo "${BASH_REMATCH[1]}" | xargs)
fi

if [[ "$ARTIST - $TITLE" == $(cat "$TARGET" 2> /dev/null) ]]; then
    exit 0
fi

wget -O /tmp/qobuz_art "$ART" 2> /dev/null
notify-send -u low -a qobuz -i /tmp/qobuz_art "$ARTIST" "[$ALBUM] $TITLE"
echo "$ARTIST - $TITLE" > "$TARGET"

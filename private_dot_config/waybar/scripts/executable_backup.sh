#!/usr/bin/env bash

LOG_PATH="${XDG_DATA_HOME}/duplicacy"

# Get today’s log files
BACKUP_LOG="${LOG_PATH}/$(date +%Y-%m-%d).log"

TEXT=""
DISK_OK="󰋊"
DISK_ERROR="󱁌"
DISK_DELAY=3600

NOW=$(date +%s)

if [ ! -f "$BACKUP_LOG" ]; then
    TEXT="${TEXT} <span foreground='#f38ba8'>${DISK_ERROR}</span>"
else
    LAST_MODIF=$(date -r "$BACKUP_LOG" +%s)
    ((ELAPSED = NOW - LAST_MODIF))
    ((STALE = DISK_DELAY * 2 / 3))
    if (( ELAPSED > DISK_DELAY )); then
        TEXT="${TEXT} <span foreground='#f38ba8'>${DISK_ERROR}</span>"
    elif (( ELAPSED >= STALE )); then
        TEXT="${TEXT} <span foreground='#fab387'>${DISK_OK}</span>"
    else
        TEXT="${TEXT} <span foreground='#a6e3a1'>${DISK_OK}</span>"
    fi
fi

JSON="{ \"text\": \"$TEXT\" }"
echo "$JSON"

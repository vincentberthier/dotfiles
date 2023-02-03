#!/bin/bash

BACKUP_PATH="/mnt/aegis/backup/"
LOG_PATH="$HOME/.local/share/duplicacy"


# Get today’s log files
BACKUP_LOG="${LOG_PATH}/$(date +%Y-%m-%d).log"
SYNC_LOG="${LOG_PATH}/$(date +%Y-%m-%d)-sync.log"

TEXT=""
REMOTE_OK="󰒍"
REMOTE_ERROR="󰒎"
REMOTE_DELAY=21600
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
    if (( $ELAPSED > $DISK_DELAY )); then
        TEXT="${TEXT} <span foreground='#f38ba8'>${DISK_ERROR}</span>"
    elif (( $ELAPSED >= $STALE )); then
        TEXT="${TEXT} <span foreground='#fab387'>${DISK_OK}</span>"
    else
        TEXT="${TEXT} <span foreground='#a6e3a1'>${DISK_OK}</span>"
    fi
fi

if [ ! -f "$SYNC_LOG" ]; then
    TEXT="${TEXT} <span foreground='#f38ba8'>${REMOTE_ERROR}</span>"
else
    LAST_MODIF=$(date -r "$BACKUP_LOG" +%s)
    ((ELAPSED = NOW - LAST_MODIF))
    ((STALE = REMOTE_DELAY * 2 / 3))
    if (( $ELAPSED > $REMOTE_DELAY )); then
        TEXT="${TEXT} <span foreground='#f38ba8'>${REMOTE_ERROR}</span>"
    elif (( $ELAPSED >= $STALE )); then
        TEXT="${TEXT} <span foreground='#fab387'>${REMOTE_OK}</span>"
    else
        TEXT="${TEXT} <span foreground='#a6e3a1'>${REMOTE_OK}</span>"
    fi
fi

JSON="{ \"text\": \"$TEXT \" }"
echo """$JSON"

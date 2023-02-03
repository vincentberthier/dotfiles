#!/bin/bash

# Prune old snapshots
# 1 revision per day for a week, then 1 per week for a month then 1 per month after six months
/usr/bin/duplicacy prune -threads 8 -keep 30:180 -keep 7:30 -keep 1:7
# /usr/bin/duplicacy prune -threads 4 -keep 0:360     # Discard everything after a year


LOG_PATH="/home/vincent/.local/share/duplicacy/$(date +%Y-%m-%d)-sync.log"
/usr/bin/rclone sync --progress /mnt/aegis/backup/ crypt:backup >> "$LOG_PATH"

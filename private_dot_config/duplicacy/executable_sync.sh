#!/bin/bash

# Prune old snapshots
/usr/bin/duplicacy prune -keep 1:30

LOG_PATH="/home/vincent/.local/share/duplicacy/$(date +%Y-%m-%d)-sync.log"
/usr/bin/rclone sync --progress /mnt/aegis/backup/ crypt:backup >> "$LOG_PATH"

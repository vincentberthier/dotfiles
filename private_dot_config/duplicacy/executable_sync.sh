#!/bin/bash

# Prune old snapshots
/usr/bin/duplicacy prune -keep 1:7       # 1 revision per day after a week
/usr/bin/duplicacy prune -keep 7:30      # 1 revision per week after a month
/usr/bin/duplicacy prune -keep 30:180    # 1 revision per month after six months
# /usr/bin/duplicacy prune -keep 0:360     # Discard everything after a year


LOG_PATH="/home/vincent/.local/share/duplicacy/$(date +%Y-%m-%d)-sync.log"
/usr/bin/rclone sync --progress /mnt/aegis/backup/ crypt:backup >> "$LOG_PATH"

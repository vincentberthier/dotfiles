#!/bin/bash

# Cron job to backup locally
# To init a new repository: duplicacy init --repository FOLDER_TO_BACKUP --storage-name Aegis BACKUP_NAME /mnt/aegis/backup/

LOG_PATH="/home/vincent/.local/share/duplicacy/"
mkdir -p "$LOG_PATH"

# Remove log files older than a weep
find "$LOG_PATH" -type f -mtime 6 -delete

# Create the new log file
LOG_FILE=$LOG_PATH/$(date +%Y-%m-%d).log

echo "-------------------------------------------------------" >> "$LOG_FILE"
echo "Début de la sauvegarde: $(date)" >> "$LOG_FILE"
echo "-------------------------------------------------------" >> "$LOG_FILE"

REPO_ROOT=/home/vincent/.config/duplicacy/
for dir in */; do
    echo "------------- Traitement de $dir -------------" >> "$LOG_FILE"
    cd "$REPO_ROOT/$dir"
    /usr/bin/duplicacy backup -threads 4 -stats >> "$LOG_FILE"
done
echo "------------- Vérification d’intégrité -------------" >> "$LOG_FILE"
/usr/bin/duplicacy check -stats -tabular >> "$LOG_PATH/$(date +%Y-%m-%d)-sync.log"

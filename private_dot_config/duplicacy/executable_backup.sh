#!/bin/bash

# Cron job to backup locally
# To init a new repository: duplicacy init --repository FOLDER_TO_BACKUP --storage-name Aegis BACKUP_NAME /mnt/aegis/backup/

LOG_PATH="/home/vincent/.config/duplicacy/"
mkdir -p "$LOG_PATH"

# Remove log files older than a weep
find "$LOG_PATH" -type f -mtime 6 -delete

# Create the new log file
LOG_PATH=LOG_PATH/$(date +%Y-%m-%d).log

echo "-------------------------------------------------------" >> "$LOG_PATH"
echo "Début de la sauvegarde: $(date)" >> "$LOG_PATH"
echo "-------------------------------------------------------" >> "$LOG_PATH"

ROOT=$PWD
for dir in */; do
    echo "------------- Traitement de $dir -------------" >> "$LOG_PATH"
    cd "$ROOT/$dir"
    /usr/bin/duplicacy backup -threads 4 -stats >> "$LOG_PATH"
done
echo "------------- Vérification d’intégrité -------------" >> "$LOG_PATH"
/usr/bin/duplicacy check -stats -tabular >> "$LOG_PATH"

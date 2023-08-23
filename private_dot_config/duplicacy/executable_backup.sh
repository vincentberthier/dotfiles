#!/usr/bin/env bash

# Cron job to backup locally

FOLDERS=("$HOME/code" "$HOME/Documents" "$HOME/Images" "$XDG_CONFIG_HOME")
LOG_PATH="${XDG_DATA_HOME}/duplicacy"
mkdir -p "$LOG_PATH"

# Remove log files older than a weep
find "$LOG_PATH" -type f -mtime 6 -delete

# Create the new log file
LOG_FILE=$LOG_PATH/$(date +%Y-%m-%d).log.tmp

echo "-------------------------------------------------------" >> "$LOG_FILE"
echo "Début de la sauvegarde: $(date)" >> "$LOG_FILE"
echo "-------------------------------------------------------" >> "$LOG_FILE"

for dir in "${FOLDERS[@]}"; do
    echo "------------- Traitement de $dir -------------" >> "$LOG_FILE"
    cd "$dir"
    /usr/bin/duplicacy backup -threads 4 >> "$LOG_FILE"
done
CHECK_LOG="$LOG_PATH/$(date +%Y-%m-%d)-check.log.tmp"
echo "------------- Vérification d’intégrité -------------" >> "$CHECK_LOG"
/usr/bin/duplicacy check -stats -tabular >> "$CHECK_LOG"

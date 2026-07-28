#!/usr/bin/env bash
# Hourly duplicacy backup, to the pcloud vault and — when the drive is
# connected — to the local Aegis storage. Driven by duplicacy-backup.timer.

set -uo pipefail

source "${XDG_CONFIG_HOME:-${HOME}/.config}/duplicacy/lib.sh"

mkdir -p "$LOG_PATH"
exec >>"${LOG_PATH}/$(date +%F).log" 2>&1

log "------------------------------------------------------------"
log "Début de la sauvegarde"

load_storage_password || exit 1

status=0

backup_to() {
	local storage="$1" dir
	for dir in "${FOLDERS[@]}"; do
		log "----- ${storage}: ${dir}"
		cd "$dir" || {
			log "ERROR: ${dir} is unreachable"
			status=1
			continue
		}
		duplicacy backup -threads 4 -storage "$storage" || {
			log "ERROR: backup of ${dir} to ${storage} failed"
			status=1
		}
	done
}

if cloud_available; then
	backup_to default
else
	log "ERROR: ${CLOUD_MOUNT} is not mounted — cloud backup skipped"
	status=1
fi

if aegis_available; then
	backup_to aegis
else
	log "Aegis drive not connected — local backup skipped (not an error)"
fi

prune_logs
log "Fin de la sauvegarde (status ${status})"
exit "$status"

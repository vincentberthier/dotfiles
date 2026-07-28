#!/usr/bin/env bash
# Daily prune of both storages. Driven by duplicacy-prune.timer.
# Retention: one revision per day for a week, one per week for a month,
# one per month up to six months.

set -uo pipefail

source "${XDG_CONFIG_HOME:-${HOME}/.config}/duplicacy/lib.sh"

mkdir -p "$LOG_PATH"
exec >>"${LOG_PATH}/$(date +%F)-prune.log" 2>&1

log "------------------------------------------------------------"
log "Début du nettoyage"

load_storage_password || exit 1

# Any repository works: -all prunes every snapshot id in the storage.
cd "${HOME}/Documents" || {
	log "ERROR: ${HOME}/Documents is unreachable"
	exit 1
}

status=0

prune_storage() {
	local storage="$1"
	log "----- pruning ${storage}"
	duplicacy prune -threads 8 -keep 30:180 -keep 7:30 -keep 1:7 -all -exhaustive -storage "$storage" || {
		log "ERROR: prune of ${storage} failed"
		status=1
	}
}

if cloud_available; then
	prune_storage default
else
	log "ERROR: ${CLOUD_MOUNT} is not mounted — cloud prune skipped"
	status=1
fi

if aegis_available; then
	prune_storage aegis
else
	log "Aegis drive not connected — local prune skipped (not an error)"
fi

log "Fin du nettoyage (status ${status})"
exit "$status"

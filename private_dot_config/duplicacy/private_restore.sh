#!/usr/bin/env bash
# Manual restore of the four backed-up folders onto a fresh machine.
#
# THIS OVERWRITES ~/code, ~/Documents, ~/Images AND ~/.config with the newest
# revision. It is a disaster-recovery tool, run by hand, and must never be wired
# into a startup sequence.
#
# Restores from Aegis when the drive is connected (fast, local), otherwise from
# the pcloud vault.

set -uo pipefail

source "${XDG_CONFIG_HOME:-${HOME}/.config}/duplicacy/lib.sh"

RSA_KEY="${HOME}/.ssh/duplicacy"

if [[ "${1:-}" != "--yes" ]]; then
	cat >&2 <<-EOF
		This will overwrite the contents of:
		  ${FOLDERS[*]}
		with the newest backed-up revision.

		Re-run with --yes to proceed.
	EOF
	exit 1
fi

load_storage_password || exit 1
load_rsa_passphrase

RSA_PUBKEY=$(rsa_pem_pubkey) || exit 1
trap 'rm -f "$RSA_PUBKEY"' EXIT

if aegis_available; then
	storage_name="aegis"
	storage_url="$AEGIS_STORAGE"
elif cloud_available; then
	storage_name="default"
	storage_url="$CLOUD_MOUNT"
else
	log "ERROR: neither the Aegis drive nor ${CLOUD_MOUNT} is available"
	exit 1
fi
log "Restoring from ${storage_name} (${storage_url})"

for folder in "${FOLDERS[@]}"; do
	id=$(snapshot_id_for "$folder")
	log "Restoring ${folder} (snapshot ${id})"
	mkdir -p "$folder"
	cd "$folder" || continue

	if [[ ! -d .duplicacy ]]; then
		duplicacy init -e -key "$RSA_PUBKEY" -storage-name "$storage_name" "$id" "$storage_url" || continue
		sd '"filters": ""' "\"filters\": \"${XDG_CONFIG_HOME}/duplicacy/filters.txt\"" .duplicacy/preferences
	fi

	revision=$(latest_revision "$id" "$storage_name")
	if [[ -z "$revision" ]]; then
		log "ERROR: no revision found for ${id}, skipping"
		continue
	fi

	duplicacy restore -ignore-owner -r "$revision" -storage "$storage_name" -key "$RSA_KEY" ||
		log "ERROR: restore of ${folder} failed"
done

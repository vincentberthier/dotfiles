#!/usr/bin/env bash
# Integrity verification. Two modes, driven by two timers:
#
#   weekly  - chunk existence on both storages, plus a full file-level
#             verification of the newest revision of every snapshot id.
#             That is a real restorability proof: chunks are fetched,
#             files reconstructed and hashes compared, nothing is written.
#   monthly - everything above, plus -chunks: every chunk in the storage is
#             decrypted and hash-verified.
#
# The heavy modes run against the Aegis storage only. It is a local SSD, so
# verification costs nothing in bandwidth; doing the same against pcloud would
# mean re-downloading the whole 260G.

set -uo pipefail

MODE="${1:-weekly}"

# shellcheck source=/dev/null
source "${XDG_CONFIG_HOME:-${HOME}/.config}/duplicacy/lib.sh"

mkdir -p "$LOG_PATH"
exec >>"${LOG_PATH}/$(date +%F)-check.log" 2>&1

log "------------------------------------------------------------"
log "Vérification d'intégrité (${MODE})"

load_storage_password || exit 1

cd "${HOME}/Documents" || {
	log "ERROR: ${HOME}/Documents is unreachable"
	exit 1
}

status=0

run_check() {
	local label="$1"
	shift
	log "----- ${label}"
	"$@" || {
		log "ERROR: ${label} failed"
		status=1
	}
}

if cloud_available; then
	run_check "default: chunk existence" \
		duplicacy -background check -all -stats -tabular -threads 4 -storage default
else
	log "ERROR: ${CLOUD_MOUNT} is not mounted — cloud check skipped"
	status=1
fi

if ! aegis_available; then
	log "Aegis drive not connected — deep verification skipped (not an error)"
	log "Fin de la vérification (status ${status})"
	exit "$status"
fi

run_check "aegis: chunk existence" \
	duplicacy check -all -stats -tabular -threads 4 -storage aegis

# File-level verification needs the RSA private key to decrypt chunks.
load_rsa_passphrase
if RSA_KEY=$(rsa_pkcs1_privkey); then
	trap 'rm -f "$RSA_KEY"' EXIT
	for folder in "${FOLDERS[@]}"; do
		id=$(snapshot_id_for "$folder")
		revision=$(latest_revision "$id" aegis)
		if [[ -z "$revision" ]]; then
			log "ERROR: no revision of ${id} on aegis to verify"
			status=1
			continue
		fi
		run_check "aegis: file verification of ${id} revision ${revision}" \
			duplicacy -background check -id "$id" -r "$revision" -files -threads 4 -storage aegis -key "$RSA_KEY"
	done
else
	log "ERROR: file-level verification skipped, the RSA key is unusable"
	status=1
fi

if [[ "$MODE" == "monthly" ]]; then
	run_check "aegis: full chunk verification" \
		duplicacy -background check -all -chunks -threads 4 -storage aegis -key "$RSA_KEY"
fi

log "Fin de la vérification (status ${status})"
exit "$status"

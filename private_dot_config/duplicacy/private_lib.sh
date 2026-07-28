#!/usr/bin/env bash
# Shared helpers for the duplicacy backup / prune / check scripts.
#
# Sourced, never run directly. Deliberately NOT a chezmoi template and
# deliberately free of secrets: passwords are read from 1Password at run time so
# nothing sensitive is ever written to disk (and ~/.config is itself backed up).

CLOUD_MOUNT="${HOME}/vault"
AEGIS_MOUNT="/run/media/${USER}/Aegis"
AEGIS_STORAGE="${AEGIS_MOUNT}/duplicacy"

XDG_CONFIG_HOME="${XDG_CONFIG_HOME:-${HOME}/.config}"
XDG_DATA_HOME="${XDG_DATA_HOME:-${HOME}/.local/share}"

# The code/documents/images snapshot ids are deliberately NOT host-qualified:
# the intent is that any machine can restore the common set and carry on. That
# only works if exactly one machine ever writes them — otherwise revisions from
# two machines interleave under one id and a restore of "the newest revision"
# hands you the wrong host's data.
#
# gaia is that machine. Everywhere else backs up ~/.config alone, which is
# host-qualified (config_<hostname>) and so cannot collide. Nothing is lost:
# ~/code lives in VCS, and the other machines are used to drive gaia rather than
# worked in directly.
FULL_BACKUP_HOST="gaia"

# shellcheck disable=SC2034  # consumed by the scripts that source this file
if [[ "$(hostname)" == "$FULL_BACKUP_HOST" ]]; then
	FOLDERS=("${HOME}/code" "${HOME}/Documents" "${HOME}/Images" "${XDG_CONFIG_HOME}")
else
	FOLDERS=("${XDG_CONFIG_HOME}")
fi
LOG_PATH="${XDG_DATA_HOME}/duplicacy"
LOG_RETENTION_DAYS=30

# Holds the storage password and nothing else. Rendered by chezmoi from
# 1Password; excluded from the backups themselves via filters.txt.
SECRET_FILE="${XDG_CONFIG_HOME}/duplicacy/password"

log() {
	printf '%s %s\n' "$(date '+%Y-%m-%d %H:%M:%S')" "$*"
}

# `op read` blocks on a desktop authorisation prompt when 1Password is locked.
# The bound here is a deadlock circuit-breaker, not a synchronisation mechanism:
# a locked vault must fail fast so the unit exits and the timer retries later,
# rather than wedging until the next tick.
op_read() {
	timeout 30 op read --no-newline "$1"
}

# Only the storage password is needed to back up, prune or check. The RSA
# passphrase is required for restore alone, so it is loaded separately and stays
# out of the unattended path entirely.
#
# The password comes from a chezmoi-rendered file holding nothing but the secret
# (mode 0600, inside a 0700 directory), because reading 1Password at run time
# means no backups whenever the vault is locked — which it auto-does. 1Password
# remains the source of truth: the chezmoi source is a template calling
# onepasswordRead, so the secret never reaches git. The op path stays as a
# fallback for a machine that has not run `chezmoi apply` yet.
load_storage_password() {
	local password
	if [[ -r "$SECRET_FILE" ]]; then
		password=$(<"$SECRET_FILE")
	elif ! password=$(op_read "op://Personal/Duplicacy/backup_pwd"); then
		log "ERROR: ${SECRET_FILE} is unreadable and 1Password is locked or unreachable."
		return 1
	fi
	if [[ -z "$password" ]]; then
		log "ERROR: the storage password resolved to an empty value."
		return 1
	fi
	export DUPLICACY_PASSWORD="$password"
	# duplicacy looks for DUPLICACY_<STORAGE>_PASSWORD before falling back to
	# DUPLICACY_PASSWORD; both storages share the same password.
	export DUPLICACY_AEGIS_PASSWORD="$password"
}

# ~/.ssh/duplicacy is currently an unencrypted PKCS#8 key, so this is a no-op in
# practice. It is kept so that encrypting the key later needs no script change.
load_rsa_passphrase() {
	local passphrase
	if ! passphrase=$(op_read "op://Personal/Duplicacy/backup_rsa_pwd"); then
		log "WARNING: could not read the RSA passphrase from 1Password; continuing, the key is unencrypted."
		return 0
	fi
	export DUPLICACY_RSA_PASSPHRASE="$passphrase"
}

# duplicacy wants a PEM public key; ~/.ssh/duplicacy.pub is in OpenSSH format,
# which it rejects with "unrecognized public key". Derive the PEM form from the
# private key instead of storing a third copy of the key material: it cannot
# drift out of sync, and it is public data anyway.
# duplicacy only accepts a PKCS#1 private key ("BEGIN RSA PRIVATE KEY").
# ~/.ssh/duplicacy is PKCS#8 ("BEGIN PRIVATE KEY"), which it rejects outright
# with "Unsupported private key type PRIVATE KEY" — so restore and -files
# verification both failed silently until this was caught. Convert to a
# temporary 0600 file rather than changing what 1Password stores: identical key
# material, different PEM encoding. Callers must rm the returned path.
rsa_pkcs1_privkey() {
	local private_key="${HOME}/.ssh/duplicacy" pkcs1
	pkcs1=$(mktemp --tmpdir duplicacy-key-XXXXXX.pem) || return 1
	chmod 600 "$pkcs1"
	if ! openssl rsa -in "$private_key" -passin "pass:${DUPLICACY_RSA_PASSPHRASE:-}" \
		-traditional -out "$pkcs1" 2>/dev/null; then
		rm -f "$pkcs1"
		log "ERROR: could not convert ${private_key} to PKCS#1"
		return 1
	fi
	printf '%s' "$pkcs1"
}

rsa_pem_pubkey() {
	local private_key="${HOME}/.ssh/duplicacy" pem
	pem=$(mktemp --tmpdir duplicacy-pubkey-XXXXXX.pem) || return 1
	if ! openssl pkey -in "$private_key" -passin "pass:${DUPLICACY_RSA_PASSPHRASE:-}" -pubout -out "$pem" 2>/dev/null; then
		rm -f "$pem"
		log "ERROR: could not derive the PEM public key from ${private_key}"
		return 1
	fi
	printf '%s' "$pem"
}

cloud_available() {
	mountpoint -q "$CLOUD_MOUNT" && [[ -f "${CLOUD_MOUNT}/config" ]]
}

# The Aegis drive is removable. Its absence is a normal state, never an error.
aegis_available() {
	mountpoint -q "$AEGIS_MOUNT" && [[ -f "${AEGIS_STORAGE}/config" ]]
}

# Snapshot id for a repository, matching what duplicacy-setup writes:
# basename, lowercased, dot stripped, hostname appended for the config repo.
snapshot_id_for() {
	local folder="$1" name
	name=$(basename "$folder")
	name=${name#.}
	name=${name,,}
	if [[ "$name" == "config" ]]; then
		name="config_$(hostname)"
	fi
	printf '%s' "$name"
}

# Newest revision number for a snapshot id, or empty if there is none.
# Must be called from inside a repository.
latest_revision() {
	local id="$1" storage="$2" revision
	revision=$(duplicacy -background list -id "$id" -storage "$storage" 2>/dev/null | tail -n 1 | awk '{print $4}')
	[[ "$revision" =~ ^[0-9]+$ ]] && printf '%s' "$revision"
}

prune_logs() {
	fd . "$LOG_PATH" -e log --changed-before "${LOG_RETENTION_DAYS}d" -X rm
}

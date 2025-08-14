#!/usr/bin/env bash

# Prune old snapshots
export DUPLICACY_PASSWORD="MotDePasse"
export DUPLICACY_RSA_PASSPHRASE="MotDePasse"
BIN=$1

# 1 revision per day for a week, then 1 per week for a month then 1 per month after six months
cd "${HOME}/Images" || return
$BIN prune -threads 8 -keep 30:180 -keep 7:30 -keep 1:7 -all -exhaustive

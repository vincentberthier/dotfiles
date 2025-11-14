#!/usr/bin/env bash

# --- Generic window lookup -----------------------------------------------

lookup_window_exact() {
    local windows="$1"
    local title="$2"
    echo "$windows" | jq -r --arg t "$title" '
        .[] | select(.title == $t) | .id
    '
}

lookup_window_zen_prefix() {
    local windows="$1"
    local prefix="$2"
    echo "$windows" | jq -r --arg prefix "$prefix" '
        .[]
        | select(.app_id == "zen" and (.title | startswith($prefix)))
        | .id
    '
}

# --- Wait until a window appears ------------------------------------------

wait_for_window() {
    local lookup_func="$1"   # name of lookup function
    local title="$2"         # title or prefix
    local timeout="${3:-30}" # default timeout: 10s

    local id=""
    local windows=""
    local elapsed=0

    while (( elapsed < timeout )); do
        windows=$(niri msg -j windows)
        id=$($lookup_func "$windows" "$title")

        if [[ -n "$id" ]]; then
            echo "$id"
            return 0
        fi

        sleep 0.3
        ((elapsed++))
    done

    echo ""
    return 1
}

# --- Unified move function -------------------------------------------------

move_by_lookup() {
    local lookup_func="$1"
    local title="$2"
    local dest="$3"

    local id
    id=$(wait_for_window "$lookup_func" "$title" 10)

    if [[ -z "$id" ]]; then
        echo "Window '$title' not found after waiting"
        return 1
    fi

    echo "Moving window '$title' (id $id) → workspace '$dest'"
    niri msg action move-window-to-workspace --window-id "$id" "$dest"
}

# --- Shortcuts -------------------------------------------------------------

move_exact()     { move_by_lookup lookup_window_exact "$1" "$2"; }
move_zen_prefix() { move_by_lookup lookup_window_zen_prefix "$1" "$2"; }

# --- Main ------------------------------------------------------------------

sleep 2

move_exact      "󰚰 Update"  ""
move_exact      " Qobuz"   ""
move_zen_prefix "[General]" ""
move_zen_prefix "[Misc]"    ""
move_zen_prefix "[WebDev]"  "󰾔"

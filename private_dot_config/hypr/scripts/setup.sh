#!/usr/bin/env bash
# set -e

WEB=0

function move_floorp {
    readarray -t windows < <(hyprctl clients -j  | jq -r '[.[] | select((.initialClass == "floorp"))]' | jq -r '.[].address')
    if [ ${#windows[@]} -eq 0 ]; then return; fi
    # just as the windows are launched, the extension hasn’t yet set their names, so wait a bit
    sleep 15
    for w in "${windows[@]}"; do
        title=$(hyprctl clients -j |  jq -r '[.[] | select ((.address == "'"$w"'"))]' | jq -r '.[].title')
        workspace=$(echo "$title" | awk '{print $1}' | tr '[:upper:]' '[:lower:]' | grep -Eo '\w+')
        if [[ $(hostname) == "gaia" || $(hostname) == "hephaistos" ]]; then
            id="name:$workspace"

        else
            case "$workspace" in
                chat)    id=1 ;;
                general) id=2 ;;
                dev)     id=3 ;;
                misc)    id=4 ;;
                webdev)  id=5 ;;
                work)    id=6 ;;
                *)       return ;;
            esac

        fi
        hyprctl dispatch movetoworkspacesilent "$id",address:"$w"
    done
    WEB=1
}

sleep 2

RUST_WINDOWS=$(hyprctl clients -j | jq -r '[.[] | select ((.title | contains("") ))]' | jq -r '.[].address')

if [[ $(hostname) == "athena" ]]
    then
    hyprctl dispatch movetoworkspacesilent 2,address:"$(hyprctl clients -j | jq -r '[.[] | select ((.title == "󰚰 Update" ))]' | jq -r '.[].address' | head -n 1)"
    hyprctl dispatch movetoworkspacesilent 4,address:"$(hyprctl clients -j | jq -r '[.[] | select ((.title == "󰈺 Misc" ))]' | jq -r '.[].address' | head -n 1)"
    for id in $RUST_WINDOWS; do
        hyprctl dispatch movetoworkspacesilent 3,address:$id
    done
else
    hyprctl dispatch movetoworkspacesilent name:general,address:"$(hyprctl clients -j | jq -r '[.[] | select ((.title == "󰚰 Update" ))]' | jq -r '.[].address' | head -n 1)"
    hyprctl dispatch movetoworkspacesilent name:misc,address:"$(hyprctl clients -j | jq -r '[.[] | select ((.title == "󰈺 Misc" ))]' | jq -r '.[].address' | head -n 1)"
    for id in $RUST_WINDOWS; do
        hyprctl dispatch movetoworkspacesilent name:dev,address:$id
    done
fi

while [ $WEB == 0 ]; do
    move_floorp
    sleep 1
done

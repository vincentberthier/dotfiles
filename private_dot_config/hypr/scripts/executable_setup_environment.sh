#!/usr/bin/env bash
# set -e

WEB=0

function move_zen {
    readarray -t windows < <(hyprctl clients -j  | jq -r '[.[] | select((.initialClass == "zen"))]' | jq -r '.[].address')
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

if [[ $(hostname) == "athena" ]]
    then
    hyprctl dispatch movetoworkspacesilent 3,address:"$(hyprctl clients -j | jq -r '[.[] | select ((.title == "󰚰 Update" ))]' | jq -r '.[].address' | head -n 1)"
    hyprctl dispatch movetoworkspacesilent 4,address:"$(hyprctl clients -j | jq -r '[.[] | select ((.title == "󰈺 Misc" ))]' | jq -r '.[].address' | head -n 1)"
else
    hyprctl dispatch movetoworkspacesilent name:general,address:"$(hyprctl clients -j | jq -r '[.[] | select ((.title == "󰚰 Update" ))]' | jq -r '.[].address' | head -n 1)"
    hyprctl dispatch movetoworkspacesilent name:misc,address:"$(hyprctl clients -j | jq -r '[.[] | select ((.title == "󰈺 Misc" ))]' | jq -r '.[].address' | head -n 1)"
fi

while [ $WEB == 0 ]; do
    move_zen
    sleep 1
done

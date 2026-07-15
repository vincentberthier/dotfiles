function switch_wifi --description "Switches to another network. wpa_cli list_networks to get the list"
    wpa_cli select_network $argv[1]
end

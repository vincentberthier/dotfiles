function shx --wraps helix --description "Execute helix as root with user config"
    doas helix --config $XDG_CONFIG_HOME/helix/config.toml $argv
end

#!/usr/bin/env bash

# Get the list of sinks
sinks=($(wpctl status | awk '/Sinks:/,/Sources:/' | grep -Eo '[0-9]+\..*\[vol:' | awk '{print $1}' | tr -d '.'))
current_sink_line=$(wpctl status | awk '/Sinks:/,/Sources:/' | grep "*")

# Extract the current sink ID
current_sink=$(echo "$current_sink_line" | grep -Eo '[0-9]+' | head -1)

# Find the current sink index
current_index=-1
for i in "${!sinks[@]}"; do
    if [[ "${sinks[$i]}" == "$current_sink" ]]; then
        current_index=$i
        break
    fi
done
echo "sink: $current_sink at index $current_index"

# Calculate the next sink index
next_index=$(( (current_index + 1) % ${#sinks[@]} ))

# Set the next sink as default
wpctl set-default ${sinks[$next_index]}


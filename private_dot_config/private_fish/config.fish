if status is-interactive
    # Commands to run in interactive sessions can go here
end

zoxide init fish | source
# starship init fish | source

# Disable fish greetings
set -U fish_greeting

# Prompt navigation
function mark_prompt_start --on-event fish_prompt
    echo -en "\e]133;A\e\\"
end

# Vi mode
fish_vi_key_bindings
# Emulates vim's cursor shape behavior
# Set the normal and visual mode cursors to a block
set fish_cursor_default block
# Set the insert mode cursor to a line
set fish_cursor_insert line
# Set the replace mode cursor to an underscore
set fish_cursor_replace_one underscore
# The following variable can be used to configure cursor shape in
# visual mode, but due to fish_cursor_default, is redundant here
set fish_cursor_visual block

if test -f /usr/bin/python3 
    please 2> /dev/null
end

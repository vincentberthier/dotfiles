local status, telescope = pcall(require, 'telescope')
if not status then
    vim.notify("Failed to load Telescope")
    return
end

telescope.load_extension("media_files")

local builtin = require "telescope.builtin"
local actions = require "telescope.actions"
local opts = { noremap = true, silent = true }

telescope.setup {
    defaults = {
        prompt_prefix = " ",
        selection_caret = " ",
        path_display = { "smart" },

        mappings = {
            i = {
                ["<C-n>"] = actions.cycle_history_next,
                ["<C-p>"] = actions.cycle_history_prev,

                ["<C-s>"] = actions.move_selection_next,
                ["<C-r>"] = actions.move_selection_previous,

                ["<C-c>"] = actions.close,

                ["<Down>"] = actions.move_selection_next,
                ["<Up>"] = actions.move_selection_previous,

                ["<CR>"] = actions.select_default,
                ["<C-x>"] = actions.select_horizontal,
                ["<C-v>"] = actions.select_vertical,
                ["<C-t>"] = actions.select_tab,

                ["<C-u>"] = actions.preview_scrolling_up,
                ["<C-d>"] = actions.preview_scrolling_down,

                ["<PageUp>"] = actions.results_scrolling_up,
                ["<PageDown>"] = actions.results_scrolling_down,

                ["<Tab>"] = actions.toggle_selection + actions.move_selection_worse,
                ["<S-Tab>"] = actions.toggle_selection + actions.move_selection_better,
                ["<C-q>"] = actions.send_to_qflist + actions.open_qflist,
                ["<M-q>"] = actions.send_selected_to_qflist + actions.open_qflist,
                ["<C-l>"] = actions.complete_tag,
                ["<C-_>"] = actions.which_key, -- keys from pressing <C-/>
            },

            n = {
                ["<esc>"] = actions.close,
                ["<CR>"] = actions.select_default,
                ["<C-x>"] = actions.select_horizontal,
                ["<C-v>"] = actions.select_vertical,
                ["<C-t>"] = actions.select_tab,

                ["<Tab>"] = actions.toggle_selection + actions.move_selection_worse,
                ["<S-Tab>"] = actions.toggle_selection + actions.move_selection_better,
                ["<C-q>"] = actions.send_to_qflist + actions.open_qflist,
                ["<M-q>"] = actions.send_selected_to_qflist + actions.open_qflist,

                ["s"] = actions.move_selection_next,
                ["r"] = actions.move_selection_previous,
                ["T"] = actions.move_to_top,
                ["M"] = actions.move_to_middle,
                ["N"] = actions.move_to_bottom,

                ["<Down>"] = actions.move_selection_next,
                ["<Up>"] = actions.move_selection_previous,
                ["gg"] = actions.move_to_top,
                ["G"] = actions.move_to_bottom,

                ["<C-u>"] = actions.preview_scrolling_up,
                ["<C-d>"] = actions.preview_scrolling_down,

                ["<PageUp>"] = actions.results_scrolling_up,
                ["<PageDown>"] = actions.results_scrolling_down,

                ["?"] = actions.which_key,
            },
        },
    },
    -- pickers = {
    -- Default configuration for builtin pickers goes here:
    -- picker_name = {
    --   picker_config_key = value,
    --   ...
    -- }
    -- Now the picker_config_key will be applied every time you call this
    -- builtin picker
    -- },
    extensions = {
        media_files = {
            -- filetypes whitelist
            -- defaults to {"png", "jpg", "mp4", "webm", "pdf"}
            filetypes = { "png", "webp", "jpg", "jpeg" },
            find_cmd = "rg" -- find command (defaults to `fd`)
        }
        -- Your extension configuration goes here:
        -- extension_name = {
        --   extension_config_key = value,
        -- }
        -- please take a look at the readme of the extension you want to configure
    },
}

-- Find files
vim.keymap.set("n", "<leader>f",
    "<cmd>lua require'telescope.builtin'.find_files(require('telescope.themes').get_dropdown({ previewer = false }))<CR>"
    , opts)
vim.keymap.set('n', '<leader>tf', builtin.find_files, opts)
vim.keymap.set('n', '<leader>ts', builtin.live_grep, opts)
vim.keymap.set('n', '<C-p>', builtin.git_files, opts)

-- Vim pickers
vim.keymap.set("n", "<leader>tb", builtin.buffers, opts)
vim.keymap.set("n", "<leader>tk", builtin.keymaps, opts)

-- LSP stuff
vim.keymap.set("n", "<leader>tlr", builtin.lsp_references, opts)
vim.keymap.set("n", "<leader>tld", builtin.diagnostics, opts)
vim.keymap.set("n", "<leader>tls", builtin.lsp_document_symbols, opts)
vim.keymap.set("n", "<leader>tlw", builtin.lsp_workspace_symbols, opts)

-- Git stuff
vim.keymap.set("n", "<leader>tgc", builtin.git_commits, opts)
vim.keymap.set("n", "<leader>tgb", builtin.git_branches, opts)
vim.keymap.set("n", "<leader>tgs", builtin.git_status, opts)

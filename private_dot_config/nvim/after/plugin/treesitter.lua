local status, configs = pcall(require, "nvim-treesitter.configs")
if not status then
    vim.notify("Failed to load Treesitter")
    return
end

configs.setup {
    -- A list of parser names, or "all"
    ensure_installed = "all",

    -- Install parsers synchronously (only applied to `ensure_installed`)
    sync_install = false,

    -- Automatically install missing parsers when entering buffer
    -- Recommendation: set to false if you don't have `tree-sitter` CLI installed locally
    auto_install = true,

    -- List of parsers to ignore installing (for "all")
    ignore_install = { "awk", "elm", "fortran", "hack", "haskell", "mermaid", "nickel", "org" },

    autopairs = {
        enable = true,
    },
    highlight = {
        -- `false` will disable the whole extension
        enable = true,
        disable = { "" },

        -- Setting this to true will run `:h syntax` and tree-sitter at the same time.
        -- Set this to `true` if you depend on 'syntax' being enabled (like for indentation).
        -- Using this option may slow down your editor, and you may see some duplicate highlights.
        -- Instead of true it can also be a list of languages
        additional_vim_regex_highlighting = true,
    },
    indent = { enable = true, disable = { "" } },
    rainbow = {
        enable = true,
        -- disable = {},
        extended_mode = true,  -- also highlight non-bracket delimiters like html tags
        max_file_lines = nil,  -- do not enable for files more than N lines
        -- colors = {}, -- table of hex strings
        -- termcolors = {}, -- table of colour name strings
    },
    context_commentstring = {
        enable = true,
        enable_autocmd = false,
    }
}

-- Treesitter folding 
vim.wo.foldmethod = 'expr'
vim.wo.foldexpr = 'nvim_treesitter#foldexpr()'

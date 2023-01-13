vim.g.mapleader = " "
vim.g.maplocalleader = " "

-- menuone: popup even when there's only one match
-- noinsert: Do not insert text until a selection is made
-- noselect: Do not auto-select, nvim-cmp plugin will handle this for us.
vim.o.completeopt = "menuone,noinsert,noselect"

local lsp = require("lsp-zero")

lsp.preset("recommended")

lsp.ensure_installed({
    'sumneko_lua',
})

-- Fix Undefined global 'vim'
lsp.configure('sumneko_lua', {
    settings = {
        Lua = {
            diagnostics = {
                globals = { 'vim' }
            }
        }
    }
})
-- add common json schemas
lsp.configure("jsonls", require("user.lsp.settings.jsonls").opts)

local cmp_status, cmp = pcall(require, "cmp")
if not cmp_status then
    vim.notify("failed to load cmp")
    return
end

local snip_status, luasnip = pcall(require, "luasnip")
if not snip_status then
    vim.notify("failed to load luasnip")
    return
end

require("luasnip/loaders/from_vscode").lazy_load()

--   פּ ﯟ   some other good icons
local kind_icons = {
    Text = "",
    Method = "m",
    Function = "",
    Constructor = "",
    Field = "",
    Variable = "",
    Class = "",
    Interface = "",
    Module = "",
    Property = "",
    Unit = "",
    Value = "",
    Enum = "",
    Keyword = "",
    Snippet = "",
    Color = "",
    File = "",
    Reference = "",
    Folder = "",
    EnumMember = "",
    Constant = "",
    Struct = "",
    Event = "",
    Operator = "",
    TypeParameter = "",
}

local check_backspace = function()
    local col = vim.fn.col "." - 1
    return col == 0 or vim.fn.getline("."):sub(col, col):match "%s"
end

local cmp_select = { behavior = cmp.SelectBehavior.Select }
local cmp_mappings = lsp.defaults.cmp_mappings({
    ['<C-d>'] = cmp.mapping.select_prev_item(cmp_select),
    ['<C-l>'] = cmp.mapping.select_next_item(cmp_select),
    ['<C-y>'] = cmp.mapping.confirm({ select = false }),
    ["<C-Space>"] = cmp.mapping.complete(),
    ["<C-e>"] = cmp.mapping {
        i = cmp.mapping.abort(),
        c = cmp.mapping.close(),
    },
    ["<Tab>"] = cmp.mapping(function(fallback)
        if cmp.visible() then
            cmp.select_next_item()
        elseif luasnip.expandable() then
            luasnip.expand()
        elseif luasnip.expand_or_jumpable() then
            luasnip.expand_or_jump()
        elseif check_backspace() then
            fallback()
        else
            fallback()
        end
    end, {
        "i",
        "s",
    }),
    ["<S-Tab>"] = cmp.mapping(function(fallback)
        if cmp.visible() then
            cmp.select_prev_item()
        elseif luasnip.jumpable(-1) then
            luasnip.jump(-1)
        else
            fallback()
        end
    end, {
        "i",
        "s",
    }),
})

-- disabble completion with tab
-- cmp_mappings["<Tab>"] = nil
-- cmp_mappings["<S-Tab>"] = nil

lsp.setup_nvim_cmp({
    snippet = {
        expand = function(args)
            luasnip.lsp_expand(args.body) -- for luasnip users
        end,
    },
    mapping = cmp_mappings,
    formatting = {
        fields = { "kind", "abbr", "menu" },
        format = function(entry, vim_item)
            -- kind icons
            vim_item.kind = string.format("%s %s", kind_icons[vim_item.kind], vim_item.kind)
            vim_item.menu = ({

                luasnip = "⋗",
                buffer = "Ω",
                path = "🖫",
                nvim_lsp = "λ",
                nvim_lua = "識",
            })[entry.source.name]
            return vim_item
        end,
    },
    sources = {
        { name = "nvim_lsp" },
        { name = "nvim_lua" },
        { name = "luasnip" },
        { name = "buffer" },
        { name = "path" },
    },

})

lsp.set_preferences({
    suggest_lsp_servers = false,
    sign_icons = {
        error = "",
        warn = "",
        hint = "",
        info = "",
    }
})

---------------------------
--   Navic configuraton  --
---------------------------
local navic_status, navic = pcall(require, "nvim-navic")
if not navic_status then
    vim.notify("nvim-navic was not found. Disabling it in statusline")
end
navic.setup {
        icons = {
        File          = " ",
        Module        = " ",
        Namespace     = " ",
        Package       = " ",
        Class         = " ",
        Method        = " ",
        Property      = " ",
        Field         = " ",
        Constructor   = " ",
        Enum          = "練",
        Interface     = "練",
        Function      = " ",
        Variable      = " ",
        Constant      = " ",
        String        = " ",
        Number        = " ",
        Boolean       = "◩ ",
        Array         = " ",
        Object        = " ",
        Key           = " ",
        Null          = "ﳠ ",
        EnumMember    = " ",
        Struct        = " ",
        Event         = " ",
        Operator      = " ",
        TypeParameter = " ",
    },
    highlight = false,
    separator = " > ",
    depth_limit = 0,
    depth_limit_indicator = "..",
    safe_output = true
}

local function on_attach(client, bufnr)
    local opts = { buffer = bufnr, remap = false }

    if client.name == "eslint" then
        vim.cmd.LspStop('eslint')
        return
    end
    if navic_status and client.server_capabilities.documentSymbolProvider then
        navic.attach(client, bufnr)
    end

    vim.keymap.set("n", "gd", vim.lsp.buf.definition, opts)
    --    vim.keymap.set("n", "gD", vim.lsp.buf.declarations, opts)
    vim.keymap.set("n", "gi", vim.lsp.buf.implementation, opts)
    --    vim.keymap.set("n", "gr", vim.lsp.buf.references, opts)
    vim.keymap.set("n", "gr", "<nop>", opts)
    vim.keymap.set("n", "K", vim.lsp.buf.hover, opts)
    vim.keymap.set("n", "<leader>vws", vim.lsp.buf.workspace_symbol, opts)
    vim.keymap.set("n", "gl", vim.diagnostic.open_float, opts)
    vim.keymap.set("n", "[d", vim.diagnostic.goto_next, opts)
    vim.keymap.set("n", "]d", vim.diagnostic.goto_prev, opts)
    vim.keymap.set("n", "<leader>ca", vim.lsp.buf.code_action, opts)
    vim.keymap.set("n", "<leader>rn", vim.lsp.buf.rename, opts)
    vim.keymap.set("i", "<C-h>", vim.lsp.buf.signature_help, opts)
    vim.keymap.set("n", "<leader>lf", vim.lsp.buf.format, opts)
end

lsp.on_attach(on_attach)

lsp.setup()

vim.diagnostic.config({
    virtual_text = true,
})

local status, rust = pcall(require, "rust-tools")
if not status then
    vim.notify("Could not load Rust tools in LSP")
    return
end

rust.setup({
    server = {
        on_attach = function(client, bufnr)
            local opts = { buffer = bufnr, remap = false }
            on_attach(client, bufnr)
            -- Rust hover actions
            vim.keymap.set("n", "<C-space>", rust.hover_actions.hover_actions, opts)
            -- Rust code actions
            vim.keymap.set("n", "<leader>a", rust.code_action_group.code_action_group, opts)
        end,
    },
})



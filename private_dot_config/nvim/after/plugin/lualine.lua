local status, lualine = pcall(require, "lualine")
if not status then
    vim.notify("Lualine not found.")
    return
end

local function get_spaces()
    return "" .. vim.api.nvim_buf_get_option(0, "shiftwidth") .. " spaces"
end

local function diff_source()
    local gitsigns = vim.b.gitsigns_status_dict
    if gitsigns then
        return {
            added = gitsigns.added,
            modified = gitsigns.changed,
            removed = gitsigns.removed,
        }
    end
end

local diff = {
    "diff",
    source = diff_source,
    symbols = {
        added = " ",
        modified = " ",
        removed = " ",
    },
    padding = { left = 2, right = 1 },
    diff_color = {
        added = { fg = "#98be65" },
        modified = { fg = "#ECBE7B" },
        removed = { fg = "#ec5f67" },
    },
    cond = nil,
}

local diagnostics = {
    "diagnostics",
    sources = { "nvim_diagnostic" },
    symbols = {
        error = " ",
        warn = " ",
        info = " ",
        hint = " ",
    },
    -- cond = conditions.hide_in_width,
}

local lsp = {
    function(msg)
        msg = msg or "LS Inactive"
        local buf_clients = vim.lsp.buf_get_clients()
        if next(buf_clients) == nil then
            if type(msg) == "boolean" or #msg == 0 then
                return "LS Inactive"
            end
            return msg
        end
        local buf_ft = vim.bo.filetype
        local buf_client_names = {}
        local copilot_active = false

        -- add client
        for _, client in pairs(buf_clients) do
            if client.name ~= "null-ls" and client.name ~= "copilot" then
                table.insert(buf_client_names, client.name)
            end

            if client.name == "copilot" then
                copilot_active = true
            end
        end

        -- add formatter
        local formatters = require "lvim.lsp.null-ls.formatters"
        local supported_formatters = formatters.list_registered(buf_ft)
        vim.list_extend(buf_client_names, supported_formatters)

        -- add linter
        local linters = require "lvim.lsp.null-ls.linters"
        local supported_linters = linters.list_registered(buf_ft)
        vim.list_extend(buf_client_names, supported_linters)

        local unique_client_names = vim.fn.uniq(buf_client_names)

        local language_servers = "[" .. table.concat(unique_client_names, ", ") .. "]"

        if copilot_active then
            language_servers = language_servers .. "%#SLCopilot#" .. " %*"
        end

        return language_servers
    end,
    color = { gui = "bold" },
    cond = function()
        return vim.o.columns > 100
    end,
}

lualine.setup {
    options = {
        icons_enabled = true,
        theme = "iceberg_dark",
        always_divide_middle = false,
        globalstatus = true,
    },
    sections = {
        lualine_a = { 'mode' },
        lualine_b = { 'branch', diff },
        lualine_c = { 'filename', diagnostics, lsp },
        lualine_x = { get_spaces, 'encoding', 'fileformat', 'filetype' },
        lualine_y = { 'progress' },
        lualine_z = { 'location' }
    },
}

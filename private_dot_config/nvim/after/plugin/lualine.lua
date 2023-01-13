local status, lualine = pcall(require, "lualine")
if not status then
    vim.notify("Lualine not found.")
    return
end

local navic_status, navic = pcall(require, "lualine")
if not navic_status then
    vim.notify("Navic not found, disabling statusline")
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

-- Taken from https://github.com/LunarVim/LunarVim/blob/master/lua/lvim/core/lualine/components.lua
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

local function navic_line()
    local res = ""
    if navic_status and navic.is_available() then
        res = navic.get_location()
    end
    return res
end

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
        lualine_c = { 'filename' },
        lualine_x = { diagnostics, lsp, get_spaces, 'filetype' },
        lualine_y = { 'progress' },
        lualine_z = { 'location' }
    },
    tabline = {
        lualine_a = { "buffers" },
        lualine_z = { "tabs" }
    },
    winbar = {
        lualine_a = {},
        lualine_b = {"filename"},
        lualine_c = {navic_line},
        lualine_x = {},
        lualine_y = {},
        lualine_z = {},
    }
}

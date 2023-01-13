local status, lualine = pcall(require, "lualine")
if not status then
    vim.notify("Lualine not found.")
    return
end
local sign_icons = {
        error = "",
        warn = "",
        hint = "",
        info = "",
    }

local function get_spaces()
    return "" .. vim.api.nvim_buf_get_option(0, "shiftwidth") .. " spaces"
end

local function diagnostics()
    local diags = require'lualine.components.diagnostics.'.get_diagnostics{'nvim_lsp'}[1]
    local res = ""
    if diags.error > 0 then
        res = res .. " " .. diags.error .. sign_icons.error
    end
    if diags.warn > 0 then
        res = res .. " " .. diags.warn .. sign_icons.warn
    end
    if diags.hint > 0 then
        res = res .. " " .. diags.hint .. sign_icons.hint
    end
    if diags.info > 0 then
        res = res .. " " .. diags.info .. sign_icons.info
    end
    return res:sub(1)
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

local git_diff_symbols = {
    LineAdded = "",
    LineModified = "",
    LineRemoved = "",
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
        lualine_b = { 'branch', { 'diff', source = diff_source, symbols = git_diff_symbols } },
        lualine_c = { 'filename', diagnostics },
        lualine_x = { get_spaces, 'encoding', 'fileformat', 'filetype' },
        lualine_y = { 'progress' },
        lualine_z = { 'location' }
    },
}



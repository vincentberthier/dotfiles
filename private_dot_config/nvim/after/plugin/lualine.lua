local status, lualine = pcall(require, "lualine")
if not status then
    vim.notify("Lualine not found.")
    return
end

local function get_spaces()
    return "" .. vim.api.nvim_buf_get_option(0, "shiftwidth") .. " spaces"
end

lualine.setup {
    options = {
        icons_enabled = true,
        theme = "iceberg_dark",
        sections = {
            lualine_x = {'encoding', 'fileformat', 'filetype'}
        }
    },
}

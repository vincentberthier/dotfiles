local status, lualine = pcall(require, "lualine")
if not status then
    vim.notify("Lualine not found.")
    return
end

lualine.setup {
    options = {
        icons_enabled = true,
        theme = "iceberg_dark",

    }
}

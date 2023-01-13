local status, headers = pcall(require, "auto-headers")
if not status then
    vim.notify("Missing auto-headers plugin.")
    return
end

headers.setup({
    projects = {
        {
            project_name = "auto-header.nvim",
            root = "/home/vincent/code/auto-header.nvim",
            create = false,
            update = true,
            template = {
                "File: #file_relative_path",
                "Project: #project_name",
                "Creation date: #date_now",
                "Author: #author_name",
                "-----",
                "Last modified: #date_now",
                "Modified By: #author_name",
                "-----",
                headers.licenses.MIT,
            },
            data = {
                cp_holders = "Vincent Berthier",
                author_mail = ""
            }
        }
    }
})

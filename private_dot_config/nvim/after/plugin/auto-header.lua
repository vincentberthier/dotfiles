local status, headers = pcall(require, "auto-header")
if not status then
    vim.notify("Missing auto-header plugin.")
    return
end

headers.setup({
    templates = {
        {
            language = "rust",
            prefix = "// ",
            block = "",
            block_length = 0,
            before = {},
            after = { "",
                "//! # crate_name",
                "//!",
                "//! Crate description",
                "" },
            template = {
                "File: #file_relative_path",
                "Project: #project_name",
                "Creation date: #date_now",
                "Author: #author_name <#author_mail>",
                "-----",
                "Last modified: #date_now",
                "Modified By: #author_name",
                "-----",
                "Copyright © #cp_year <#author_name> - All rights reserved"
            },
            track_change = {
                "File: ",
                "Last modified: ",
                "Modified By: ",
                "Copyright ",
            },
        }

    },
    projects = {
        {
            project_name = "Vincent’s projects",
            root = "/home/vincent/code/",
            create = true,
            update = true,
            data = {
                cp_holders = "Vincent Berthier",
                author_mail = "vincent.berthier@posteo.org",
            },
        },
        {
            project_name = "Athena’s Crucible",
            root = "/home/vincent/code/athena_crucible/",
            create = true,
            update = true,
            data = {
                cp_holders = "Vincent Berthier",
                author_mail = "vincent.berthier@posteo.org",
            }
        },
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

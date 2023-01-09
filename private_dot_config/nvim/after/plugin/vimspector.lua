vim.g.leader = " "

vim.g.vimspector_sidebar_width = 85
vim.g.vimspector_sidebar_height = 15
vim.g.vimspector_terminal_maxwidth = 70

vim.keymap.set("n", "<F9>", "<cmd>call vimspector#Launch()<CR>")
vim.keymap.set("n", "<F5>", "<cmd>call vimspector#StepOver()<CR>")
vim.keymap.set("n", "<F8>", "<cmd>call vimspector#Reset()<CR>")
vim.keymap.set("n", "<F11>", "<cmd>call vimspector#StepOver()<CR>")
vim.keymap.set("n", "<F12>", "<cmd>call vimspector#StepOut()<CR>")
vim.keymap.set("n", "<F10>", "<cmd>call vimspector#StepInto()<CR>")

vim.keymap.set("n", "<leader>Db", "<cmd>call vimspector#ToggleBreakpoint()<CR>")
vim.keymap.set("n", "<leader>Dw", "<cmd>call vimspector#AddWatch()<CR>")
vim.keymap.set("n", "<leader>De", "<cmd>call vimspector#Evaluate()<CR>")


-- Bépo layout related keymaps
local keymap = vim.api.nvim_set_keymap
local opts = { noremap = true, silent = true }

-- Moving keys
keymap("n", "t", "h", opts) -- previous character
keymap("n", "s", "j", opts) -- next line
keymap("n", "r", "k", opts) -- previous line
keymap("n", "n", "l", opts) -- next character
keymap("n", "k", "r", opts) -- replace
keymap("v", "t", "h", opts) -- previous character
keymap("v", "s", "j", opts) -- next line
keymap("v", "r", "k", opts) -- previous line
keymap("v", "n", "l", opts) -- next character
keymap("x", "t", "h", opts) -- previous character
keymap("x", "s", "j", opts) -- next line
keymap("x", "r", "k", opts) -- previous line
keymap("x", "n", "l", opts) -- next character

-- Window navigation
keymap("n", "<C-t>", "<C-w>h", opts) -- Go to left Window
keymap("n", "<C-s>", "<C-w>j", opts) -- Go to bottow Window
keymap("n", "<C-r>", "<C-w>k", opts) -- Go to up Window
keymap("n", "<C-n>", "<C-w>l", opts) -- Go to right Window

--[[ keymap("t", "<C-t>", "<C-\\><C-N><C-w>h", term_opts) -- Go to terminal left Window ]]
--[[ keymap("t", "<C-s>", "<C-\\><C-N><C-w>j", term_opts) -- Go to terminal bottow Window ]]
--[[ keymap("t", "<C-r>", "<C-\\><C-N><C-w>k", term_opts) -- Go to terminal up Window ]]
--[[ keymap("t", "<C-n>", "<C-\\><C-N><C-w>l", term_opts) -- Go to terminal right Window ]]

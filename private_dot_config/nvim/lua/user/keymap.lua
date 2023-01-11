local opts = { noremap = true, silent = true }
--[[ local term_opts = { silent = true } ]]

-- Alias
local keymap = vim.api.nvim_set_keymap

-- Space is leader key
keymap("", "<Space>", "<nop>", opts)
vim.g.mapleader = " "
vim.g.maplocalleader = " "

vim.g.clipboard = {
    name = "wl-clipboard",
    copy = { ["+"] = { "wl-copy" }, ["*"] = { "wl-copy"} },
    paste = { ["+"] = { "wl-paste"}, ["*"] = { "wl-paste"}},
    cache_enabled = true,
}

-- Modes
--   normal mode = "n"
--   insert mode = "i"
--   visual mode = "v"
--   visual block mode = "x",
--   term mode = "t"
--   command mode = "c"

-- BÉPO remaps of standard keys
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

keymap("n", "<leader>e", ":NvimTreeToggle<CR>", opts) -- Toggles netrw in a left bar

-- Resize split windows
keymap("n", "<C-Up>", ":resize +2<CR>", opts)
keymap("n", "<C-Down>", ":resize -2<CR>", opts)
keymap("n", "<C-Left>", ":vertical resize -2<CR>", opts)
keymap("n", "<C-Right>", ":vertical resize +2<CR>", opts)

-- Navigate in buffers
keymap("n", "<S-n>", ":bnext<CR>", opts)
keymap("n", "<S-t>", ":bprevious<CR>", opts)
keymap("n", "<S-c>", ":Bdelete<CR>", opts)

-- Escape insert mode fast
keymap("i", "vd", "<Esc>", opts)

-- Stay in indent mode
keymap("v", "<", "<gv", opts)
keymap("v", ">", ">gv", opts)

-- Show / hide the undo tree
keymap("n", "<leader>u", ":UndotreeShow<CR>", opts)

-- Move selected lines up or down
keymap("v", "<A-s>", ":m '>+1<cr>gv=gv", opts)
keymap("v", "<A-r>", ":m '<-2<cr>gv=gv", opts)
keymap("x", "<A-s>", ":move '>+1<CR>gv-gv", opts)
keymap("x", "<A-r>", ":m '<-2<CR>gv-gv", opts)

--
keymap("n", "Y", "yg$", opts)
-- Append the next line to the current one after a spaces
keymap("n", "J", "mzJ`z", opts)
-- Keep the cursor in the middle while scrolling
keymap("n", "<C-d>", "<C-d>zz", opts)
keymap("n", "<C-u>", "<C-u>zz", opts)
-- Keep the cursor in the middle of the screen while searching for terms
keymap("n", "l", "nzzzv", opts)
keymap("n", "L", "Nzzzv", opts)

-- Paste over while keeping current copied data
keymap("x", "<leader>p", [["_dP]], opts)

-- Copy to clipboard
keymap("n", "<leader>y", [["+y]], opts)
keymap("v", "<leader>y", [["+y]], opts)
keymap("n", "<leader>Y", [["+Y]], opts)

keymap("n", "<leader>d", [["_d]], opts)
keymap("v", "<leader>d", [["_d]], opts)

-- Disable Q
keymap("n", "Q", "<nop>", opts)

-- Go to another session
keymap("n", "<C-f>", "<cmd>silent !tmux neww tmux-sessionizer<CR>", opts)

-- Quick fix navigation??
--keymap("n", "<C-s>", "<cmd>cnext<CR>zz", opts)
--keymap("n", "<C-r>", "<cmd>cprev<CR>zz", opts)
keymap("n", "<leader>t", "<cmd>lnext<CR>zz", opts)
keymap("n", "<leader>n", "<cmd>lprev<CR>zz", opts)

-- Replace current word in buffer
vim.keymap.set("n", "<leader>s", [[:%s/\<<C-r><C-w>\>/<C-r><C-w>/gI<Left><Left><Left>]])
vim.keymap.set("n", "<leader>x", "<cmd>!chmod +x %<CR>", { silent = true })


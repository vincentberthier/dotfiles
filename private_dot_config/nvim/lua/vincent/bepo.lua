-- Bépo layout related keymaps
local keymap = vim.api.nvim_set_keymap
local opts = { noremap = true, silent = true }

-- Moving keys
keymap("n", "t", "h", opts) -- previous character
keymap("n", "s", "j", opts) -- next line
keymap("n", "r", "k", opts) -- previous line
keymap("n", "n", "l", opts) -- next character
keymap("v", "t", "h", opts) -- previous character
keymap("v", "s", "j", opts) -- next line
keymap("v", "r", "k", opts) -- previous line
keymap("v", "n", "l", opts) -- next character
keymap("x", "t", "h", opts) -- previous character
keymap("x", "s", "j", opts) -- next line
keymap("x", "r", "k", opts) -- previous line
keymap("x", "n", "l", opts) -- next character

-- Remap the keys changed by the movement keys
keymap("n", "h", "t", opts)
keymap("n", "<S-h>", "<S-t>", opts)
keymap("v", "h", "t", opts)
keymap("v", "<S-h>", "<S-t>", opts)
keymap("x", "h", "t", opts)
keymap("x", "<S-h>", "<S-t>", opts)
keymap("o", "h", "t", opts)
keymap("o", "<S-h>", "<S-t>", opts)
keymap("n", "j", "s", opts)
keymap("n", "<S-s>", "mzJ`z", opts) -- Append the next line to the current one after a space
keymap("v", "j", "s", opts)
keymap("v", "<S-s>", "mzJ`z", opts) -- Append the next line to the current one after a space
keymap("x", "j", "s", opts)
keymap("x", "<S-s>", "mzJ`z", opts) -- Append the next line to the current one after a space
keymap("o", "j", "s", opts)
keymap("o", "<S-s>", "mzJ`z", opts) -- Append the next line to the current one after a space
keymap("n", "k", "r", opts)
keymap("n", "<S-k>", "<S-r>", opts)
keymap("v", "k", "r", opts)
keymap("v", "<S-k>", "<S-r>", opts)
keymap("x", "k", "r", opts)
keymap("x", "<S-k>", "<S-r>", opts)
keymap("o", "k", "r", opts)
keymap("o", "<S-k>", "<S-r>", opts)
keymap("n", "l", "nzzzv", opts) -- Keep the cursor in the middle of the screen while searching for terms
keymap("n", "<S-l>", "Nzzzv", opts) -- Keep the cursor in the middle of the screen while searching for terms

-- Window navigation
keymap("n", "<C-t>", "<C-w>h", opts) -- Go to left Window
keymap("n", "<C-s>", "<C-w>j", opts) -- Go to bottow Window
keymap("n", "<C-r>", "<C-w>k", opts) -- Go to up Window
keymap("n", "<C-n>", "<C-w>l", opts) -- Go to right Window

-- Navigate in buffers
keymap("n", "<leader>bn", ":bnext<CR>", opts)
keymap("n", "<leader>bt", ":bprevious<CR>", opts)

keymap("n", "<leader>tn", ":tabn<CR>", opts) -- go to next tab
keymap("n", "<leader>tt", ":tabn<CR>", opts) -- go to previous tab

-- Escape insert mode fast
keymap("i", "vd", "<Esc>", opts)

-- Redo
keymap("n", "<C-K>", "<c-r>", opts)

-- Move selected lines up or down
keymap("v", "<A-s>", ":m '>+1<cr>gv=gv", opts)
keymap("v", "<A-r>", ":m '<-2<cr>gv=gv", opts)
keymap("x", "<A-s>", ":move '>+1<CR>gv-gv", opts)
keymap("x", "<A-r>", ":m '<-2<CR>gv-gv", opts)

keymap("n", "<leader>t", "<cmd>lnext<CR>zz", opts) -- go to previous error
keymap("n", "<leader>n", "<cmd>lprev<CR>zz", opts) -- go to next error

-- Vim-Tmux
keymap("n", "C-t", "<cmd>TmuxNavigateLeft<CR>", opts)
keymap("n", "C-s", "<cmd>TmuxNavigateDown<CR>", opts)
keymap("n", "C-r", "<cmd>TmuxNavigateUp<CR>", opts)
keymap("n", "C-n", "<cmd>TmuxNavigateRight<CR>", opts)
keymap("n", "C-'", "<cmd>TmuxNavigatePrevious<CR>", opts)

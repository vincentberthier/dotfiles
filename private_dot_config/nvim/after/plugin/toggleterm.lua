local status_ok, toggleterm = pcall(require, "toggleterm")
if not status_ok then
	return
end

toggleterm.setup({
	size = 20,
	open_mapping = "<leader>x",
	hide_numbers = true,
	shade_filetypes = {},
	shade_terminals = true,
	shading_factor = 2,
	start_in_insert = true,
	insert_mappings = true,
	persist_size = true,
	direction = "float",
	close_on_exit = true,
	shell = "zsh",
	float_opts = {
		border = "curved",
		winblend = 0,
		highlights = {
			border = "Normal",
			background = "Normal",
		},
	},
})

function _G.set_terminal_keymaps()
	local opts = { noremap = true }
	vim.api.nvim_buf_set_keymap(0, "t", "<esc>", [[<C-\><C-n>]], opts)
	vim.api.nvim_buf_set_keymap(0, "t", "vd", [[<C-\><C-n>]], opts)
	vim.api.nvim_buf_set_keymap(0, "t", "<C-x>", [[<cmd>wincmd h<CR>]], opts)
	vim.api.nvim_buf_set_keymap(0, "t", "<C-s>", [[<cmd>wincmd j<CR>]], opts)
	vim.api.nvim_buf_set_keymap(0, "t", "<C-k>", [[<cmd>wincmd k<CR>]], opts)
	vim.api.nvim_buf_set_keymap(0, "t", "<C-l>", [[<cmd>wincmd l<CR>]], opts)
end

vim.cmd("autocmd! TermOpen term://* lua set_terminal_keymaps()")

local Terminal = require("toggleterm.terminal").Terminal
local lazygit = Terminal:new({ cmd = "lazygit", hidden = true })

function _LAZYGIT_TOGGLE()
	lazygit:toggle()
end

local python = Terminal:new({ cmd = "ipython3", hidden = true })

function _PYTHON_TOGGLE()
	python:toggle()
end

local ncdu = Terminal:new({ cmd = "ncdu", hidden = true })

function _NCDU_TOGGLE()
	ncdu:toggle()
end

local htop = Terminal:new({ cmd = "htop", hidden = true })

function _HTOP_TOGGLE()
	htop:toggle()
end

vim.api.nvim_set_keymap("n", "<C-x><C-p>", "<cmd>lua _PYTHON_TOGGLE()<CR>", { noremap = true, silent = true })
vim.api.nvim_set_keymap("n", "<C-x><C-t>", "<cmd>lua _HTOP_TOGGLE()<CR>", { noremap = true, silent = true })
vim.api.nvim_set_keymap("n", "<C-x><C-h>", "<cmd>lua _NCDU_TOGGLE()<CR>", { noremap = true, silent = true })

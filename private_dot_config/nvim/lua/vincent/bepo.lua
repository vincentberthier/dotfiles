-- Bépo layout related keymaps
local keymap = vim.api.nvim_set_keymap
local opts = { noremap = true, silent = true }

local status_wk, wk = pcall(require, "which-key")
if not status_wk then
	print("Could not load which-key: default keymaps")
	return
end

local motions = {
	["t"] = { "h", "Left" },
	["T"] = { "H", "Screen top" },
	["s"] = { "j", "Up" },
	["S"] = { "mzJ`z", "Join lines" },
	["r"] = { "k", "Down" },
	["R"] = { "K", "Replace mode" },
	["n"] = { "l", "Right" },
	["N"] = { "L", "Screen bottom" },
	["h"] = { "t", "Move before next char" },
	["H"] = { "T", "Move before previous char" },
	["j"] = { "s", "Substitute character" },
	["J"] = { "s", "Substitute Line" },
	["k"] = { "r", "Replace" },
	["K"] = { "R", "Replace mode" },
	["l"] = { "nzzzv", "Next find" },
	["L"] = { "Nzzzv", "Previous find" },
}

wk.register(motions, { mode = "n" })
wk.register(motions, { mode = "v" })
wk.register(motions, { mode = "x" })
wk.register(motions, { mode = "o" })

wk.register(
	{
		["<C-k>"] = { "<C-r>", "Redo" },
		["<leader>"] = {
			b = {
				t = { ":bprevious<CR>", "Next buffer" },
				n = { ":bnext<CR>", "Previous buffer" },
			},
			T = {
				t = { ":tabp<CR>", "Next tab" },
				n = { ":tabn<CR>", "Previous tab" },
			},
			l = {
				t = { "<cmd>lprev<CR>zz", "Previous error" },
				n = { "<cmd>lnext<CR>zz", "Next error" },
			},
		},
		-- Window navigation
		["<C-t>"] = { "<cmd> TmuxNavigateLeft<CR>", "Left window" },
		["<C-s>"] = { "<cmd> TmuxNavigateUp<CR>", "Up window" },
		["<C-r>"] = { "<cmd> TmuxNavigateDown<CR>", "Down window" },
		["<C-n>"] = { "<cmd> TmuxNavigateRight<CR>", "Right window" },
		["<C-'>"] = { "<cmd> TmuxNavigatePrevious<CR>", "Previous window" },
	},
	-- Options
	{ mode = "n" }
)
wk.register(
	{
		["<C-e>"] = { "<Esc>", "Normal mode" },
	},
	-- Options
	{ mode = "i" }
)

wk.register(
	{
		["<C-e>"] = { "<Esc>", "Normal mode" },
		["<A-s>"] = { ":m >+1<CR>gv=gv", "Move lines up" },
		["<A-r>"] = { ":m >-2<CR>gv=gv", "Move lines down" },
	},
	-- Options
	{ mode = "v" }
)

wk.register(
	{
		["<C-e>"] = { "<Esc>", "Normal mode" },
		["<A-s>"] = { ":m >+1<CR>gv=gv", "Move lines up" },
		["<A-r>"] = { ":m >-2<CR>gv=gv", "Move lines down" },
	},
	-- Options
	{ mode = "x" }
)

local function deregister(mappings, prefix, mode)
	local all_mappings = {}
	for _, lhs in ipairs(mappings) do
		local mapping = (prefix or "<leader>") .. lhs
		pcall(vim.api.nvim_del_keymap, mode or "n", mapping)
		all_mappings[mapping] = "which_key_ignore"
	end
	wk.register(all_mappings)
end

deregister({ "<C-H>", "<C-J>", "<C-L>" })

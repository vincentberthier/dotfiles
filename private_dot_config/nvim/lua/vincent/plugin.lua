local fn = vim.fn

local lazypath = vim.fn.stdpath("data") .. "/lazy/lazy.nvim"
if not vim.loop.fs_stat(lazypath) then
	vim.fn.system({
		"git",
		"clone",
		"--filter=blob:none",
		"https://github.com/folke/lazy.nvim.git",
		"--branch=stable", -- latest stable release
		lazypath,
	})
end
vim.opt.rtp:prepend(lazypath)

-- Autocommand that reloads neovim whenever this file is saved
vim.cmd([[
    augroup lazy_user_config
        autocmd!
        autocmd BufWritePost plugin.lua Lazy sync
    augroup end
]])

-- Use a protected call so there are no errors on the first use
local status_ok, lazy = pcall(require, "lazy")
if not status_ok then
	return
end

lazy.setup({
	-- Install theme
	{
		"catppuccin/nvim",
		lazy = false,
		priority = 1000,
		as = "catppuccin",
		config = function()
			require("catppuccin").setup({
				flavour = "mocha",
				transparent_background = true,
				term_colors = false,
				integrations = {
					cmp = true,
					dap = {
						enable = true,
						enable_ui = true,
					},
					gitsigns = true,
					lsp_saga = true,
					mason = true,
					native_lsp = {
						enabled = true,
						virtual_text = {
							errors = { "italic" },
							hints = { "italic" },
							warnings = { "italic" },
							information = { "italic" },
						},
						underlines = {
							errors = { "underline" },
							hints = { "underline" },
							warnings = { "underline" },
							information = { "underline" },
						},
					},
					navic = {
						enabled = true,
						custom_bg = "NONE",
					},
					nvimtree = true,
					treesitter = true,
					telescope = true,
				},
			})
			vim.cmd([[colorscheme catppuccin]])
		end,
	},
	"nvim-lua/popup.nvim", -- an implementation of the popup API from vim in Neovim
	"nvim-lua/plenary.nvim", -- useful lua functions used by lots of plugins

	-- Telescope
	{
		"nvim-telescope/telescope.nvim",
		branch = "0.1.x",
		dependencies = {
			"nvim-telescope/telescope-media-files.nvim",
		},
	},

	--[[ "arcticicestudio/nord-vim", ]]
	--[[ "folke/tokyonight.nvim", ]]
	"xiyaowong/nvim-transparent",

	-- install treesiter
	{ "nvim-treesitter/nvim-treesitter", build = ":TSUpdate" },
	"p00f/nvim-ts-rainbow", -- colour pairs of brackets
	{ "windwp/nvim-ts-autotag", after = "nvim-treesitter" },

	-- install undotree for easier undo navigation
	"mbbill/undotree",
	-- install git plugins
	"tpope/vim-fugitive",
	"lewis6991/gitsigns.nvim",

	-- install LSP servers
	{
		"VonHeikemen/lsp-zero.nvim",
		branch = "v1.x",
		dependencies = {
			-- LSP Support
			"neovim/nvim-lspconfig",
			"williamboman/mason.nvim",
			"williamboman/mason-lspconfig.nvim",
			{ "glepnir/lspsaga.nvim", branch = "main" },

			-- Autocompletion
			"hrsh7th/nvim-cmp", -- completion plugin
			"hrsh7th/cmp-buffer", -- buffer completion
			"hrsh7th/cmp-path", -- path completions
			"hrsh7th/cmp-cmdline", -- command line completions
			"saadparwaiz1/cmp_luasnip", -- snippets completions
			"hrsh7th/cmp-nvim-lsp",
			"hrsh7th/cmp-nvim-lua",

			-- Formatting and linting
			"jose-elias-alvarez/null-ls.nvim",
			"jayp0521/mason-null-ls.nvim",

			-- Snippets
			"L3MON4D3/LuaSnip", -- snippet engine
			"rafamadriz/friendly-snippets", -- snippets library
		},
	},

	-- Visualize lsp progress
	{
		"j-hui/fidget.nvim",
		config = function()
			require("fidget").setup()
		end,
	},

	-- Diagnostics pannel
	{ "folke/trouble.nvim", dependencies = { "nvim-tree/nvim-web-devicons" } },

	-- Debugging
	"mfussenegger/nvim-dap",
	"rcarriga/nvim-dap-ui",
	"ldelossa/nvim-dap-projects",
	"mfussenegger/nvim-dap-python",

	-- Adds extra functionality over rust analyzer
	"simrat39/rust-tools.nvim",

	"windwp/nvim-autopairs", -- Autopairs closes brackets
	"numToStr/Comment.nvim", -- Easily comment stuff
	"JoosepAlviste/nvim-ts-context-commentstring", -- set comments by file type
	"nvim-tree/nvim-tree.lua", -- replace netrw with NvimTree
	"nvim-tree/nvim-web-devicons", -- for file icons
	"moll/vim-bbye", -- close buffers without closing windows
	-- use "ahmedkhalf/project.nvim" -- project management (doesn’t work / bad hardcoded maps)

	-- Auto-headers
	"VincentBerthier/auto-header.nvim",

	-- Status line
	{ "nvim-lualine/lualine.nvim", dependencies = { "nvim-tree/nvim-web-devicons", opt = true } },
	-- Context in the statusline
	{ "SmiteshP/nvim-navic", dependencies = "neovim/nvim-lspconfig" },

	-- tmux & split window navigation
	"christoomey/vim-tmux-navigator",

	-- Maximize and restore current window
	"szw/vim-maximizer",

	-- add, delete, change surroundings
	"tpope/vim-surround",

	-- Coloration for kitty conf
	"fladson/vim-kitty",

	-- Keymap / rebinds handling
	{
		"folke/which-key.nvim",
		config = function()
			vim.o.timeout = true
			vim.o.timeoutlen = 300
		end,
	},
})

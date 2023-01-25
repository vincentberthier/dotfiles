local fn = vim.fn

-- automatically install packer
local install_path = fn.stdpath("data") .. "/site/pack/packer/start/packer.nvim"
if fn.empty(fn.glob(install_path)) > 0 then
	PACKER_BOOSTRAP = fn.system({
		"git",
		"clone",
		"--depth",
		"1",
		"https://github.com/wbthomason/packer.nvim",
		install_path,
	})
	print("Installing packer, close and reopen Neovim…")
	-- Only required if you have packer configured as `opt`
	vim.cmd([[packadd plugin.nvim]])
end

-- Autocommand that reloads neovim whenever this file is saved
vim.cmd([[
    augroup packer_user_config
        autocmd!
        autocmd BufWritePost plugin.lua source <afile> | PackerSync
    augroup end
]])

-- Use a protected call so there are no errors on the first use
local status_ok, packer = pcall(require, "packer")
if not status_ok then
	return
end

-- Have packer use a popup window
packer.init({
	display = {
		open_fn = function()
			return require("packer.util").float({ border = "rounded" })
		end,
	},
})

return require("packer").startup(function(use)
	-- Packer can manage itself
	use("wbthomason/packer.nvim")
	use("nvim-lua/popup.nvim") -- an implementation of the popup API from vim in Neovim
	use("nvim-lua/plenary.nvim") -- useful lua functions used by lots of plugins

	-- Telescope
	use({ "nvim-telescope/telescope.nvim", branch = "0.1.x" })
	use("nvim-telescope/telescope-media-files.nvim")
	use({ "nvim-telescope/telescope-fzf-native.nvim", run = "make" })

	-- Install theme
	use({ "catppuccin/nvim", as = "catppuccin" })
	use({ "folke/tokyonight.nvim" })
	use({ "xiyaowong/nvim-transparent" })

	-- install treesiter
	use("nvim-treesitter/nvim-treesitter", { run = ":TSUpdate" })
	use("p00f/nvim-ts-rainbow") -- colour pairs of brackets
	use({ "windwp/nvim-ts-autotag", after = "nvim-treesitter" })

	-- install undotree for easier undo navigation
	use("mbbill/undotree")
	-- install git plugins
	use("tpope/vim-fugitive")
	use("lewis6991/gitsigns.nvim")

	-- install LSP servers
	use({
		"VonHeikemen/lsp-zero.nvim",
		requires = {
			-- LSP Support
			{ "neovim/nvim-lspconfig" },
			{ "williamboman/mason.nvim" },
			{ "williamboman/mason-lspconfig.nvim" },
			{ "glepnir/lspsaga.nvim", branch = "main" },

			-- Autocompletion
			{ "hrsh7th/nvim-cmp" }, -- completion plugin
			{ "hrsh7th/cmp-buffer" }, -- buffer completion
			{ "hrsh7th/cmp-path" }, -- path completions
			{ "hrsh7th/cmp-cmdline" }, -- command line completions
			{ "saadparwaiz1/cmp_luasnip" }, -- snippets completions
			{ "hrsh7th/cmp-nvim-lsp" },
			{ "hrsh7th/cmp-nvim-lua" },

			-- Formatting and linting
			{ "jose-elias-alvarez/null-ls.nvim" },
			{ "jayp0521/mason-null-ls.nvim" },

			-- Snippets
			{ "L3MON4D3/LuaSnip" }, -- snippet engine
			{ "rafamadriz/friendly-snippets" }, -- snippets library
		},
	})

	-- Visualize lsp progress
	use({
		"j-hui/fidget.nvim",
		config = function()
			require("fidget").setup()
		end,
	})

	-- Debugging
	use({ "mfussenegger/nvim-dap" })
	use({ "rcarriga/nvim-dap-ui" })
	use({ "ldelossa/nvim-dap-projects" })
	use({ "mfussenegger/nvim-dap-python" })

	-- Adds extra functionality over rust analyzer
	use("simrat39/rust-tools.nvim")

	use("windwp/nvim-autopairs") -- Autopairs closes brackets
	use("numToStr/Comment.nvim") -- Easily comment stuff
	use("JoosepAlviste/nvim-ts-context-commentstring") -- set comments by file type
	use("nvim-tree/nvim-tree.lua") -- replace netrw with NvimTree
	use("nvim-tree/nvim-web-devicons") -- for file icons
	--[[ use "akinsho/bufferline.nvim" -- bufferline ]]
	use("moll/vim-bbye") -- close buffers without closing windows
	use("akinsho/toggleterm.nvim") -- open terminal
	-- use "ahmedkhalf/project.nvim" -- project management (doesn’t work / bad hardcoded maps)

	-- Auto-headers
	use("VincentBerthier/auto-header.nvim")

	-- Status line
	use({ "nvim-lualine/lualine.nvim", requires = { "kyazdani142/nvim-web-devicons", opt = true } })
	-- Context in the statusline
	use({ "SmiteshP/nvim-navic", requires = "neovim/nvim-lspconfig" })

	-- tmux & split window navigation
	use({ "christoomey/vim-tmux-navigator" })

	-- Maximize and restore current window
	use({ "szw/vim-maximizer" })

	-- add, delete, change surroundings
	use({ "tpope/vim-surround" })

	-- Coloration for kitty conf
	use({ "fladson/vim-kitty" })

	-- automically set up configuration after cloning packer.nvim
	-- Needs to be at the very end
	if PACKER_BOOSTRAP then
		require("packer").sync()
	end
end)

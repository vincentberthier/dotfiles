vim.g.mapleared = " "

local options = {
	-- Indentation
	tabstop = 4, -- number of spaces a tab counts for
	softtabstop = 4, -- number of spaces to replace a tab with
	shiftwidth = 4, -- number of spaces to insert for identation
	expandtab = true, -- convert tabs to space

	smartindent = true, -- make identing smart (???)

	-- Editing options
	-- Disable word wrap
	wrap = false, -- don’t wrap lines
	conceallevel = 0, -- so that `` is visible in Markdown files
	fileencoding = "utf-8", -- force utf-8 encoding of files

	-- Disable backup file, but persist undo tree
	swapfile = false, -- no swap files
	backup = false, -- no backup files
	undodir = os.getenv("HOME") .. "/.vim/undodir", -- persist undo tree in this dir
	undofile = true, -- persist undo tree files here

	-- Search highlighting & incremental
	hlsearch = true, -- keep the searched terms highlited
	incsearch = true, -- allow incremental search
	ignorecase = true, -- ignore case when searching
	smartcase = true, -- override ignorecase if uppercase present

	termguicolors = true, -- set term gui colours

	-- Backspace
	backspace = "indent,eol,start", -- Allow backspace on indent, end of line or insert mode start position

	-- Generic UI
	scrolloff = 8, -- always show at least eight rows up/down
	sidescrolloff = 8, -- always show at least eight columns
	cursorline = true, -- highlight the current line
	signcolumn = "yes", -- always display the sign column
	cmdheight = 1, -- bottom command line height
	pumheight = 10, -- pop-up menu height
	showmode = false, -- do not show current mode
	showtabline = 2, -- always show tabs
	splitbelow = true, -- vertical splits will be opened below
	splitright = true, -- horizontal splits will be opened right
	timeoutlen = 1000, -- time (ms) to wait for mapped sequences
	guifont = "monospace:h17", -- font used in graphical neovim apps
	-- Line numbers
	nu = true, -- Show line numbers
	relativenumber = true, -- Line numbers are relative to current line
	numberwidth = 2, -- width of the line number column

	updatetime = 50, -- idle time (ms) before swap update

	-- Show column 100
	colorcolumn = "100", -- colour that column

	-- Completion
	completeopt = { "menuone", "noselect", "noinsert" },
	shortmess = vim.opt.shortmess + { c = true },
}

for k, v in pairs(options) do
	vim.opt[k] = v
end

vim.opt.iskeyword:append("-")
vim.opt.isfname:append("@-@") -- add @ to allowed file names

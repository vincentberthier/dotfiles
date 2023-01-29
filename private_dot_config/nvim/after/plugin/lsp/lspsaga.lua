local saga_status, saga = pcall(require, "lspsaga")
if not saga_status then
	print("Could not load saga: lsp commands won't work.")
	return
end

saga.setup({
	scroll_preview = { scroll_down = "<C-f>", scroll_up = "<C-b>" },
	definition = {
		edit = "<CR>",
	},
	ui = {
		kind = require("catppuccin.groups.integrations.lsp_saga").custom_kind(),
	},
})

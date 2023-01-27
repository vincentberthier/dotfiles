function ColorMyPencils(color)
	color = color or "nord"
	local status_ok, _ = pcall(vim.cmd, "colorscheme " .. color)
	if not status_ok then
		vim.notify("colorscheme " .. color .. " not found!")
		return
	end

	vim.api.nvim_set_hl(0, "Normal", { bg = "none" })
	vim.api.nvim_set_hl(0, "VertSplit", { bg = "none" })
	vim.api.nvim_set_hl(0, "Folded", { bg = "none" })
	vim.api.nvim_set_hl(0, "NormalFloat", { bg = "none" })
	vim.api.nvim_set_hl(0, "EndOfBuffer", { bg = "none" })
end

ColorMyPencils()

local status, transparent = pcall(require, "transparent")
if not status then
	vim.notify("Failed to load transparent module")
	return
end

transparent.setup({
	enable = true,
	extra_groups = { "all" },
	exclude = {},
})

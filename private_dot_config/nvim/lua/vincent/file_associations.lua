-- add mxx files to c++
vim.filetype.add({
	extension = {
		mxx = "cpp",
	},
})

-- Only want two indent spaces for nix files
vim.api.nvim_create_autocmd("FileType", {
	pattern = "nix",
	callback = function()
		vim.opt_local.shiftwidth = 2
	end,
})

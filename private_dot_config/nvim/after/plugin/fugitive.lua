vim.keymap.set("n", "<leader>gs", vim.cmd.Git)

local user_fugitive = vim.api.nvim_create_augroup("user_fugitive", {})

local autocmd = vim.api.nvim_create_autocmd
autocmd("BufWinEnter", {
	group = user_fugitive,
	pattern = "*",
	callback = function()
		if vim.bo.ft ~= "fugitive" then
			return
		end

		local bufnr = vim.api.nvim_get_current_buf()

		local status_wk, wk = pcall(require, "which-key")
		if not status_wk then
			print("Could not load which-key, maps will be defaults")
			return
		end
		wk.register({
			["<leader>"] = {
				g = {
					p = {
						function()
							vim.cmd.Git("push")
						end,
						"Push",
					},
					P = {
						function()
							vim.cmd.Git({ "pull", "--rebase" })
						end,
						"Pull",
					},
					t = { ":Git push -u origin", "Set target branch" },
				},
			},
		}, { mode = "n", buffer = bufnr })
	end,
})

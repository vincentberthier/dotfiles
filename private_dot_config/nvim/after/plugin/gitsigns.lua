local status_ok, gitsigns = pcall(require, "gitsigns")
if not status_ok then
	return
end

gitsigns.setup({
	signs = {
		add = { hl = "GitSignsAdd", text = "▎", numhl = "GitSignsAddNr", linehl = "GitSignsAddLn" },
		change = { hl = "GitSignsChange", text = "▎", numhl = "GitSignsChangeNr", linehl = "GitSignsChangeLn" },
		delete = { hl = "GitSignsDelete", text = "契", numhl = "GitSignsDeleteNr", linehl = "GitSignsDeleteLn" },
		topdelete = { hl = "GitSignsDelete", text = "契", numhl = "GitSignsDeleteNr", linehl = "GitSignsDeleteLn" },
		changedelete = { hl = "GitSignsChange", text = "▎", numhl = "GitSignsChangeNr", linehl = "GitSignsChangeLn" },
		untracked = { hl = "GitSignsAdd", text = "┆", numhl = "GitSignsAddNr", linehl = "GitSignsAddLn" },
	},
	signcolumn = true, -- Toggle with `:Gitsigns toggle_signs`
	numhl = false, -- Toggle with `:Gitsigns toggle_numhl`
	linehl = false, -- Toggle with `:Gitsigns toggle_linehl`
	word_diff = false, -- Toggle with `:Gitsigns toggle_word_diff`
	watch_gitdir = {
		interval = 1000,
		follow_files = true,
	},
	attach_to_untracked = true,
	current_line_blame = true, -- Toggle with `:Gitsigns toggle_current_line_blame`
	current_line_blame_opts = {
		virt_text = true,
		virt_text_pos = "eol", -- 'eol' | 'overlay' | 'right_align'
		delay = 1000,
		ignore_whitespace = false,
	},
	current_line_blame_formatter = "<author>, <author_time:%Y-%m-%d> - <summary>",
	current_line_blame_formatter_opts = {
		relative_time = false,
	},
	sign_priority = 6,
	update_debounce = 100,
	status_formatter = nil, -- Use default
	max_file_length = 40000,
	preview_config = {
		-- Options passed to nvim_open_win
		border = "single",
		style = "minimal",
		relative = "cursor",
		row = 0,
		col = 1,
	},
	yadm = {
		enable = false,
	},
	on_attach = function(bufnr)
		local gs = package.loaded.gitsigns

		local status_wk, wk = pcall(require, "which-key")
		if not status_wk then
			print("Could not load which-key, maps will be defaults")
			return
		end

		-- Navigation
		wk.register({
			g = {
				b = {
					function()
						gs.blame_line({ full = true })
					end,
					"Blame",
				},
				d = { gs.toggle_deleted, "Toggle deleted" },
				D = {
					function()
						gs.diffthis("~")
					end,
					"Diff",
				},
				h = {
					name = "Hunk",
					d = {
						function()
							gs.diffthis("~")
						end,
						"Diff this",
					},
					n = {
						function()
							if vim.wo.diff then
								return "]c"
							end
							vim.schedule(function()
								gs.next_hunk()
							end)
							return "<Ignore>"
						end,
						"Next hunk",
					},
					p = { gs.prev_hunk, "Preview" },
					r = { ":Gitsigns reset_hunk<CR>", "Reset hunk" },
					s = { ":Gitsigns stage_hunk<CR>", "Stage hunk" },
					t = {
						function()
							if vim.wo.diff then
								return "[c"
							end
							vim.schedule(function()
								gs.prev_hunk()
							end)
							return "<Ignore>"
						end,
						"Previous hunk",
					},
					u = { gs.undo_stage_hunk, "Undo stage hunk" },
				},
				r = { gs.reset_buffer, "Reset the buffer" },
				s = { gs.stage_buffer, "Stage the buffer" },
				t = { gs.toggle_current_line_blame, "Toggle blame" },
			},
		}, { mode = "n", buffer = bufnr })

		wk.register({
			g = {
				h = { ":<C-u>Gitsigns select_hunk<CR>" },
			},
		}, { mode = "o", buffer = bufnr })
		wk.register({
			g = {
				h = { ":<C-u>Gitsigns select_hunk<CR>" },
			},
		}, { mode = "x", buffer = bufnr })
	end,
})

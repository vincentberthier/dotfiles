local status_wk, wk = pcall(require, "which-key")
if not status_wk then
	print("Could not load which-key: default keymaps")
	return
end

local keys = {
	["<leader>"] = {
		f = {
			s = {
				function()
					require("flash").jump({
						search = {
							mode = function(str)
								return "\\<" .. str
							end,
						},
					})
				end,
				"Flash ",
			},
			S = {
				function()
					require("flash").treesitter({})
				end,
				"Flash Treesitter",
			},
		},
	},
}

wk.register(keys, { mode = "n" })
wk.register(keys, { mode = "x" })
wk.register(keys, { mode = "o" })

wk.register({
	["<leader>"] = {
		f = {
			r = {
				function()
					require("flash").remote()
				end,
				"Remote Flash",
			},
			R = {
				function()
					require("flash").treesitter_search()
				end,
				"Flash Treesitter Search",
			},
		},
	},
}, { mode = "o" })

wk.register({
	["<leader>"] = {
		f = {
			R = {
				function()
					require("flash").treesitter_search()
				end,
				"Flash Treesitter Search",
			},
		},
	},
}, { mode = "x" })

wk.register({
	["<C-s>"] = {
		function()
			require("flash").toggle()
		end,
		"Flash Treesitter Search",
	},
}, { mode = "c" })

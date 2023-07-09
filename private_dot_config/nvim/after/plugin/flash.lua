local status_wk, wk = pcall(require, "which-key")
if not status_wk then
	print("Could not load which-key: default keymaps")
	return
end

local status_f, flash = pcall(require, "flash")
if not status_f then
	print("Could not load flash")
	return
end

flash.setup({
	char = {
		label = { exclude = "tsrniardc" },
		keys = {},
	},
})

local keys = {
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
				require("flash").treesitter()
			end,
			"Flash Treesitter",
		},
	},
}

wk.register(keys, { mode = "n" })
wk.register(keys, { mode = "x" })
wk.register(keys, { mode = "o" })

wk.register({
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
}, { mode = "o" })

wk.register({
	f = {
		R = {
			function()
				require("flash").treesitter_search()
			end,
			"Flash Treesitter Search",
		},
	},
}, { mode = "x" })

wk.register({
	["<c-s>"] = {
		function()
			require("flash").toggle()
		end,
		"Toggle Flash Search",
	},
}, { mode = "c" })

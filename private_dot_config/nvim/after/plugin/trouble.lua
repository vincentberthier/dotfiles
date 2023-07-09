local status_t, trouble = pcall(require, "trouble")
if not status_t then
	print("Could not load trouble")
	return
end

trouble.setup({
	action_keys = {
		refresh = "x",
		switch_severity = "w",
		previous = "s",
		next = "r",
	},
})

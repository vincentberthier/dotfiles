local mstatus, mason = pcall(require, "mason")
if not mstatus then
	print("Mason was not found: cannot configure LSP servers.")
	return
end

local mason_lsp_pconfig_status, mason_lspconfig = pcall(require, "mason-lspconfig")
if not mason_lsp_pconfig_status then
	print("Could not find mason-lspconfig: cannot configure LSP servers")
	return
end

local mason_null_ls_status, mason_null = pcall(require, "mason-null-ls")
if not mason_null_ls_status then
	print("Could not find mason-null-ls: cannot configure LSP servers")
	return
end

-- enable mason
mason.setup({
	ui = {
		check_outdated_packages_on_open = true,
		icons = {
			package_installed = "✓",
			package_pending = "➜",
			package_uninstalled = "✗",
		},
	},
})

mason_lspconfig.setup({
	ensure_installed = {
		"lua_ls",
		"clangd",
		--[[ "rust_analyzer", ]]
	},
	automatic_installation = true,
})

mason_null.setup({
	ensure_installed = {
		-- Lua
		"stylua",
		-- Python
		"black",
		"flake8",
		"autoflake",
		"autopep8",
		"isort",
		"pydocstyle",
		-- rust
		--[[ "rustfmt", ]]
		-- C++-
		"clang-format",
		-- Shell
		"shellharden",
		"shellcheck",
	},
	automatic_installation = true,
})

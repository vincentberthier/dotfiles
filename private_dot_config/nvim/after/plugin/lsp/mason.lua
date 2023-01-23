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
mason.setup()

mason_lspconfig.setup({
	ensure_installed = {
		"sumneko_lua",
		"clangd",
		"rust_analyzer",
		"pylsp",
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
		"mypy",
		"pydocstyle",
		"pylint",
		-- rust
		"rustfmt",
		-- C++-
		"clang-format",
		"cpplint",
		-- Shell
		"shellharden",
		"shellcheck",
	},
	automatic_installation = true,
})

--[[
   astro_inject_meta — darktable Lua plugin

   After each export, if the file lands under ~/Images/Photos/Astro/ and
   matches the YYYY-MM-DD_<target>-<mode>[-web].jpg naming, shell out to
   astro_inject_meta.py so EXIF/XMP metadata from the YAML sidecar gets
   stamped in immediately.

   Install: this file lives in ~/.config/darktable/lua/. The companion
   ~/.config/darktable/luarc must `require "astro_inject_meta"` to load it.

   Logs surface in darktable's console (run `darktable -d lua` to tail).
]]

local dt = require "darktable"

local SCRIPT = os.getenv("HOME") .. "/.config/siril/scripts/astro_inject_meta.py"
local EXPORT_ROOT = os.getenv("HOME") .. "/Images/Photos/Astro"

local function shell_quote(s)
    return "'" .. s:gsub("'", "'\\''") .. "'"
end

local function should_inject(filename)
    if not filename then return false end
    if filename:sub(1, #EXPORT_ROOT) ~= EXPORT_ROOT then return false end
    if not filename:lower():match("%.jpg$") then return false end
    return true
end

dt.register_event(
    "astro_inject_meta",
    "intermediate-export-image",
    function(event, image, filename, format, storage)
        if not should_inject(filename) then return end
        local cmd = "python3 " .. shell_quote(SCRIPT) .. " " .. shell_quote(filename)
        dt.print_log("astro_inject_meta: " .. cmd)
        local rc = dt.control.execute(cmd)
        if rc ~= 0 then
            dt.print_error(
                ("astro_inject_meta failed (rc=%d) for %s"):format(rc, filename)
            )
        end
    end
)

dt.print_log("astro_inject_meta plugin loaded")

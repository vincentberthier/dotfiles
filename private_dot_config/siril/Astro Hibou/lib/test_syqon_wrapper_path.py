#!/usr/bin/env python3
"""Guard the SyQon wrapper's pyscript invocation.

Two independent ways this call can fail SILENTLY, both verified against the
Siril 1.5 source on 2026-07-19:

1. **Resolution.** `process_pyscript` (src/core/command.c:15046) uses an
   argument verbatim if it stats as a file; otherwise it probes each
   script_path entry with `find_file_in_directory()` (src/core/utils.c:1650) —
   a single `g_build_filename(path, basename)` + stat, **no recursion**. Only
   the community repo gets `find_file_recursively()`. So a bare
   "syqon_logged.py" stopped resolving the moment the wrapper moved into lib/.

2. **Quoting.** The script directory is "Astro Hibou", which contains a space.
   `parse_line` (src/core/command_line_processor.c:97) splits on blanks unless
   the token is wrapped in " or '. Unquoted, Siril receives ".../Astro" and the
   run dies — or worse, silently does the wrong thing, which is precisely what
   happened to every `pm` expression until 2026-07-09.

Run:  ~/.local/share/siril/venv/bin/python3 <this file>
"""
import importlib.util
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location(
    "astro_hibou_core", HERE / "astro_hibou_core.py")
core = importlib.util.module_from_spec(spec)
spec.loader.exec_module(core)

failures = []


def check(label, cond):
    print(f"{'ok  ' if cond else 'FAIL'}  {label}")
    if not cond:
        failures.append(label)


def parse_line(myline):
    """Faithful port of parse_line(), command_line_processor.c:97-124."""
    words, i, n = [], 0, len(myline)
    string_starter = "\0"
    while True:
        while i < n and myline[i] in " \t":
            i += 1
        if i < n and myline[i] in "\"'":
            string_starter = myline[i]
            i += 1
        if i >= n or myline[i] in "\0\n\r":
            break
        start = i
        while True:
            i += 1
            if string_starter != "\0" and i < n and myline[i] == string_starter:
                string_starter = "\0"
                break
            if not (i < n and (myline[i] not in " \t" or string_starter != "\0")
                    and (i >= n or myline[i] not in "\r\n")):
                break
        words.append(myline[start:i])
        if i >= n:
            break
        i += 1
    return words


w = core.SYQON_WRAPPER
check("SYQON_WRAPPER is absolute", w.is_absolute())
check("SYQON_WRAPPER exists on disk", w.is_file())
check("SYQON_WRAPPER lives in lib/ (stays out of the Scripts menu)",
      w.parent.name == "lib")

# The exact string _run_syqon builds.
arg = f'"{w}"'
toks = parse_line(f"pyscript {arg} Prism.py --model deep")
check("quoted arg survives Siril's tokenizer intact", toks[1] == str(w))
check("tool name is still a separate word", toks[2] == "Prism.py")

# If the path ever loses its space, quoting stops being load-bearing — but it
# must keep working either way, so assert the fix is robust, not incidental.
if " " in str(w):
    bare = parse_line(f"pyscript {w} Prism.py")
    check("unquoted WOULD truncate (proves the quoting is required)",
          bare[1] != str(w))

# The wrapper must be able to find the SyQon tools from its new location.
roots = (Path.home() / ".local" / "share" / "siril-scripts", w.parent.parent)
check("wrapper's search roots both exist", all(r.is_dir() for r in roots))

print()
if failures:
    print(f"{len(failures)} FAILURE(S)")
    sys.exit(1)
print("all checks passed")

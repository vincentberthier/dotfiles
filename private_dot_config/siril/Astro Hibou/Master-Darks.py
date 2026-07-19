#!/usr/bin/env python3
"""
Master-Darks.py — stack dark subs into master_darks_<exp>.fit.

Point DARKS_ROOT at a folder holding one subfolder per exposure
(0.20s/, 4.00s/, 60.00s/ …), each containing ONLY the dark subs for that
exposure. Each folder is linked into a sequence, stacked (winsorized 3/3,
no normalisation — the dark-frame standard), and written as
<OUT_DIR>/master_darks_<exp>.fit, overwriting the stale master.

Safety guard: EVERY frame in a folder must carry OFFSET == EXPECTED_OFFSET
or that exposure is skipped untouched. This catches leftover offset-30 subs
(e.g. old 0025..0049 that a shorter new run didn't overwrite) that would
otherwise be stacked into an offset-25 master and silently corrupt
calibration. This drive has no backup — the guard is deliberately strict.

GUI only: sirilpy needs a live Siril. Run it from Siril's Scripts menu.
"""

import shutil
import sys
from pathlib import Path

from sirilpy import SirilInterface, LogColor

# ---- configure -------------------------------------------------------------
DARKS_ROOT      = Path("/run/media/vincent/Corrbolg/Astro/Raws/Calibration/DARKS")
OUT_DIR         = Path("/run/media/vincent/Corrbolg/Astro/Raws/Calibration")
EXPECTED_OFFSET = 25
REJ             = ("winsorized", "3", "3")   # reject cosmics, keep real hot pixels
# ---------------------------------------------------------------------------


def fits_offset(path: Path):
    """Return the OFFSET header card as int (no astropy dependency), or None."""
    try:
        with open(path, "rb") as fh:
            while True:
                block = fh.read(2880)
                if not block:
                    return None
                for i in range(0, len(block), 80):
                    card = block[i:i + 80]
                    key = card[:8].rstrip()
                    if key == b"OFFSET":
                        try:
                            return int(float(card[10:].split(b"/")[0]))
                        except ValueError:
                            return None
                    if key == b"END":
                        return None
    except OSError:
        return None


def dark_frames(folder: Path):
    return sorted(f for f in folder.iterdir()
                  if f.suffix.lower() in (".fit", ".fits", ".fts"))


siril = SirilInterface()
siril.connect()

if not DARKS_ROOT.is_dir():
    siril.log(f"DARKS_ROOT not found: {DARKS_ROOT}", LogColor.RED)
    sys.exit(1)

exp_dirs = sorted(d for d in DARKS_ROOT.iterdir()
                  if d.is_dir() and d.name.endswith("s") and d.name != "workdir")
if not exp_dirs:
    siril.log(f"No <exp>s/ subfolders under {DARKS_ROOT}", LogColor.RED)
    sys.exit(1)

built, skipped = [], []
for d in exp_dirs:
    exp = d.name
    frames = dark_frames(d)
    if len(frames) < 2:
        siril.log(f"skip {exp}: only {len(frames)} frame(s)", LogColor.DEFAULT)
        skipped.append(exp)
        continue

    offs = {fits_offset(f) for f in frames}
    if offs != {EXPECTED_OFFSET}:
        seen = sorted(o for o in offs if o is not None)
        siril.log(f"skip {exp}: offsets present {seen or '[unreadable]'}, "
                  f"expected only {EXPECTED_OFFSET} — clear leftover subs first",
                  LogColor.RED)
        skipped.append(exp)
        continue

    siril.log(f"Stacking {exp}: {len(frames)} frames @ offset {EXPECTED_OFFSET}",
              LogColor.BLUE)
    shutil.rmtree(d / "process", ignore_errors=True)
    siril.cmd("cd", str(d))
    siril.cmd("link", "dark", "-out=process")
    siril.cmd("cd", "process")
    out = OUT_DIR / f"master_darks_{exp}"
    siril.cmd("stack", "dark", "rej", *REJ, "-nonorm", f"-out={out}")
    built.append(exp)

siril.log(f"Done. Built: {', '.join(built) or 'none'}. "
          f"Skipped: {', '.join(skipped) or 'none'}.",
          LogColor.GREEN if built else LogColor.RED)

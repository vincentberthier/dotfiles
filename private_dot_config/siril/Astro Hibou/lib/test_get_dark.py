"""Regression test for get_dark's exposure-token normalisation.

The bug it guards against, observed live on 2026-07-15:

Dark masters are named with the exposure's trailing "s"
(`master_darks_120.00s.fit`). RE_FLATS captures that "s" inside its exposure
group, but RE_LIGHTS does not — the "s" sits *outside* the group
(`([\\d\\.]+)s_`), so a light's exposure reaches get_dark as "120.00" instead
of "120.00s". The old get_dark then looked for `master_darks_120.00.fit`, which
does not exist, returned None, and every light calibrated flat-only: no dark
subtraction, no -cc=dark bad-pixel interpolation. Proven on M 51 2026-07-13/14
subs, whose FITS HISTORY read `dark=False flat=True cc=False`, against a 2025
run's `dark=True flat=True cc=True`.

get_dark must resolve BOTH the flat token ("0.20s") and the light token
("0.20") to the same on-disk master.
"""

import sys, tempfile, atexit, shutil
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
import astro_hibou_core as C

TMP = Path(tempfile.mkdtemp(prefix="test_get_dark_"))
atexit.register(shutil.rmtree, TMP, True)

# A dark library named exactly as Master-Darks.py / the reshoot writes it.
for exp in ("0.20s", "60.00s", "120.00s", "300.00s"):
    (TMP / f"master_darks_{exp}.fit").write_bytes(b"")

# get_dark reads the module global; point it at the fake library.
C.DARK_PATH = TMP

failures = []


def check(label, got, want):
    ok = got == want
    print(f"{label:56} -> {'ok' if ok else 'FAIL'}")
    if not ok:
        failures.append(f"{label}: got {got!r}, want {want!r}")


def resolved(exposure):
    """Return the resolved master's name, or None."""
    p = C.get_dark(exposure)
    return p.name if p is not None else None

# --- the light token (no "s") must resolve, the whole point of the fix -----
check("light token '120.00' resolves", resolved("120.00"), "master_darks_120.00s.fit")
check("light token '60.00' resolves", resolved("60.00"), "master_darks_60.00s.fit")
check("light token '300.00' resolves", resolved("300.00"), "master_darks_300.00s.fit")

# --- the flat token (already "s") must keep working, no double-suffix ------
check("flat token '0.20s' resolves", resolved("0.20s"), "master_darks_0.20s.fit")
check("flat token '120.00s' resolves", resolved("120.00s"), "master_darks_120.00s.fit")

# --- a genuinely absent exposure is still None (no invented file) ----------
check("missing exposure '999.00' -> None", resolved("999.00"), None)
check("missing exposure '999.00s' -> None", resolved("999.00s"), None)

# --- the light and flat forms of the same exposure map to one file ---------
check(
    "light '120.00' and flat '120.00s' agree",
    resolved("120.00") == resolved("120.00s") == "master_darks_120.00s.fit",
    True,
)

print()
if failures:
    for f in failures:
        print("FAILURE:", f)
    sys.exit(1)
print("ALL ASSERTIONS PASSED")

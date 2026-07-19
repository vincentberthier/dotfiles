"""Regression tests for `Pipeline._pin_syqon_config`.

The SyQon tools take only a handful of CLI flags; every other knob lives in
`<siril configdir>/syqon_<tool>_config.json`, which their GUIs rewrite. Some
knobs have no flag at all — Parallax's `mode` (which *model* runs), Starless's
`stretch_method` / `ihs_target` — so before 2026-07-12 a pipeline run silently
inherited whatever the last interactive GUI session left behind, and two runs
of the same script could produce different images with nothing in the log to
say why. These tests pin the behaviour that fixes it.
"""

import sys, json, tempfile, atexit, shutil, types
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import astro_hibou_core as C

TMP = Path(tempfile.mkdtemp(prefix="test_syqon_config_pin_"))
atexit.register(shutil.rmtree, TMP, True)

failures = []


def check(label, got, want):
    ok = got == want
    print(f"{label:64} -> {'ok' if ok else 'FAIL'}")
    if not ok:
        failures.append(f"{label}: got {got!r}, want {want!r}")


def pipeline(cfgdir: Path):
    """A Pipeline with only what _pin_syqon_config touches: self.siril."""
    p = C.Pipeline.__new__(C.Pipeline)
    p.siril = types.SimpleNamespace(get_siril_configdir=lambda: str(cfgdir))
    return p


def read(cfgdir: Path, tool: str) -> dict:
    return json.loads((cfgdir / f"syqon_{tool}_config.json").read_text())


# --- 1. GUI residue is overwritten, unrelated keys are preserved ------------
#
# The exact trap: a GUI session leaves `mode: aesthetics` (a different model!)
# and `linked_stretch: false` behind. The pipeline must not inherit either.
d = TMP / "residue"
d.mkdir()
(d / "syqon_parallax_config.json").write_text(
    json.dumps({"mode": "aesthetics", "linked_stretch": False, "batch_size": "4"})
)
pipeline(d)._pin_syqon_config("parallax", {**C.PARALLAX_CONFIG, "sharpen_alpha": 1.0})
cfg = read(d, "parallax")
check("parallax: GUI 'mode' residue overwritten", cfg["mode"], "classic")
check("parallax: GUI 'linked_stretch' residue overwritten", cfg["linked_stretch"], True)
check("parallax: untouched key preserved", cfg["batch_size"], "4")
check("parallax: sharpen_alpha threaded through", cfg["sharpen_alpha"], 1.0)

# --- 2. a missing config file is created ------------------------------------
d = TMP / "missing"
d.mkdir()
pipeline(d)._pin_syqon_config("starless", C.STARLESS_CONFIG)
cfg = read(d, "starless")
check("starless: config created when absent", cfg["stretch_method"], "ihs")
check("starless: ihs_target pinned", cfg["ihs_target"], 0.1)
check("starless: model pinned", cfg["model"], "axiom3")

# --- 3. a corrupt config file is rewritten, not raised on -------------------
d = TMP / "corrupt"
d.mkdir()
(d / "syqon_prism_config.json").write_text("{ not json at all")
pipeline(d)._pin_syqon_config("prism", {**C.PRISM_CONFIG, "modulation": 100})
cfg = read(d, "prism")
check("prism: corrupt config rewritten", cfg["stretch_target"], C.PRISM_STRETCH_TARGET)
check("prism: modulation is percent (int), not a fraction", cfg["modulation"], 100)

# --- 4. a config dir that does not exist yet --------------------------------
d = TMP / "nodir" / "siril"
pipeline(d)._pin_syqon_config("prism", C.PRISM_CONFIG)
check("prism: config dir created", (d / "syqon_prism_config.json").exists(), True)

# --- 5. the pinned values --------------------------------------------------
#
# 0.10 rather than Prism's 0.25 default. On current evidence the flag makes no
# visible difference; this just pins it so a run is reproducible.
check("Prism stretch target is pinned", C.PRISM_STRETCH_TARGET, 0.10)
check("Parallax runs the classic sharpen model", C.PARALLAX_CONFIG["mode"], "classic")
check("Parallax linked stretch on (star colours)", C.PARALLAX_CONFIG["linked_stretch"], True)
check("Starless uses IHS 0.1", C.STARLESS_CONFIG["ihs_target"], 0.1)

print()
if failures:
    print(f"{len(failures)} FAILURE(S):")
    for f in failures:
        print("  -", f)
    sys.exit(1)
print("all ok")

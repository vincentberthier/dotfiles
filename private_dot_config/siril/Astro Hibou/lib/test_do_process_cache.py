"""Regression tests for do_process's SyQon-chain caching.

Two defects, both observed on M 101 2026-07-10 after a fourth night was added:

1. The `denoise` History entry is keyed on `<image>_deconvolved.fit` as its
   input. Rebuilding `<image>.fit` invalidates `deconvolve` (its input moved)
   but NOT `denoise` (its recorded input, the stale deconvolved file, did not
   move). do_process tested `denoise_done` first, so it loaded the previous
   run's `<image>_denoised.fit` and skipped Parallax and Prism entirely.

2. Star removal then "succeeded" because the check was `final_out.exists()`,
   which passes on the previous run's leftovers. A Starless that wrote nothing
   was recorded as done.
"""

import sys, time, tempfile, atexit, shutil, types
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
import astro_hibou_core as C

TMP = Path(tempfile.mkdtemp(prefix="test_do_process_cache_"))
atexit.register(shutil.rmtree, TMP, True)

failures = []


def check(label, got, want):
    ok = got == want
    print(f"{label:58} -> {'ok' if ok else 'FAIL'}")
    if not ok:
        failures.append(f"{label}: got {got!r}, want {want!r}")


def touch(p: Path, when: float) -> Path:
    p.write_bytes(b"x")
    import os
    os.utime(p, (when, when))
    return p


# --- 1. the stale-denoise trap --------------------------------------------
root = TMP / "cache"
root.mkdir()
h = C.History(root)
inp = root / "lrgb.fit"
deconv = root / "lrgb_deconvolved.fit"
denoise = root / "lrgb_denoised.fit"

# Yesterday: the whole chain ran and was recorded.
t0 = time.time() - 86400
touch(inp, t0)
touch(deconv, t0 + 60)
touch(denoise, t0 + 120)
h.records[C.Step(str(root), "deconvolve", "lrgb")] = t0 + 61
h.records[C.Step(str(root), "denoise", "lrgb")] = t0 + 121

# Today: a new night lands, compose rewrites the master. Nothing else moved.
touch(inp, time.time())

deconv_done = h.is_done(root, "deconvolve", "lrgb", outputs=[deconv], inputs=[inp])
denoise_alone = h.is_done(root, "denoise", "lrgb", outputs=[denoise], inputs=[deconv])

check("rebuilt master invalidates deconvolve", deconv_done, False)
check("denoise checked alone is (wrongly) still done", denoise_alone, True)
check("cascaded: denoise must not be reused", deconv_done and denoise_alone, False)

# The fix also drops the record, so it cannot linger in .history.
h2 = C.History(root)
h2.records[C.Step(str(root), "denoise", "lrgb")] = t0 + 121
h2.invalidate(root, "denoise", "lrgb")
check("invalidate removes the denoise record",
      C.Step(str(root), "denoise", "lrgb") in h2.records, False)

# Control: if the master did NOT change, both stay cached.
root2 = TMP / "cache_unchanged"
root2.mkdir()
h3 = C.History(root2)
i2, d2, n2 = (root2 / "lrgb.fit", root2 / "lrgb_deconvolved.fit",
              root2 / "lrgb_denoised.fit")
touch(i2, t0); touch(d2, t0 + 60); touch(n2, t0 + 120)
h3.records[C.Step(str(root2), "deconvolve", "lrgb")] = t0 + 61
h3.records[C.Step(str(root2), "denoise", "lrgb")] = t0 + 121
dd = h3.is_done(root2, "deconvolve", "lrgb", outputs=[d2], inputs=[i2])
nd = h3.is_done(root2, "denoise", "lrgb", outputs=[n2], inputs=[d2])
check("untouched master keeps deconvolve cached", dd, True)
check("untouched master keeps denoise cached", dd and nd, True)

# A fresh deconvolve output must invalidate a cached denoise.
touch(d2, time.time())
check("fresh deconv output invalidates denoise",
      h3.is_done(root2, "denoise", "lrgb", outputs=[n2], inputs=[d2]), False)


# --- 2. Starless must prove it wrote --------------------------------------
def starless_stub(behaviour):
    """A Pipeline-shaped object exposing only what _run_starless touches.

    That includes `_pin_syqon_config`, which _run_starless calls to stop the
    tool inheriting the GUI's saved config (Starless's `stretch_method` and
    `ihs_target` have no CLI flag). Bind the real thing against a scratch
    config dir rather than stubbing it out, so this test also fails if the pin
    ever stops being issued.
    """
    cfgdir = TMP / "cfg"
    cfgdir.mkdir(exist_ok=True)
    obj = types.SimpleNamespace()
    obj.siril = types.SimpleNamespace(get_siril_configdir=lambda: str(cfgdir))
    obj._pin_syqon_config = types.MethodType(C.Pipeline._pin_syqon_config, obj)
    obj._run_syqon = lambda *a, **k: behaviour()
    obj._run_starless = types.MethodType(C.Pipeline._run_starless, obj)
    return obj


sr = TMP / "starless"
sr.mkdir()
out1, out2 = sr / "starless_x.fit", sr / "starmask_x.fit"

# (a) tool writes nothing, outputs absent -> must raise
p = starless_stub(lambda: None)
try:
    p._run_starless(out1, out2)
    check("no output at all -> raises", False, True)
except RuntimeError as e:
    check("no output at all -> raises", "starless_x.fit" in str(e), True)

# (b) THE BUG: stale leftovers from a previous run, tool writes nothing.
touch(out1, t0); touch(out2, t0)
p = starless_stub(lambda: None)
try:
    p._run_starless(out1, out2)
    check("stale leftovers -> raises (exists() would have passed)", False, True)
except RuntimeError as e:
    check("stale leftovers -> raises (exists() would have passed)",
          "starless_x.fit" in str(e) and "starmask_x.fit" in str(e), True)

# (c) only one of the two rewritten -> still a failure
touch(out1, t0); touch(out2, t0)
p = starless_stub(lambda: touch(out1, time.time()))
try:
    p._run_starless(out1, out2)
    check("partial write -> raises", False, True)
except RuntimeError as e:
    check("partial write -> raises",
          "starmask_x.fit" in str(e) and "starless_x.fit" not in str(e), True)

# (d) real run: both rewritten -> no raise
touch(out1, t0); touch(out2, t0)


def both():
    now = time.time()
    touch(out1, now)
    touch(out2, now)


p = starless_stub(both)
try:
    p._run_starless(out1, out2)
    check("both outputs rewritten -> passes", True, True)
except RuntimeError as e:
    check(f"both outputs rewritten -> passes ({e})", False, True)

print()
if failures:
    for f in failures:
        print("FAILURE:", f)
    sys.exit(1)
print("ALL ASSERTIONS PASSED")

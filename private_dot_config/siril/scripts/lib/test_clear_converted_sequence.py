"""Regression test for Pipeline._clear_converted_sequence.

The bug it guards against, observed on M 101 2026-07-09:

`convert -out=../` symlinks each input frame into process/ as
`<seq>_00001.fit`, numbered by position. Rebuilding a sequence with fewer
frames (what the quarantine retry does) overwrites the indices it needs and
leaves the highest one behind, pointing at a sub that has since moved to
DISPOSED/. Siril's directory rescan still counts that dangling entry, builds an
N+1-image sequence, and `calibrate` dies on the frame it cannot open:

    Erreur dans le fichier FITS : luminance_00018.fit
    Impossible de charger l'image 17 de la séquence luminance_
    Le traitement de la séquence a échoué.
"""

import sys, tempfile, atexit, shutil
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
import astro_hibou_core as C

TMP = Path(tempfile.mkdtemp(prefix="test_clear_seq_"))
atexit.register(shutil.rmtree, TMP, True)

clear = C.Pipeline._clear_converted_sequence


def build(root: Path, name: str) -> Path:
    """A process/ dir as it looks after an 18-frame convert, then a disposal."""
    d = root
    d.mkdir(parents=True, exist_ok=True)
    lights = d / "lights"
    lights.mkdir(exist_ok=True)
    # 17 live frames, plus a dangling 18th whose target was disposed of.
    for i in range(1, 18):
        target = lights / f"frame_{i:04d}.fits"
        target.write_bytes(b"")
        (d / f"{name}_{i:05d}.fit").symlink_to(target)
    (d / f"{name}_00018.fit").symlink_to(lights / "disposed.fits")
    (d / f"{name}_.seq").write_text("S 'luminance_' 1 18 18 5 -1 7 0 0 0\n")
    (d / f"{name}_conversion.txt").write_text("stale\n")
    return d


def names(d: Path) -> set:
    return {p.name for p in d.iterdir() if p.is_file() or p.is_symlink()}


failures = []


def check(label, got, want):
    ok = got == want
    print(f"{label:52} -> {'ok' if ok else 'FAIL'}")
    if not ok:
        failures.append(f"{label}: got {got!r}, want {want!r}")


# --- the dangling link is what actually breaks the run --------------------
d = build(TMP / "case1", "luminance")
assert (d / "luminance_00018.fit").is_symlink()
assert not (d / "luminance_00018.fit").exists(), "must be dangling"

clear(d, "luminance")
left = names(d)
check("every frame link removed", {n for n in left if n.endswith(".fit")}, set())
check("dangling 00018 removed", "luminance_00018.fit" in left, False)
check("stale .seq removed", "luminance_.seq" in left, False)
check("conversion.txt removed", "luminance_conversion.txt" in left, False)

# --- and it must not scythe the neighbours --------------------------------
d = build(TMP / "case2", "luminance")
# Sibling sequences that share a substring, plus the master it all feeds.
(d / "flats_luminance_00001.fit").symlink_to(d / "lights" / "frame_0001.fits")
(d / "flats_luminance_.seq").write_text("x\n")
(d / "pp_luminance_00001.fit").symlink_to(d / "lights" / "frame_0001.fits")
(d / "r_pp_luminance_00001.fit").symlink_to(d / "lights" / "frame_0001.fits")
(d / "master_luminance.fit").write_bytes(b"")
(d / "master_flats_luminance.fit").write_bytes(b"")

clear(d, "luminance")
left = names(d)
for survivor in (
    "flats_luminance_00001.fit",
    "flats_luminance_.seq",
    "pp_luminance_00001.fit",
    "r_pp_luminance_00001.fit",
    "master_luminance.fit",
    "master_flats_luminance.fit",
):
    check(f"survives: {survivor}", survivor in left, True)

# --- clearing the flats sequence must not touch the lights ----------------
d = build(TMP / "case3", "flats_ha")
(d / "ha_00001.fit").symlink_to(d / "lights" / "frame_0001.fits")
(d / "ha_.seq").write_text("x\n")

clear(d, "flats_ha")
left = names(d)
check("flats_ha links gone", any(n.startswith("flats_ha_0") for n in left), False)
check("survives: ha_00001.fit", "ha_00001.fit" in left, True)
check("survives: ha_.seq", "ha_.seq" in left, True)

# --- the combine path clears "pp_<filter>", and must spare "r_pp_<filter>" -
d = build(TMP / "case5", "pp_luminance")
(d / "r_pp_luminance_00001.fit").symlink_to(d / "lights" / "frame_0001.fits")
(d / "r_pp_luminance_.seq").write_text("x\n")
(d / "master_pp_flats_luminance.fit").write_bytes(b"")

clear(d, "pp_luminance")
left = names(d)
check("pp_luminance links gone", any(n.startswith("pp_luminance_0") for n in left), False)
check("pp_luminance_.seq gone", "pp_luminance_.seq" in left, False)
check("survives: r_pp_luminance_00001.fit", "r_pp_luminance_00001.fit" in left, True)
check("survives: r_pp_luminance_.seq", "r_pp_luminance_.seq" in left, True)
check("survives: master_pp_flats_luminance.fit", "master_pp_flats_luminance.fit" in left, True)

# --- idempotent: a clean dir is not an error ------------------------------
d = TMP / "case4"
d.mkdir()
clear(d, "luminance")
check("no-op on an empty dir", names(d), set())

print()
if failures:
    for f in failures:
        print("FAILURE:", f)
    sys.exit(1)
print("ALL ASSERTIONS PASSED")

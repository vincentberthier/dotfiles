#!/usr/bin/env python3
"""Astro-Hibou shared processing library.

This module is the common core imported by the three Astro-Hibou launcher
scripts that live next to it:

  - astro_hibou.py          — single-target GUI (calibrate → stack → recombine
                              → deconv/denoise/star-removal → _STRETCH_ME).
  - astro_hibou_mosaic.py   — multi-panel mosaic front-end.
  - astro_hibou_veralux.py  — interactive VeraLux continuation past the linear
                              checkpoint.

It carries no GUI window of its own and is not meant to be launched from the
Siril script menu directly; the launchers add this file's directory to
sys.path and `import astro_hibou_core`. Everything reusable — the Siril
`Pipeline`, the step-caching `History`, the SyQon wrappers, the metadata
sidecar, the generic Qt `PipelineWorker`, and the post-run `StatsDialog` —
lives here so a fix lands in one place.
"""

import hashlib
import json
import os
import re
import shutil
import subprocess
import threading
import time
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import date
from enum import Enum
from pathlib import Path
from typing import Callable, Iterable, Iterator

import sirilpy

sirilpy.ensure_installed(
    "PyQt6", "astropy", "numpy", "PyYAML", "psutil", "scipy", "Pillow"
)

import numpy as np  # noqa: E402  — deps imported after ensure_installed()
import yaml  # noqa: E402
from PIL import Image  # noqa: E402
from astropy.io import fits  # noqa: E402
from scipy.ndimage import gaussian_filter  # noqa: E402
from sirilpy import CommandError, SirilError  # noqa: E402
from PyQt6.QtCore import QObject, Qt, pyqtSignal  # noqa: E402
from PyQt6.QtWidgets import (  # noqa: E402
    QAbstractScrollArea,
    QApplication,
    QDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)


# --- Shared GUI helpers ------------------------------------------------------

# Qt's "no maximum" sentinel. PyQt6 does not export QWIDGETSIZE_MAX.
_QWIDGETSIZE_MAX = 16_777_215

# Floor for a scroll area's height when the window has to shrink to fit a small
# screen: below this it is a slit, not a view.
_MIN_SCROLL_HEIGHT = 120


def scrollable(content: QWidget) -> QScrollArea:
    """Wrap a widget so a tall form scrolls instead of crushing its children.

    Without this, a Qt layout that cannot fit its children shrinks the *last*
    groups past their minimum and their rows overlap — the "Processing" box
    collapsing into unreadable stripes once the day checkboxes populate the
    Options group. Scrolling is the only honest response to "does not fit".
    """
    area = QScrollArea()
    area.setWidgetResizable(True)
    area.setFrameShape(QFrame.Shape.NoFrame)
    area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
    # Without AdjustToContents a QScrollArea reports a small, constant sizeHint,
    # so fit_to_content() can never grow the window and every dialog opens with
    # a scrollbar it does not need. With it, the window grows to fit and only
    # scrolls once it hits the screen cap.
    area.setSizeAdjustPolicy(QAbstractScrollArea.SizeAdjustPolicy.AdjustToContents)
    area.setWidget(content)
    return area


def _invalidate_layouts(widget: QWidget) -> None:
    """Depth-first `invalidate()` of every nested layout under `widget`.

    Adding a widget to a nested layout only posts a `LayoutRequest` event to the
    parent; the ancestors' cached `sizeHint()` is not refreshed until the event
    loop delivers it. `fit_to_content` runs synchronously from a signal handler,
    so it would measure the *stale* hint and resize to the old size. Measured:
    after adding four checkboxes the group's own hint goes 44 -> 150 px while its
    parent still reports 248. Invalidating bottom-up fixes the whole chain
    without pumping the event loop (which would be re-entrant here).
    """
    # A QScrollArea has no layout() of its own — its content hangs off
    # .widget(), so the recursion has to step through it explicitly or it stops
    # at the scroll area and nothing inside is ever refreshed.
    if isinstance(widget, QAbstractScrollArea):
        inner = widget.widget()
        if inner is not None:
            _invalidate_layouts(inner)
        widget.updateGeometry()
        return
    layout = widget.layout()
    if layout is None:
        return
    for i in range(layout.count()):
        child = layout.itemAt(i).widget()
        if child is not None:
            _invalidate_layouts(child)
    layout.invalidate()
    layout.activate()
    widget.updateGeometry()


def fit_to_content(window: QWidget, screen_fraction: float = 0.85) -> None:
    """Resize a window to its content, capped by the screen, and leave it resizable.

    Call this after any change that adds or removes widgets.

    **Never pair `adjustSize()` with `setFixedSize()`.** `setFixedSize` sets the
    minimum *and* maximum to the current size, so the next `adjustSize()` is
    clamped to it and cannot grow — the window stays at the size it had before
    the widgets were added, and whatever sits at the bottom of the layout gets
    squeezed. Releasing the constraint first is what makes the regrow work.
    """
    screen = window.screen() or QApplication.primaryScreen()
    if screen is not None:
        avail = screen.availableGeometry()
        cap_w = int(avail.width() * screen_fraction)
        cap_h = int(avail.height() * screen_fraction)
    else:
        cap_w = cap_h = _QWIDGETSIZE_MAX

    window.setMinimumSize(0, 0)
    window.setMaximumSize(_QWIDGETSIZE_MAX, _QWIDGETSIZE_MAX)
    _invalidate_layouts(window)

    # A QScrollArea's own sizeHint does not track its content even under
    # AdjustToContents, so the window would never grow past the area's default
    # hint. Drive the area from its content directly, capped by the screen: the
    # minimum is what stops the groups being crushed, the cap is what makes it
    # scroll instead of running off the display.
    areas = []
    for area in window.findChildren(QAbstractScrollArea):
        inner = area.widget()
        if inner is None:
            continue
        frame = 2 * area.frameWidth()
        bar = area.verticalScrollBar().sizeHint().width()
        area.setMinimumHeight(min(inner.sizeHint().height() + frame, cap_h))
        area.setMinimumWidth(min(inner.sizeHint().width() + frame + bar, cap_w))
        areas.append(area)

    window.adjustSize()
    # The cap applies to the whole window, but the scroll area's minimum is what
    # sets the window's own minimum, so a cap-height area plus the pinned status
    # row and buttons overshoots. Give the areas back exactly the overshoot.
    overflow = window.sizeHint().height() - cap_h
    if overflow > 0 and areas:
        share = -(-overflow // len(areas))  # ceil
        for area in areas:
            area.setMinimumHeight(max(_MIN_SCROLL_HEIGHT,
                                      area.minimumHeight() - share))
        window.adjustSize()

    hint = window.sizeHint()
    window.resize(min(hint.width(), cap_w), min(hint.height(), cap_h))


# --- Configuration ----------------------------------------------------------

DARK_PATH = Path(
    os.environ.get(
        "ASTRO_HIBOU_DARK_PATH",
        "/run/media/vincent/Corrbolg/Astro/Raws/Calibration",
    )
)
SIRIL_MIN_VERSION = "1.5.0"

# Below this many frames, skip the `-filter-round=3k` guard in stack_lights:
# a `-filter-*` cut on a very short sequence can drop it below the 2-image
# stacking minimum and Siril aborts. Keep every frame and let per-pixel
# rejection do the cleanup on thin nights.
QUALITY_FILTER_MIN_FRAMES = 8

# Longest edge of the _STRETCH_ME preview JPEG. Big enough to judge the
# background at a glance, small enough to open instantly.
PREVIEW_MAX_PX = 2048

# The preview uses an asinh stretch, not the MTF autostretch whose numbers the
# README prints. MTF pins the background to its target (0.25), which can only
# render as a flat grey sky with the object floating on it — a valid inspection
# screen-stretch but not representative of an achievable result, so it read as
# "atrocious". asinh compresses the highlights and holds the shadows down, the
# way a real deep-sky stretch does, giving a near-black sky and visible arms.
# Both parameters are still derived from the PRE-denoise (deconvolved) frame —
# the invariant that keeps the black point off the denoised frame's collapsed
# sigma. BLACK_OFFSET sits the black point ~1 sigma under the sky so it reads
# black without clipping the faint outer structure (offset 0 crushed the halo);
# TARGET_BG is where the sky median lands after the curve.
PREVIEW_BLACK_OFFSET = 1.0
PREVIEW_TARGET_BG = 0.08

# Target median of SyQon Prism's internal temporary stretch (--stretch-target).
#
# 0.10 (Prism's own default is 0.25). On current evidence THIS FLAG DOES NOT
# MATTER: setting the median to 0.1 in both Parallax and Prism produced no
# visible change. It was moved to 0.25 and back on 2026-07-12, both times on
# reasoning that did not hold. Leave it alone; see _run_prism before touching.
PRISM_STRETCH_TARGET = 0.10

# --- SyQon tool configuration ------------------------------------------------
#
# The SyQon tools accept a handful of CLI flags; every other knob lives in
# `<siril configdir>/syqon_<tool>_config.json`, which their GUIs rewrite on
# every interactive session. Several knobs have NO flag at all:
#
#   Parallax  `mode` — which model runs: "classic" -> parallax_sharpen.pth,
#             "aesthetics" -> aesthetics_deblur.pth. Also `use_mtf` and
#             `mtf_target`. `--linked` can only turn `linked_stretch` ON;
#             there is no way to turn it off from the command line.
#   Starless  `stretch_method`, `ihs_target`, `model`, `mask_method` — none of
#             them has a flag. Its argparse offers only --tile-size, --overlap,
#             --no_gpu, --axiom3, --force_update_check.
#
# So a pipeline run silently inherits whatever the last interactive GUI session
# left behind, and the same script can produce a different image on two runs
# with nothing in the log to say why. Observed on M 101: the 2026-07-10 pipeline
# run and the 2026-07-12 hand-driven GUI run differed in Parallax's
# `linked_stretch` and `overlap`, invisibly.
#
# `_pin_syqon_config` therefore writes these keys before every invocation, so
# the run is defined by the pipeline rather than by GUI residue. The values are
# the ones validated by hand on M 101 (2026-07-12). A key that also has a CLI
# flag is still passed on the command line; pinning it here just means the two
# cannot disagree.

PARALLAX_CONFIG = {
    "edition": "pro",
    "mode": "classic",  # parallax_sharpen.pth ("aesthetics" = deblur model)
    "correct": True,  # aberration correction (StellarDirectNet)
    "sharpen": True,
    "tile_size": 512,
    "overlap": 256,
    "pad": 96,
    "use_mtf": True,  # temporary stretch, for linear data
    "mtf_target": 0.25,
    "linked_stretch": True,  # preserves star colours
}

PRISM_CONFIG = {
    "model": "deep",
    "tile_size": 512,
    "overlap": 256,
    "pad": 96,
    "stretch_method": "statistical",
    "stretch_target": PRISM_STRETCH_TARGET,
    "ihs_target": PRISM_STRETCH_TARGET,
}

STARLESS_CONFIG = {
    "model": "axiom3",
    "tile_size": 512,
    "overlap": 256,
    "generate_mask": True,
    "mask_method": "subtraction",
    "stretch_method": "ihs",  # IHS keeps bright cores off the clamp
    "ihs_target": 0.1,
    "linked_stretch": False,
}

# --- Frame quarantine -------------------------------------------------------
#
# A sub whose framing is grossly inconsistent with the rest of its sequence —
# the rotator or the whole imaging train moved mid-session, a slew never
# recentred — makes `seqapplyreg -framing=min` fail outright ("the intersection
# of all images is null or negative"), taking the entire channel down with it.
# Rather than lose the night, move the offending frame(s) out of LIGHTS/ into
# DISPOSED/ (never deleted — this drive is the only copy) and rebuild.
#
# A frame is an outlier when its registered footprint overlaps the rest of the
# sequence too little to survive `-framing=min` (which crops the stack to the
# common area of every sub). Overlap — not rotation angle — is the right test:
# the IMX533 is square, so a rotation *about the field centre* barely shrinks the
# common area (a 45 deg rotation still overlaps 83 %, a ~180 deg meridian flip
# 93-100 %), while a failed recenter or a train that shifted drops it sharply. A
# raw rotation threshold cannot tell a benign cross-night meridian flip (both
# pier sides, ~180 deg apart, near-full overlap — homography registration aligns
# it fine) from a mechanical slip, and wrongly disposed the flipped night's subs.
# 0.90 sits cleanly between the real cases measured on this rig: an M 101 Ha
# misframe (82.9 %, dispose) and an NGC 7023 meridian flip (93.1 %, keep).
DISPOSED_DIRNAME = "DISPOSED"
QUARANTINE_MIN_OVERLAP = 0.90  # of the frame area, vs the majority footprint

# Never let quarantine eat a sequence. If the outliers are anything but a clear
# minority we cannot know which group is the good one (e.g. two nights shot at
# genuinely different rotator angles pooled into one sequence), so refuse to
# dispose of anything and surface it instead. Below QUARANTINE_MIN_FRAMES a
# disagreement is undecidable by majority at all: 1-vs-1 has no majority.
QUARANTINE_MAX_OUTLIER_FRAC = 0.40
QUARANTINE_MIN_FRAMES = 3

# Post-recombination coverage crop: a whole edge row/column is trimmed only
# while its covered fraction is below this. Higher = trims the ragged mosaic
# edge and its rotated corners more aggressively (cleaner but smaller); lower
# = keeps more, leaving small black corners for manual cleanup. Interior gaps
# (thin panel seams) are always tolerated. ~0.8 keeps a mosaic near its full
# extent while removing the dead border.
COVERAGE_EDGE_THRESHOLD = 0.8

# --- Ha blend mask ----------------------------------------------------------
#
# Ha is blended only where Ha actually emits. The gate is the continuum-
# cancelled excess (Ha - base, both linear-matched), smoothed to beat down its
# own noise, then thresholded and ramped to a soft 0..1 mask.
#
# The blur is what makes the gate work: the raw excess carries sigma 2.71e-04
# on M 101, but a 2 px Gaussian takes that to 6.11e-05 (0.23x), so a 2-sigma
# cut on the smoothed excess sits ~9 sigma above the raw sky. The ramp width
# feathers the mask edge so no hard seam appears around an HII knot.
HA_MASK_BLUR_PX = 2.0
HA_MASK_THRESHOLD_SIGMA = 2.0
HA_MASK_RAMP_SIGMA = 6.0

# Photometric color calibration (RGB/LRGB only; SHO is skipped).
#
# Sensor: IMX533 is covered by the catalog's combined IMX entry
# (mono_sensors/Sony_IMX.json, name "Sony IMX411/455/461/533/571").
#
# Filters: Scorpio Astro ScorPlat is not in the upstream SPCC catalog,
# so we ship our own visually-digitized entries at
# ~/.local/share/siril-spcc-database/mono_filters/Scorpio_Astro_ScorPlat_LRGB.json
# (dataQualityMarker=3 — manufacturer chart, no spectrophotometer).
# Edges accurate to ~+/- 2-5 nm, plateau heights to ~+/- 5%. Acceptable
# for pretty-picture calibration; replace with measured data if available.
SPCC_SENSOR = "Sony IMX411/455/461/533/571"
SPCC_R_FILTER = "Scorpio R"
SPCC_G_FILTER = "Scorpio G"
SPCC_B_FILTER = "Scorpio B"
SPCC_WHITE_REF = "Average Spiral Galaxy"

RE_DATE = r"\d{4}-\d{2}-\d{2}"
RE_LIGHTS = (
    r"^([\w -]+)_([\w]+)_([\d\.]+)s_(\d{4})_"
    r"([\d\.-]+)C_S(\d+)_H([\d\.]+)_R([\d\.]+)_([\d_-]+)\.fits$"
)
RE_FLATS = r"(FLAT)_([\w]+)_([\d\.]+s)"

FILTER_NAMES = {
    "S": "sii", "H": "ha", "O": "oiii",
    "L": "luminance", "R": "red", "G": "green", "B": "blue",
}
FILTER_DISPLAY_ORDER = {"L": 0, "R": 1, "G": 2, "B": 3, "S": 4, "H": 5, "O": 6}
FILTER_CODE_FROM_NAME = {v: k for k, v in FILTER_NAMES.items()}
# Pretty names for the post-run stats panel; the lowercased filter keys
# .title() poorly for the narrowband ones ("Sii", "Oiii").
FILTER_LABELS = {
    "luminance": "Luminance",
    "red": "Red",
    "green": "Green",
    "blue": "Blue",
    "sii": "SII",
    "ha": "Ha",
    "oiii": "OIII",
}
SHO_PALETTE_OPTIONS = ("SHO", "HOO", "OHS", "HSO", "Forax")

# GUI recombination label -> the file stem the pipeline writes for it.
RECOMBINATION_FILES = {
    "LRGB": "lrgb",
    "RGB": "rgb",
    "HaLRGB-R": "halrgb_r",
    "HaLRGB-L": "halrgb_l",
    "SHO": "sho",
    "HOO": "hoo",
    "OHS": "ohs",
    "HSO": "hso",
    "Forax": "forax",
}
MODE_LABEL_FROM_FILE = {v: k for k, v in RECOMBINATION_FILES.items()}


def mode_label(image: str) -> str:
    """File stem -> the mode as it is written in a filename.

    ``halrgb_r`` -> ``HaLRGB-R``, ``forax`` -> ``Forax``. Naive ``.upper()``
    would give ``HALRGB_R``, which is neither the GUI label nor the token the
    export convention and the GIMP legend plug-in expect.
    """
    return MODE_LABEL_FROM_FILE.get(image, image.upper())

# Most option labels read as filter codes when iterated char-by-char
# ("LRGB" -> L,R,G,B). The exceptions get explicit mappings.
OPTION_FILTER_CODES = {
    "Forax": "SHO",
    "HaLRGB-R": "LRGBH",
    "HaLRGB-L": "LRGBH",
}


def option_filter_codes(option: str) -> str:
    return OPTION_FILTER_CODES.get(option, option)


class ShootingMode(Enum):
    SHO = 1
    RGB = 2
    LRGB = 3
    HALRGB = 4


def order_filters(codes: Iterable[str]) -> str:
    return "".join(sorted(codes, key=lambda c: FILTER_DISPLAY_ORDER.get(c, 99)))


def get_dark(exposure: str) -> Path | None:
    # Dark masters are named with the exposure's trailing "s"
    # (master_darks_120.00s.fit). RE_FLATS captures that "s" as part of its
    # exposure group, but RE_LIGHTS does not — the "s" sits *outside* the
    # group (`([\d\.]+)s_`), so a light's exposure reaches here as "120.00".
    # Without re-suffixing it, get_dark("120.00") looks for a nonexistent
    # master_darks_120.00.fit, returns None, and every light calibrates
    # flat-only: no dark subtraction and no -cc=dark bad-pixel interpolation
    # (proven on 2026-07-15 M 51 subs: dark=False in the FITS HISTORY).
    # Normalise so both light and flat exposure tokens resolve.
    exp = exposure if exposure.endswith("s") else f"{exposure}s"
    candidate = DARK_PATH / f"master_darks_{exp}.fit"
    return candidate if candidate.exists() else None


# --- Metadata sidecar -------------------------------------------------------

# Author identity baked into every sidecar — overridable per-image by editing
# the YAML.
AUTHOR_NAME = "Vincent Berthier"
AUTHOR_EMAIL = "contact@astro-hibou.eu"

# Default privacy rounding for SITELAT / SITELONG — integer degrees gives
# ~110 km of positional ambiguity, enough to publish without leaking the
# imaging site. Override the value in the sidecar by hand if needed.
SITE_COORD_DECIMALS = 0


def _hget(header, key, default=None):
    """Fetch a FITS keyword, stripping string padding and treating empty
    strings as missing."""
    try:
        v = header[key]
    except KeyError:
        return default
    if isinstance(v, str):
        v = v.strip()
        return v if v else default
    return v


def _round_coord(value, decimals: int = SITE_COORD_DECIMALS):
    if value is None:
        return None
    return round(float(value), decimals) if decimals else round(float(value))


def build_metadata(
    fit_path: Path,
    *,
    mode: str | None = None,
    common_name_fr: str | None = None,
    common_name_en: str | None = None,
) -> dict:
    """Curate a FITS header into a publish-friendly dict.

    Site latitude/longitude are rounded to integer degrees by default; tweak
    SITE_COORD_DECIMALS or edit the sidecar to change precision.

    `common_name_fr` / `common_name_en` come from the astro_hibou GUI;
    empty strings normalise to None so the YAML key stays present but null.
    """
    with fits.open(fit_path) as hdul:
        h = hdul[0].header

    binning = None
    xb, yb = _hget(h, "XBINNING"), _hget(h, "YBINNING")
    if xb is not None and yb is not None:
        binning = f"{int(xb)}x{int(yb)}"

    return {
        "author": {
            "name": AUTHOR_NAME,
            "email": AUTHOR_EMAIL,
        },
        "target": {
            "name": _hget(h, "OBJECT"),
            # Common names: entered in the astro_hibou GUI, surfaced by
            # the GIMP legend plug-in and the JPG metadata injector.
            "common_name_fr": (common_name_fr or "").strip() or None,
            "common_name_en": (common_name_en or "").strip() or None,
            "ra_deg": _hget(h, "RA"),
            "dec_deg": _hget(h, "DEC"),
            "ra_hms": _hget(h, "OBJCTRA"),
            "dec_dms": _hget(h, "OBJCTDEC"),
        },
        "acquisition": {
            "mode": mode,
            "date_obs_utc": _hget(h, "DATE-OBS"),
            "date_avg_utc": _hget(h, "DATE-AVG"),
            "date_local": _hget(h, "DATE-LOC"),
            "frames_stacked": _hget(h, "STACKCNT"),
            "sub_exposure_s": _hget(h, "EXPTIME"),
            "total_integration_s": _hget(h, "LIVETIME"),
            "airmass": _hget(h, "AIRMASS"),
            "altitude_deg": _hget(h, "CENTALT"),
            "azimuth_deg": _hget(h, "CENTAZ"),
        },
        "equipment": {
            "telescope": _hget(h, "TELESCOP"),
            "camera": _hget(h, "INSTRUME"),
            "filter_wheel": _hget(h, "FWHEEL"),
            "focuser": _hget(h, "FOCNAME"),
            "focal_length_mm": _hget(h, "FOCALLEN"),
            "focal_ratio": _hget(h, "FOCRATIO"),
            "pixel_size_um": _hget(h, "XPIXSZ"),
            "binning": binning,
            "gain": _hget(h, "GAIN"),
            "offset": _hget(h, "OFFSET"),
            "sensor_temp_c": _hget(h, "CCD-TEMP"),
        },
        "site": {
            "latitude_deg": _round_coord(_hget(h, "SITELAT")),
            "longitude_deg": _round_coord(_hget(h, "SITELONG")),
            "elevation_m": _hget(h, "SITEELEV"),
        },
        "conditions": {
            "ambient_temp_c": _hget(h, "AMBTEMP"),
            "humidity_pct": _hget(h, "HUMIDITY"),
            "pressure_hpa": _hget(h, "PRESSURE"),
            "dewpoint_c": _hget(h, "DEWPOINT"),
            "cloud_cover_pct": _hget(h, "CLOUDCVR"),
            "wind_dir_deg": _hget(h, "WINDDIR"),
            "wind_speed_kph": _hget(h, "WINDSPD"),
            "wind_gust_kph": _hget(h, "WINDGUST"),
        },
        "processing": {
            "software": _hget(h, "PROGRAM"),
            "plate_solved": bool(_hget(h, "PLTSOLVD", False)),
        },
    }


def _patch_sidecar_target(
    sidecar: Path,
    *,
    common_name_fr: str | None = None,
    common_name_en: str | None = None,
) -> None:
    """Sync target.common_name_fr / target.common_name_en in an existing
    sidecar without touching anything else. Preserves the leading comment
    header. None = leave the field alone, "" = clear it."""
    text = sidecar.read_text(encoding="utf-8")
    lines = text.splitlines(keepends=True)
    i = 0
    while i < len(lines):
        stripped = lines[i].lstrip()
        if not stripped or stripped.startswith("#"):
            i += 1
            continue
        break
    preamble = "".join(lines[:i])
    body = "".join(lines[i:])
    data = yaml.safe_load(body) or {}
    target = data.setdefault("target", {})
    if common_name_fr is not None:
        target["common_name_fr"] = common_name_fr.strip() or None
    if common_name_en is not None:
        target["common_name_en"] = common_name_en.strip() or None
    new_body = yaml.safe_dump(data, sort_keys=False, allow_unicode=True)
    sidecar.write_text(preamble + new_body, encoding="utf-8")


def write_metadata_sidecar(
    fit_path: Path,
    *,
    mode: str | None = None,
    common_name_fr: str | None = None,
    common_name_en: str | None = None,
    overwrite: bool = False,
) -> Path | None:
    """Write a YAML sidecar of curated FITS metadata next to `fit_path`.

    Existing sidecars are not regenerated wholesale (so hand-edited fields
    survive), but the FR/EN common-name fields are kept in sync with the
    values from the current pipeline run.
    """
    sidecar = fit_path.with_name(fit_path.name + ".meta.yaml")
    if sidecar.exists() and not overwrite:
        if common_name_fr is not None or common_name_en is not None:
            _patch_sidecar_target(
                sidecar,
                common_name_fr=common_name_fr,
                common_name_en=common_name_en,
            )
        return sidecar
    if not fit_path.exists():
        return None
    meta = build_metadata(
        fit_path,
        mode=mode,
        common_name_fr=common_name_fr,
        common_name_en=common_name_en,
    )
    with open(sidecar, "w") as f:
        f.write(
            "# Metadata sidecar — generated from the FITS header.\n"
            "# Edit freely: the pipeline never overwrites an existing file.\n"
            f"# Source: {fit_path.name}\n\n"
        )
        yaml.safe_dump(meta, f, sort_keys=False, allow_unicode=True)
    return sidecar


# --- Common-name cache (per target root) ------------------------------------
# The object nicknames also land in the end-of-run metadata sidecar, but that
# is only written once do_process completes. To avoid re-typing them when a run
# crashes or is stopped early (the sidecar never gets written), they are cached
# here the moment a run starts and read back to pre-fill the launcher fields.
COMMON_NAMES_CACHE = ".common_names.yaml"


def save_common_names(root: Path, fr: str | None, en: str | None) -> None:
    """Persist FR/EN object nicknames under `root` immediately, decoupled from
    the end-of-run sidecar. Best-effort — never raises, never writes an empty
    cache over a good one."""
    fr = (fr or "").strip()
    en = (en or "").strip()
    if not (fr or en):
        return
    try:
        (root / COMMON_NAMES_CACHE).write_text(
            yaml.safe_dump(
                {"common_name_fr": fr or None, "common_name_en": en or None},
                allow_unicode=True,
                sort_keys=False,
            ),
            encoding="utf-8",
        )
    except OSError:
        pass


def load_common_names(root: Path) -> tuple[str, str]:
    """Return (fr, en) from the per-target cache, or ("", "") if absent."""
    try:
        data = yaml.safe_load(
            (root / COMMON_NAMES_CACHE).read_text(encoding="utf-8")
        )
    except (OSError, yaml.YAMLError):
        return "", ""
    data = data or {}
    return (
        (data.get("common_name_fr") or "").strip(),
        (data.get("common_name_en") or "").strip(),
    )


# --- Step + History ---------------------------------------------------------


@dataclass(frozen=True)
class Step:
    cwd: str
    algo: str
    detail: str = ""

    def __str__(self) -> str:
        return f"{self.cwd}:{self.algo}:{self.detail}"

    @classmethod
    def parse(cls, line: str) -> "Step":
        cwd, algo, detail = line.split(":", 2)
        return cls(cwd=cwd, algo=algo, detail=detail)


class History:
    """Append-only record of completed pipeline steps with completion times.

    A step is "still done" if both:
      - every declared output file exists, and
      - no declared input file has an mtime newer than the step's completion.

    Either condition failing invalidates the entry, so a stale recombination
    re-runs the moment its master inputs are refreshed underneath it.
    """

    def __init__(self, root: Path) -> None:
        self.file = root / ".history"
        self.records: dict[Step, float] = {}
        if self.file.exists():
            self._load()

    def clear(self) -> None:
        self.records.clear()
        if self.file.exists():
            self.file.unlink()

    def _load(self) -> None:
        # Legacy format: "cwd:algo:detail\n" (no timestamp).
        # Current format: "cwd:algo:detail\tmtime\n".
        # Legacy entries fall back to the file's mtime — old enough never to
        # invalidate steps spuriously while migration happens organically.
        fallback = self.file.stat().st_mtime
        with open(self.file) as f:
            for line in f:
                line = line.rstrip("\n")
                if not line:
                    continue
                if "\t" in line:
                    step_part, ts_part = line.split("\t", 1)
                    try:
                        ts = float(ts_part)
                    except ValueError:
                        ts = fallback
                else:
                    step_part, ts = line, fallback
                try:
                    self.records[Step.parse(step_part)] = ts
                except ValueError:
                    continue

    def _rewrite(self) -> None:
        with open(self.file, "w") as f:
            for step, ts in self.records.items():
                f.write(f"{step}\t{ts}\n")

    def is_done(
        self,
        cwd: Path | str,
        algo: str,
        detail: str = "",
        *,
        outputs: Iterable[Path] = (),
        inputs: Iterable[Path] = (),
    ) -> bool:
        step = Step(str(cwd), algo, detail)
        if step not in self.records:
            return False
        completed_at = self.records[step]
        for out in outputs:
            if not Path(out).exists():
                self._invalidate(step)
                return False
        for inp in inputs:
            p = Path(inp)
            if p.exists() and p.stat().st_mtime > completed_at:
                self._invalidate(step)
                return False
        return True

    def mark_done(self, cwd: Path | str, algo: str, detail: str = "") -> None:
        step = Step(str(cwd), algo, detail)
        ts = time.time()
        self.records[step] = ts
        with open(self.file, "a") as f:
            f.write(f"{step}\t{ts}\n")

    def invalidate(self, cwd: Path | str, algo: str, detail: str = "") -> None:
        step = Step(str(cwd), algo, detail)
        if step in self.records:
            self._invalidate(step)

    def _invalidate(self, step: Step) -> None:
        del self.records[step]
        self._rewrite()


# --- Frame quarantine -------------------------------------------------------


class FramesQuarantined(Exception):
    """Unusable frames were moved out of LIGHTS/; the caller must rebuild.

    Carries the raw light paths that were moved so the caller can drop them
    from its file list before retrying.
    """

    def __init__(self, disposed: list[Path], reasons: dict[Path, str]) -> None:
        super().__init__(f"quarantined {len(disposed)} frame(s)")
        self.disposed = disposed
        self.reasons = reasons


# eq=False: the default __eq__ would compare `matrix` element-wise and return
# an array, so `frame in frames` would raise on the ambiguous truth value.
@dataclass(eq=False)
class SeqFrame:
    """One image's registration record, parsed out of a Siril `.seq` file."""

    index: int  # 1-based image number within the sequence
    selected: bool
    matrix: np.ndarray | None  # 3x3 homography mapping this frame onto the ref


def read_seq_registration(seq_path: Path) -> list[SeqFrame]:
    """Parse the `I` (selection) and `R<layer>` (registration) lines of a .seq.

    Siril writes one `I <filenum> <selected>` line per image and, once
    `register` has run, one `R0 fwhm wfwhm roundness bg noise nbstars H h00 h01
    h02 h10 h11 h12 h20 h21 h22` line per image, both in sequence order. The
    reference frame carries the identity matrix.

    Returns [] when the file cannot be parsed or the two blocks disagree in
    length — callers must treat that as "cannot judge" and skip quarantine
    rather than guess.
    """
    try:
        lines = seq_path.read_text().splitlines()
    except OSError:
        return []

    selected: list[bool] = []
    matrices: list[np.ndarray | None] = []
    for line in lines:
        if line.startswith("I "):
            parts = line.split()
            # "I <filenum> <selected>"
            selected.append(len(parts) >= 3 and parts[2] != "0")
        elif line.startswith("R") and " H " in line:
            tail = line.split(" H ", 1)[1].split()
            if len(tail) < 9:
                matrices.append(None)
                continue
            try:
                vals = [float(v) for v in tail[:9]]
            except ValueError:
                matrices.append(None)
                continue
            matrices.append(np.array(vals, dtype=float).reshape(3, 3))

    if not selected or len(selected) != len(matrices):
        return []
    return [
        SeqFrame(index=i + 1, selected=sel, matrix=m)
        for i, (sel, m) in enumerate(zip(selected, matrices))
    ]


def _rotation_deg(matrix: np.ndarray) -> float:
    """Rotation encoded by a homography's linear part, in (-180, 180]."""
    return float(np.degrees(np.arctan2(matrix[1, 0], matrix[0, 0])))


def _frame_footprint(
    matrix: np.ndarray, width: int, height: int
) -> np.ndarray:
    """The frame's four corners mapped into reference space by its homography.

    Siril's registration matrix maps a frame's pixel coordinates onto the
    reference frame, so this is where the sub's field of view lands once
    aligned — exactly the polygon `-framing=min` intersects.
    """
    corners = np.array(
        [[0, 0, 1], [width, 0, 1], [width, height, 1], [0, height, 1]],
        dtype=float,
    )
    mapped = corners @ matrix.T
    return mapped[:, :2] / mapped[:, 2:3]


def _convex_overlap_area(subject: np.ndarray, clipper: np.ndarray) -> float:
    """Area of the intersection of two convex polygons (Sutherland-Hodgman).

    Both footprints are convex quads, so clipping `subject` against every edge
    of `clipper` yields their intersection; its shoelace area is what we want.
    """

    def inside(p, a, b):
        return (b[0] - a[0]) * (p[1] - a[1]) - (b[1] - a[1]) * (p[0] - a[0]) >= 0

    def intersect(s, e, a, b):
        dc = (a[0] - b[0], a[1] - b[1])
        dp = (s[0] - e[0], s[1] - e[1])
        n1 = a[0] * b[1] - a[1] * b[0]
        n2 = s[0] * e[1] - s[1] * e[0]
        den = dc[0] * dp[1] - dc[1] * dp[0]
        if abs(den) < 1e-12:
            return s
        return np.array(
            [(n1 * dp[0] - n2 * dc[0]) / den, (n1 * dp[1] - n2 * dc[1]) / den]
        )

    def as_ccw(poly):
        p = np.asarray(poly, dtype=float)
        x, y = p[:, 0], p[:, 1]
        signed = 0.5 * (np.dot(x, np.roll(y, 1)) - np.dot(y, np.roll(x, 1)))
        return p if signed < 0 else p[::-1]

    clip = as_ccw(clipper)
    out = list(as_ccw(subject))
    for i in range(len(clip)):
        a, b = clip[i], clip[(i + 1) % len(clip)]
        if not out:
            break
        prev = out[-1]
        clipped = []
        for cur in out:
            if inside(cur, a, b):
                if not inside(prev, a, b):
                    clipped.append(intersect(prev, cur, a, b))
                clipped.append(cur)
            elif inside(prev, a, b):
                clipped.append(intersect(prev, cur, a, b))
            prev = cur
        out = clipped
    if len(out) < 3:
        return 0.0
    p = np.asarray(out, dtype=float)
    x, y = p[:, 0], p[:, 1]
    return 0.5 * abs(np.dot(x, np.roll(y, 1)) - np.dot(y, np.roll(x, 1)))


def find_framing_outliers(
    frames: list[SeqFrame], width: int, height: int
) -> dict[int, str]:
    """Return {frame_index: reason} for frames that break `-framing=min`.

    A frame is an outlier when its registered footprint overlaps the *rest of
    the sequence* too little (below QUARANTINE_MIN_OVERLAP of the frame area).
    Overlap is judged pairwise and reduced by the median, so the verdict rests
    on the majority framing, not on the 2-pass reference: Siril picks that
    reference on image quality, so it can itself be the odd one out (a sharp
    first sub taken before the camera was nudged), and a median over the other
    frames still puts a lone rogue below threshold while leaving the majority
    above it.

    Overlap, not rotation angle, is the criterion because the sensor is square:
    a rotation about the field centre — including a ~180 deg cross-night
    meridian flip — barely shrinks the common area that `-framing=min` keeps,
    whereas a failed recenter or a shifted train collapses it. A raw rotation
    threshold cannot tell those apart and used to dispose perfectly registrable
    meridian-flipped subs.

    Returns {} when the sequence is too short to judge. The caller still has to
    apply the minority guard (QUARANTINE_MAX_OUTLIER_FRAC) before acting.
    """
    if len(frames) < QUARANTINE_MIN_FRAMES:
        return {}

    outliers: dict[int, str] = {}
    usable = [f for f in frames if f.selected and f.matrix is not None]
    usable_idx = {f.index for f in usable}
    for f in frames:
        if f.index not in usable_idx:
            outliers[f.index] = "registration failed (no star match)"
    if len(usable) < QUARANTINE_MIN_FRAMES:
        return {}

    area = float(width * height)
    footprints = {
        f.index: _frame_footprint(f.matrix, width, height) for f in usable
    }
    for f in usable:
        overlaps = sorted(
            _convex_overlap_area(footprints[f.index], footprints[g.index])
            / area
            for g in usable
            if g.index != f.index
        )
        median = float(np.median(overlaps))
        if median < QUARANTINE_MIN_OVERLAP:
            outliers[f.index] = (
                f"overlaps only {median:.0%} of the frame with the rest of "
                f"the sequence (rotated {_rotation_deg(f.matrix):+.1f} deg)"
            )

    return outliers


# --- Siril helpers ----------------------------------------------------------


def siril_cwd(siril) -> Path:
    return Path(siril.get_siril_wd())


def siril_cd(siril, path) -> None:
    siril.cmd("cd", f'"{path}"')


@contextmanager
def cwd_at(siril, path) -> Iterator[None]:
    """Run a block with the Siril working directory set to `path`,
    restoring the previous one on exit even if the block raises.
    """
    previous = siril_cwd(siril)
    siril_cd(siril, path)
    try:
        yield
    finally:
        siril_cd(siril, previous)


# --- Pipeline ---------------------------------------------------------------


class PipelineCancelled(Exception):
    """Raised inside Pipeline when the worker has been asked to stop."""


class Pipeline:
    """Siril processing pipeline; UI-agnostic.

    All Siril work lives here so it can be exercised from the GUI, a future
    CLI, or tests without dragging Qt along.

    Two optional hooks let an outside caller (typically a QThread worker)
    observe and steer execution:
      - `progress_callback(msg)` is invoked at every stage announcement.
      - `cancel_check()` runs at the same checkpoints; raise
        PipelineCancelled to stop work cleanly between Siril commands.
    """

    def __init__(self, siril, root_dir: Path) -> None:
        self.siril = siril
        self.root_dir = root_dir
        self.history = History(root_dir)
        self.progress_callback: Callable[[str], None] | None = None
        self.cancel_check: Callable[[], None] | None = None
        # Manual-crop pause: when set, the pipeline loads each recombined
        # master and blocks in pause_callback until the user has cropped it
        # by hand in Siril and pressed Continue. Used instead of the automatic
        # coverage crop, which cannot reliably guess a mosaic's crop.
        self.pause_callback: Callable[[str], None] | None = None
        self.manual_crop: bool = False
        # Tunable post-processing knobs; the GUI overrides per run.
        # deconv_strength -> SyQon Parallax sharpen alpha; denoise_strength
        # -> SyQon Prism modulation. Both 0..1.
        #
        # These are NOT intensity dials — they are **blend fractions against
        # the unprocessed input**:
        #     Parallax: out = in + alpha * (sharpened - in)
        #     Prism:    out = modulation * denoised + (1 - modulation) * in
        # so 0.5 does not mean "denoise moderately", it means "keep half the
        # noise". Measured on M 101: at modulation 0.5 the master's
        # high-frequency noise fell only 2x (4.98e-05 -> 2.51e-05), while the
        # same frame at modulation 1.0 fell 173x (-> 2.88e-07).
        #
        # SyQon's own defaults are 1.0 for both, and 1.0 is right for both.
        #
        # Prism does leave a smooth low-frequency residual, and modulation
        # scales the grain far faster than it scales that residual — which is
        # why this knob sat at 0.85 for a while, keeping enough grain to hide
        # the residual. That was treating the symptom. Measured on M 101's
        # background pixels, at 256-px blocks, Prism's residual is 2.3x what
        # block-averaging the noise it legitimately removed would produce, so
        # the invented structure is real; but its amplitude is ~4e-07 against a
        # per-pixel sigma of 4.5e-05, i.e. ~21 % of the field's *real* sky
        # structure (the grey dust/IFN this field is known for). Correlation
        # length 250-350 px; not a tiling artifact (phase modulation against
        # Prism's 512-px tile and 256-px stride is 3-4 %, at arbitrary phase).
        #
        # What made it look catastrophic was never the denoise: it was letting
        # a stretch derive its black point from the denoised frame's sigma.
        # Autostretching starless_lrgb_denoised.fit yields a midtone 6.2x
        # harsher than the deconvolved frame's (0.000061 vs 0.000379, sigma
        # 7.2e-06 vs 4.5e-05), which is what erupts as coloured continents, a
        # dark halo and a blown core. Stretching the identical pixels with the
        # pre-denoise parameters gives a clean, neutral sky. See
        # _autostretch_params, _stretch_hint, and the preview JPEG that
        # _write_stretch_preview drops next to the checkpoint so a glance at
        # the hand-off point can never mislead the way Siril's *display*
        # autostretch does.
        #
        # denoise_strength is 0.90, NOT 1.0.  _Changed 2026-07-12; the operator
        # tried 90 % in Prism's GUI and preferred the result, and the numbers
        # back it._
        #
        # `modulation` is a blend: out = m*denoised + (1-m)*input.  At m=0.90
        # you keep 10 % of the original noise.  What matters is not the grain
        # itself but what it does to the RATIO between Prism's invented
        # low-frequency residual and the noise that survives beside it -
        # measured on M 101's LRGB master:
        #
        #     m     bg sigma     residual     residual/noise
        #     1.00  2.46e-06     2.94e-05        11.9
        #     0.90  4.07e-06     2.65e-05         6.5
        #     0.85  5.32e-06     2.50e-05         4.7
        #
        # The residual is nearly unchanged in absolute terms; only the noise
        # comes back.  At m=1.0 the residual is 12x the surviving noise, i.e.
        # the dominant structure in the background, and every sigma-derived
        # stretch downstream (HyperMetric's adaptive anchor, Revela's noise
        # gate, Siril's autostretch) then keys off a sigma that no longer
        # describes the frame.  0.90 roughly halves that ratio for 10 % of the
        # noise back.
        #
        # This partially rehabilitates the old 0.85 setting, which was dropped
        # on 2026-07-10 as "grain to hide a residual".  The grain is not hiding
        # the residual; it is restoring the scale the rest of the chain measures
        # against.
        self.deconv_strength: float = 1.0
        self.denoise_strength: float = 0.90
        # Cluster mode swaps the deepsky do_process path for one tailored
        # to star fields (no star removal, full-image deconv + denoise).
        self.cluster_mode: bool = False
        # Peak weight of Ha in the HaLRGB-R/L blends, applied *through the
        # emission mask*: channel = base + w * mask * (Ha - base). See
        # _blend_ha. In the sky mask=0, so w costs nothing there; inside an
        # HII knot mask=1 and w is the full blend fraction. It is therefore a
        # purely aesthetic knob again — raise it freely for redder knots.
        #
        # It did NOT used to be. The old blend was global — (1-w)*base + w*Ha
        # over every pixel — and Ha is a 3 nm band that linear_match scales up
        # ~4x to sit at the base's level, dragging its noise along. Measured on
        # M 101 (23 L subs, 9 Ha subs), whole-frame robust sigma:
        #
        #   aligned_red  6.60e-05     aligned_ha (matched to R)  2.63e-04  4.0x
        #   aligned_lum  7.51e-05     aligned_ha (matched to L)  3.59e-04  4.8x
        #
        # Real Ha excess covers 0.78 % of the frame at 3 sigma and 0.062 % at
        # 5 sigma. A global weight pays Ha's noise on the other 99 %, buying
        # signal on almost none of it. At w=0.30 that made red the noisiest
        # channel by far — 74.5 % of its variance was Ha — and the sky read
        # *brown* despite an exactly neutral median. It is chroma noise, not a
        # cast, so background neutralisation could never touch it:
        #
        #   config              sigma_R   vs red  P(R greatest)  knot Ha kept
        #   pure red (w=0)     6.60e-05   1.000x     36.0 %          77.7 %
        #   global w=0.30      9.41e-05   1.426x     39.3 %         100.0 %
        #   masked w=0.30      6.60e-05   1.000x     36.1 %          99.8 %
        #
        # The masked blend is not a trade: it recovers 99.8 % of the Ha the
        # global blend delivered to the knots, at zero measurable noise cost.
        # The global blend spent +43 % red noise across the whole frame to buy
        # the last 22 % of knot signal. Same story in luminance, worse: the
        # global blend made blended_luminance 1.64x noisier than pure L, 80.8 %
        # of its variance Ha — on the one channel that carries all the detail.
        self.ha_weight: float = 0.5
        # The pre-stretch checkpoint (_STRETCH_ME pair) is always written; it
        # is the hand-off point where the automated pipeline stops and manual
        # stretching begins. The optional interactive VeraLux continuation
        # past this point lives in astro_hibou_veralux.py, not here.
        self.write_stretch_me: bool = True
        # Common names (FR/EN) entered in the GUI; threaded into the
        # YAML sidecar at the end of each per-target pipeline run.
        self.common_name_fr: str | None = None
        self.common_name_en: str | None = None
        # The data-night currently being processed; threaded into _step
        # so logs read e.g. "[2026-04-07] Master flat: blue".
        self.current_day: str | None = None
        # The mosaic panel currently being processed (mosaic runs only);
        # _step leads with it, so logs read e.g.
        # "[Panel 4] [2026-04-07] Master flat: blue".
        self.current_panel: str | None = None

    # --- low-level helpers ---------------------------------------------

    def cwd(self) -> Path:
        return siril_cwd(self.siril)

    def cd(self, path) -> None:
        siril_cd(self.siril, path)

    def open_image(self, image_name) -> None:
        self.siril.cmd("load", f'"{image_name}"')

    def _load_master(self, name) -> None:
        """Load a full-frame recombined master for post-processing, closing
        any currently loaded image first.

        Works around a Siril **GUI** segfault: loading a large master (653 MB
        for this mosaic) while another large master is already loaded crashes
        during the pre-load purge of reference-frame data. In the crash logs
        `load lrgb` (prior state: a sequence) succeeded, but the very next
        `load lrgb_deconvolved` (prior state: lrgb already loaded) segfaulted
        — the replace-huge-with-huge transition is the trigger. `close` frees
        the current image via a safe path so the fresh load starts from a
        clean slate. Headless (siril-cli) never hit this; it's GUI-only, and
        `close` with nothing loaded is a harmless no-op.
        """
        self.siril.cmd("close")
        self.siril.cmd("load", f'"{name}"')

    def _step(self, message: str) -> None:
        """Announce a stage: yield to a pending cancel, log to siril, and
        emit a progress event. Use at the top of each user-visible stage.

        The message leads with the mosaic panel currently being processed
        (when one is set), then the data-night — e.g.
        "[Panel 4] [2025-08-13] Master flat: red". A single-target run has no
        panel, and cross-day / post-recombination stages have no day, so the
        respective bracket is simply omitted.
        """
        if self.cancel_check is not None:
            self.cancel_check()
        prefix = ""
        if self.current_panel:
            prefix += f"[{self.current_panel}] "
        if self.current_day:
            prefix += f"[{self.current_day}] "
        stamped = f"{prefix}{message}"
        self.siril.log(stamped)
        if self.progress_callback is not None:
            self.progress_callback(stamped)

    def _pause(self, message: str) -> None:
        """Block until the user resumes (via pause_callback), e.g. after
        loading a recombined master so it can be cropped by hand. No-op when
        no pause_callback is wired (headless), so the pipeline just proceeds.
        """
        self.siril.log(stamped := message)
        if self.progress_callback is not None:
            self.progress_callback(stamped)
        if self.pause_callback is not None:
            self.pause_callback(message)

    @contextmanager
    def _day_context(self, day: str) -> Iterator[None]:
        previous = self.current_day
        self.current_day = day
        try:
            yield
        finally:
            self.current_day = previous

    @contextmanager
    def _panel_context(self, panel: str) -> Iterator[None]:
        previous = self.current_panel
        self.current_panel = panel
        try:
            yield
        finally:
            self.current_panel = previous

    def get_filter_files_exposure(
        self, regex: str
    ) -> tuple[dict[str, list[str]], dict[str, str]]:
        source_dir = self.cwd()
        filter_files: dict[str, list[str]] = {}
        filter_exposure: dict[str, str] = {}
        for entry in source_dir.iterdir():
            if not entry.is_file():
                continue
            m = re.search(regex, entry.name)
            if not m:
                continue
            filter_type = m.group(2).lower()
            filter_files.setdefault(filter_type, []).append(entry.name)
            filter_exposure[filter_type] = m.group(3)
        return filter_files, filter_exposure

    @staticmethod
    def _target_filter_names(options: list[str]) -> set[str]:
        target: set[str] = set()
        for opt in options:
            for code in option_filter_codes(opt):
                target.add(FILTER_NAMES[code])
        return target

    # --- top-level dispatch -------------------------------------------

    def discover_days(self, target_dir: Path) -> list[str]:
        """List the data-nights inside a target directory.

        A target laid out with LIGHTS+FLATS at its root is a single "day"
        whose label is the folder name; otherwise every `YYYY-MM-DD`
        subdirectory is a night. Mirrors get_available_days() but for an
        arbitrary directory rather than the Siril working directory.
        """
        if (target_dir / "LIGHTS").is_dir() and (
            target_dir / "FLATS"
        ).is_dir():
            return [target_dir.stem]
        return sorted(
            f.name
            for f in target_dir.iterdir()
            if f.is_dir() and re.search(RE_DATE, f.name)
        )

    def build_masters_for_target(
        self,
        target_dir: Path,
        target_filters: set[str],
        days: list[str] | None = None,
    ) -> tuple[set[str], Path]:
        """Build per-filter `master_<filter>.fit` files for one target.

        Handles all three on-disk layouts uniformly and returns the set of
        filters actually produced plus the `process/` directory that holds
        the masters (so the caller can recombine there, or — for a mosaic —
        gather each panel's masters):

          - LIGHTS+FLATS at the target root         → masters in <target>/process
          - a single `YYYY-MM-DD` night subdirectory → masters in <target>/<day>/process
          - several night subdirectories             → masters pooled across
            nights into <target>/process (the multi-night "gold standard")

        Background extraction runs per target: on each master for the
        single-night layouts, and once on the pooled combined master for the
        multi-night layout (deferred inside _combine_filter_across_days).
        """
        all_days = self.discover_days(target_dir)
        days = days if days else all_days

        # Single-night, lights at the target root: masters land in
        # <target>/process, gradients removed per master.
        if (target_dir / "LIGHTS").is_dir():
            with self._day_context(target_dir.stem):
                with cwd_at(self.siril, target_dir):
                    self.prepare_flats(target_filters)
                    produced = self.prepare_channels(
                        target_filters, extract_background=True
                    )
            return set(produced), target_dir / "process"

        # Single-night in a dated subdirectory: masters land in
        # <target>/<day>/process.
        if len(days) == 1:
            day = days[0]
            with self._day_context(day):
                with cwd_at(self.siril, target_dir / day):
                    self.prepare_flats(target_filters)
                    produced = self.prepare_channels(
                        target_filters, extract_background=True
                    )
            return set(produced), target_dir / day / "process"

        # Multi-night: per-night calibrate (BGE deferred), then pool every
        # night's calibrated subs into one registration + stack per filter,
        # with a single BGE pass on the combined master.
        (target_dir / "process").mkdir(exist_ok=True)
        all_filters: set[str] = set()
        for day in days:
            with self._day_context(day):
                self._step(f"Day {day}")
                with cwd_at(self.siril, target_dir / day):
                    self.prepare_flats(target_filters)
                    day_filters = self.prepare_channels(
                        target_filters, extract_background=False
                    )
            all_filters.update(day_filters)
        for filter_name in sorted(all_filters):
            self._combine_filter_across_days(target_dir, filter_name, days)
        return all_filters, target_dir / "process"

    def process_target(
        self, days: list[str], mode: str, options: list[str]
    ) -> None:
        """Full single-target pipeline: build the channel masters, recombine
        (LRGB+SPCC / SHO / OHS / ...), and — in full mode — continue into
        deconv/denoise/star-removal to the linear pre-stretch checkpoint.

        `days` is the user-selected subset of nights (empty/None = all).
        """
        start_dir = self.cwd()
        target_filters = self._target_filter_names(options)
        _produced, process_dir = self.build_masters_for_target(
            start_dir, target_filters, days
        )
        # compose()/process() operate in <cwd>/process, so put the working
        # directory at the parent of the directory that holds the masters —
        # the target root for root/multi-night layouts, the night dir for a
        # single dated subdirectory.
        with cwd_at(self.siril, process_dir.parent):
            self.compose(options)
            if mode == "full":
                self.process(options)
        self.cd(start_dir)

    def _combine_filter_across_days(
        self, start_dir: Path, filter_name: str, allowed_days: list[str]
    ) -> None:
        """Pool every night's calibrated subs for one filter into a single
        registration + stack — the multi-night equivalent of
        create_master_channel.

        We pool the *calibrated* frames (pp_<filter>_*.fit) from each night,
        NOT the per-night masters, and register them all to one common
        reference before a single stack. That gives optimal per-sub noise
        weighting and lets pixel rejection act across nights (e.g. a satellite
        trail present on only one night). A master-of-masters stack, by
        contrast, weights a thin night equally with a deep one and can leave
        the result worse than the deep night alone.

        Background extraction runs once here, on the combined master. The
        trade-off: if two nights carry strongly different gradients, GraXpert
        models a single blended gradient rather than one per night. If that
        ever bites, the fallback is per-night BGE plus an nbstack-weighted
        master-of-masters.
        """
        process_dir = start_dir / "process"
        filter_dir = process_dir / filter_name
        master_path = process_dir / f"master_{filter_name}.fit"

        # Gather the calibrated subs every allowed night produced for this
        # filter. They live in <day>/process as pp_<filter>_NNNNN.fit, written
        # by create_master_channel's calibrate step.
        sub_re = re.compile(rf"^pp_{re.escape(filter_name)}_\d+\.fits?$")
        sources: list[tuple[str, Path]] = []
        for day in allowed_days:
            day_process = start_dir / day / "process"
            if not day_process.is_dir():
                continue
            for f in sorted(day_process.iterdir()):
                if f.is_file() and sub_re.match(f.name):
                    sources.append((day, f))

        if not sources:
            self.siril.log(
                f"No calibrated subs for {filter_name}; skipping combine"
            )
            return

        source_paths = [p for _, p in sources]
        if self.history.is_done(
            process_dir,
            "combine_filter_across_days",
            detail=filter_name,
            outputs=[master_path],
            inputs=source_paths,
        ):
            self.siril.log(
                f"Combined master for {filter_name} up to date, skipping"
            )
            return

        self._step(
            f"Combining {filter_name}: {len(sources)} subs "
            f"across {len(allowed_days)} nights"
        )

        # Rebuild the pool dir from scratch so stale links from a prior run
        # (or the old master-of-masters layout) can't leak into the sequence.
        if filter_dir.exists():
            shutil.rmtree(filter_dir)
        filter_dir.mkdir(parents=True, exist_ok=True)
        # Night-prefixed names keep frames unique across nights and ordered by
        # night; `link` then indexes them into one pp_<filter> sequence. We
        # link rather than convert to avoid duplicating hundreds of subs on
        # disk — only the registered output is written out (Corrbolg is the
        # only copy of this data).
        for day, src in sources:
            (filter_dir / f"{day}_{src.name}").symlink_to(src)

        # The sequence is rebuilt from the current subs; clear the inner
        # register/stack/bge records so they re-run instead of short-circuiting
        # on a previous combine.
        self.history.invalidate(
            process_dir, "register_lights", detail=filter_name
        )
        self.history.invalidate(
            process_dir, "stack_lights", detail=f"r_pp_{filter_name}"
        )
        self.history.invalidate(
            process_dir, "extract_bg", detail=filter_name
        )
        # Same hazard as the per-night convert: `link -out=../` overwrites the
        # indices it needs and leaves higher ones behind, so a night that lost a
        # sub to DISPOSED/ strands a dangling `pp_<filter>_000NN.fit` that the
        # directory rescan still counts.
        self._clear_converted_sequence(process_dir, f"pp_{filter_name}")
        with cwd_at(self.siril, filter_dir):
            self.siril.cmd("link", f"pp_{filter_name}", "-out=../")
        with cwd_at(self.siril, process_dir):
            self.register_lights(filter_name)
            # Full quality filters + per-sub weighting now apply: the pool is
            # real subs, so winsorized rejection and the wfwhm weight are valid
            # and the per-sub weighting is automatically correct.
            self.stack_lights(f"r_pp_{filter_name}", len(sources))
            self.extract_bg(filter_name)
        self.history.mark_done(
            process_dir, "combine_filter_across_days", detail=filter_name
        )

    # --- flats ---------------------------------------------------------

    def prepare_flats(self, filters: set[str]) -> None:
        # No outer guard: create_master_flat already tracks each filter's
        # FLATS sources as inputs and the master as output, so a re-shoot
        # of any filter's flats invalidates that filter's master while
        # untouched filters skip cleanly. A wrapper-level "done" record
        # would mask those per-filter checks.
        day_dir = self.cwd()
        self._step(f"Preparing flats: {day_dir.name}")
        with cwd_at(self.siril, day_dir / "FLATS"):
            filter_files, filter_exposure = self.get_filter_files_exposure(
                RE_FLATS
            )
            for filter_type, files in filter_files.items():
                if filter_type not in filters:
                    continue
                self.create_master_flat(
                    filter_type, files, filter_exposure[filter_type]
                )

    def create_master_flat(
        self, filter_type: str, files: list[str], exposure: str
    ) -> None:
        self._step(f"Master flat: {filter_type}")
        flats_dir = self.cwd()  # day/FLATS
        process_dir = flats_dir.parent / "process"
        master_path = process_dir / f"master_flats_{filter_type}.fit"
        source_paths = [flats_dir / f for f in files]
        if self.history.is_done(
            flats_dir,
            "create_master_flat",
            detail=filter_type,
            outputs=[master_path],
            inputs=source_paths,
        ):
            self.siril.log("Step already done, skipping")
            return

        seq_dir = process_dir / f"flats_{filter_type}"
        if seq_dir.exists():
            shutil.rmtree(seq_dir)
        seq_dir.mkdir(parents=True, exist_ok=True)
        for f in files:
            (seq_dir / f).symlink_to(flats_dir / f)

        seq_name = f"flats_{filter_type}"
        self._clear_converted_sequence(process_dir, seq_name)
        with cwd_at(self.siril, seq_dir):
            self.siril.log("Converting files")
            self.siril.cmd("convert", seq_name, "-out=../")
        with cwd_at(self.siril, process_dir):
            self.calibrate_flats(seq_name, exposure)
            self.stack_flats(f"pp_{seq_name}")
            shutil.copy2(
                process_dir / f"master_pp_flats_{filter_type}.fit",
                master_path,
            )
        self.history.mark_done(
            flats_dir, "create_master_flat", detail=filter_type
        )

    def calibrate_flats(self, seq_name: str, exposure: str) -> None:
        self.siril.log(f"Calibrating {seq_name}")
        # Declaring the output sequence keeps this record from going sticky:
        # create_master_flat rebuilds `process/flats_<f>/` whenever its master
        # is missing, and without this the rebuilt sequence would skip
        # calibration and then fail to stack on absent pp_ frames.
        if self.history.is_done(
            self.cwd(),
            "calibrate_flats",
            detail=seq_name,
            outputs=[self.cwd() / f"pp_{seq_name}_.seq"],
        ):
            self.siril.log("Step already done, skipping")
            return
        dark = get_dark(exposure)
        self.siril.cmd("calibrate", seq_name, f"-dark={dark}")
        self.history.mark_done(self.cwd(), "calibrate_flats", detail=seq_name)

    def stack_flats(self, seq_name: str) -> None:
        self.siril.log(f"Stacking {seq_name}")
        master_path = self.cwd() / f"master_{seq_name}.fit"
        if self.history.is_done(
            self.cwd(),
            "stack_flats",
            detail=seq_name,
            outputs=[master_path],
        ):
            self.siril.log("Step already done, skipping")
            return
        self.siril.cmd(
            "stack",
            seq_name,
            "rej sigma 2.0 3.0",
            "-nonorm",
            f"-out=master_{seq_name}",
        )
        self.open_image(master_path.name)
        self.history.mark_done(self.cwd(), "stack_flats", detail=seq_name)

    # --- lights --------------------------------------------------------

    def prepare_channels(
        self, filters: set[str], *, extract_background: bool = True
    ) -> list[str]:
        # No outer guard: create_master_channel tracks each filter's LIGHTS
        # sources as inputs, and extract_bg now tracks the master file's
        # mtime, so adding subs to an existing day invalidates the affected
        # filter chain. A wrapper-level "done" record would short-circuit
        # both per-filter checks.
        #
        # extract_background=False is the multi-night path: there, gradients
        # are removed once on the combined master (after every night's
        # calibrated subs are pooled and stacked in _combine_filter_across_days),
        # not per-night. The per-night masters built here are kept only as
        # diagnostics / for the stats panel.
        day_dir = self.cwd()
        self._step(f"Preparing channels: {day_dir.name}")
        processed: list[str] = []
        with cwd_at(self.siril, day_dir / "LIGHTS"):
            filter_files, filter_exposure = self.get_filter_files_exposure(
                RE_LIGHTS
            )
            lights_dir = self.cwd()
            for filter_type, files in filter_files.items():
                if filter_type not in filters:
                    continue
                self.create_master_channel(
                    filter_type, files, filter_exposure[filter_type]
                )
                if extract_background:
                    self.extract_bg(filter_type)
                # create_master_channel and extract_bg leave us in
                # day/process; restore for the next iteration's symlinking.
                self.cd(lights_dir)
                processed.append(filter_type)
        return processed

    def create_master_channel(
        self, filter_type: str, files: list[str], exposure: str
    ) -> None:
        self._step(f"Master channel: {filter_type}")
        lights_dir = self.cwd()  # day/LIGHTS
        process_dir = lights_dir.parent / "process"
        master_path = process_dir / f"master_{filter_type}.fit"
        master_flat_path = process_dir / f"master_flats_{filter_type}.fit"
        # Inputs include the master flat: a re-shot flat invalidates the
        # downstream channel stack even when the LIGHTS list is unchanged.
        source_paths = [lights_dir / f for f in files] + [master_flat_path]
        if self.history.is_done(
            lights_dir,
            "create_master_channel",
            detail=filter_type,
            outputs=[master_path],
            inputs=source_paths,
        ):
            self.siril.log("Step already done, skipping")
            # Match the fresh path's postcondition: leave the caller in
            # process_dir. A following extract_bg resolves its master path and
            # History key relative to cwd; without this a cached channel would
            # leave cwd at LIGHTS, so extract_bg would cache-miss and re-run
            # GraXpert with no image loaded (crash) — or, worse, silently
            # double-subtract the background on a resumed run.
            self.cd(process_dir)
            return

        seq_name = filter_type
        remaining = list(files)

        # A lone sub cannot go through convert/register/stack: Siril writes no
        # <filter>_.seq for a single converted frame, so `calibrate <seq>`
        # dies with "séquence d'entrée invalide" and takes the whole
        # (multi-night) build down with it — observed on NGC 7023 2026-07-13,
        # a cloud-wrecked night with one Blue/Green/Red sub each. Calibrate
        # the single frame directly with `calibrate_single` so its
        # pp_<filter>_00001.fit still flows into the cross-night pool; there is
        # nothing to align or reject with one frame, so register/stack are
        # skipped and the lone calibrated sub doubles as the diagnostic master.
        if len(remaining) < 2:
            self._build_single_frame_channel(
                process_dir, lights_dir, filter_type, seq_name,
                remaining, exposure,
            )
            self.history.mark_done(
                lights_dir, "create_master_channel", detail=filter_type
            )
            return

        # One retry: register_lights quarantines rogue frames and raises, and
        # the rebuilt sequence is then free of them. A second failure is a
        # different problem and must surface rather than loop.
        for attempt in range(2):
            self._build_light_sequence(
                process_dir, lights_dir, filter_type, seq_name, remaining
            )
            self.calibrate_lights(
                seq_name,
                filter_type,
                exposure,
                source_paths=[lights_dir / f for f in remaining],
            )
            self.subtract_sky_gradient(seq_name, len(remaining))
            try:
                self.register_lights(seq_name)
            except FramesQuarantined as exc:
                if attempt == 1:
                    raise
                gone = {p.name for p in exc.disposed}
                remaining = [f for f in remaining if f not in gone]
                self.siril.log(
                    f"Rebuilding {filter_type} without {len(gone)} "
                    f"quarantined frame(s): {len(remaining)} left"
                )
                if not remaining:
                    raise
                self._reset_filter_artifacts(
                    process_dir, filter_type, seq_name
                )
                self.cd(process_dir)
                continue
            break

        self.stack_lights(f"r_pp_{seq_name}", len(remaining))
        self.history.mark_done(
            lights_dir, "create_master_channel", detail=filter_type
        )

    def _build_single_frame_channel(
        self,
        process_dir: Path,
        lights_dir: Path,
        filter_type: str,
        seq_name: str,
        files: list[str],
        exposure: str,
    ) -> None:
        """Calibrate a lone sub the sequence pipeline cannot handle.

        `convert` writes no `<filter>_.seq` for a single frame, so
        `calibrate`, `register` and `stack` all fail on it. Rather than lose
        the sub — a full third of a thin night's colour data — calibrate it
        directly with `calibrate_single` (same dark / -cc=dark / flat as the
        sequence path), background-subtract it in place like any other sub,
        and copy the result to master_<filter>.fit. The calibrated
        pp_<filter>_00001.fit is exactly what _combine_filter_across_days
        pools, so the frame still reaches the final cross-night stack; it only
        skips the per-night register/stack that need >= 2 frames. Leaves the
        caller in process_dir, matching create_master_channel's other paths.
        """
        # convert still emits the frame link + conversion.txt (the pool's
        # source->light back-mapping reads the latter), just no .seq.
        self._build_light_sequence(
            process_dir, lights_dir, filter_type, seq_name, files
        )
        self.calibrate_single_light(
            seq_name,
            filter_type,
            exposure,
            source_paths=[lights_dir / f for f in files],
        )
        self.subtract_sky_gradient(seq_name, len(files))
        pp_sub = process_dir / f"pp_{seq_name}_00001.fit"
        master_path = process_dir / f"master_{filter_type}.fit"
        shutil.copy2(pp_sub, master_path)
        self.siril.log(
            f"Single-frame channel {filter_type}: calibrated one sub, "
            f"pooled as {pp_sub.name} (no per-night register/stack)"
        )
        self.cd(process_dir)

    def _build_light_sequence(
        self,
        process_dir: Path,
        lights_dir: Path,
        filter_type: str,
        seq_name: str,
        files: list[str],
    ) -> None:
        """Symlink `files` into process/<filter>/ and `convert` them."""
        seq_dir = process_dir / filter_type
        if seq_dir.exists():
            shutil.rmtree(seq_dir)
        seq_dir.mkdir(parents=True, exist_ok=True)
        for f in files:
            (seq_dir / f).symlink_to(lights_dir / f)

        self._clear_converted_sequence(process_dir, seq_name)
        with cwd_at(self.siril, seq_dir):
            self.siril.log("Converting files")
            self.siril.cmd("convert", seq_name, "-out=../")
        # Leave the caller in process_dir; calibrate/register/stack run there.
        self.cd(process_dir)

    @staticmethod
    def _clear_converted_sequence(process_dir: Path, seq_name: str) -> None:
        """Drop the frame links a previous `convert` left for `seq_name`.

        `convert -out=../` writes one symlink per input, numbered by position
        (`<seq>_00001.fit`). It overwrites the indices it needs and leaves any
        higher one untouched, so rebuilding a sequence with fewer frames — as
        the quarantine retry does — strands a link whose target has moved to
        DISPOSED/. Siril's directory rescan still counts that entry, builds an
        N+1-image sequence, and `calibrate` then dies on the frame it cannot
        open. Deleting the links first makes the sequence on disk mirror
        `files` exactly, on the first build as well as on a rebuild.
        """
        for path in process_dir.glob(f"{seq_name}_[0-9]*.fit"):
            path.unlink()
        for name in (f"{seq_name}_.seq", f"{seq_name}_conversion.txt"):
            (process_dir / name).unlink(missing_ok=True)

    def _reset_filter_artifacts(
        self, process_dir: Path, filter_type: str, seq_name: str
    ) -> None:
        """Drop every index-keyed artifact of a sequence about to be rebuilt.

        Siril caches star lists per sequence *index* (`cache/pp_<f>_00002.lst`),
        not per source frame. Remove a frame and the indices shift underneath
        the cache, so `findstar` silently reuses another image's stars. The
        converted frame links and the `.seq`/`pp_`/`r_pp_` files carry the same
        stale numbering.
        """
        self._clear_converted_sequence(process_dir, seq_name)
        for pattern in (
            f"pp_{seq_name}_*.fit",
            f"r_pp_{seq_name}_*.fit",
            f"pp_{seq_name}_*.seq",
            f"r_pp_{seq_name}_*.seq",
        ):
            for path in process_dir.glob(pattern):
                path.unlink()
        cache_dir = process_dir / "cache"
        if cache_dir.is_dir():
            for path in cache_dir.glob(f"*{seq_name}_*.lst"):
                path.unlink()
        self.history.invalidate(
            process_dir, "calibrate_lights", detail=filter_type
        )
        # Keyed on the pp_ subs as both inputs and outputs, so a fresh
        # calibrate's newer mtimes already invalidate it — but only by
        # accident of ordering. Say it outright.
        self.history.invalidate(
            process_dir, "subtract_sky_gradient", detail=seq_name
        )
        self.history.invalidate(
            process_dir, "register_lights", detail=seq_name
        )
        self.history.invalidate(
            process_dir, "stack_lights", detail=f"r_pp_{seq_name}"
        )

    def calibrate_lights(
        self,
        seq_name: str,
        filter_type: str,
        exposure: str,
        source_paths: Iterable[Path] = (),
    ) -> None:
        self.siril.log(
            f"Calibrating {seq_name} (filter={filter_type}, exposure={exposure})"
        )
        # Declare the sequence file as the output and the raw lights as inputs:
        # without them this record is sticky, so disposing of a frame would
        # leave the stale pp_ sequence (still carrying it) in place forever.
        if self.history.is_done(
            self.cwd(),
            "calibrate_lights",
            detail=filter_type,
            outputs=[self.cwd() / f"pp_{seq_name}_.seq"],
            inputs=source_paths,
        ):
            self.siril.log("Step already done, skipping")
            return
        dark = get_dark(exposure)
        flat_arg = f"-flat=master_flats_{filter_type}.fit"
        # `-cc=dark` flags the dark master's bad pixels and interpolates
        # them out. Cheap insurance for hot/cold pixels, especially if a
        # session lacked dithering.
        if dark:
            self.siril.cmd(
                "calibrate", seq_name, f"-dark={dark}", "-cc=dark", flat_arg
            )
        else:
            self.siril.cmd("calibrate", seq_name, flat_arg)
        self.history.mark_done(
            self.cwd(), "calibrate_lights", detail=filter_type
        )

    def calibrate_single_light(
        self,
        seq_name: str,
        filter_type: str,
        exposure: str,
        source_paths: Iterable[Path] = (),
    ) -> None:
        """calibrate_lights for a lone frame: `calibrate_single`, not
        `calibrate`.

        Siril has no `<seq>_.seq` to hand `calibrate` when a channel holds one
        sub, so the single-frame path calibrates the converted frame
        `<seq>_00001` directly. Same dark / -cc=dark / flat as the sequence
        path, producing pp_<seq>_00001.fit (the name the pool globs). Shares
        the "calibrate_lights" History step/detail with the sequence path so
        the record invalidates identically; the output it declares is the pp
        frame rather than a `.seq`.
        """
        self.siril.log(
            f"Calibrating {seq_name} (single frame, filter={filter_type}, "
            f"exposure={exposure})"
        )
        pp_path = self.cwd() / f"pp_{seq_name}_00001.fit"
        if self.history.is_done(
            self.cwd(),
            "calibrate_lights",
            detail=filter_type,
            outputs=[pp_path],
            inputs=source_paths,
        ):
            self.siril.log("Step already done, skipping")
            return
        dark = get_dark(exposure)
        flat_arg = f"-flat=master_flats_{filter_type}.fit"
        frame = f"{seq_name}_00001"
        if dark:
            self.siril.cmd(
                "calibrate_single", frame, f"-dark={dark}", "-cc=dark",
                flat_arg,
            )
        else:
            self.siril.cmd("calibrate_single", frame, flat_arg)
        self.history.mark_done(
            self.cwd(), "calibrate_lights", detail=filter_type
        )

    @staticmethod
    def _resolve_source_light(member: Path) -> Path | None:
        """Map a sequence member back to the raw light it was calibrated from.

        Handles both shapes the pipeline builds:

          - per-night: `<night>/process/pp_<f>_00003.fit` is a real file, and
            `<night>/process/<f>_conversion.txt` maps index 3 back to the
            symlink `<night>/process/<f>/<orig>.fits` -> `<night>/LIGHTS/…`.
          - pooled multi-night: `<root>/process/pp_<f>_00007.fit` is a symlink
            into `<root>/process/<f>/<night>_pp_<f>_00002.fit`, itself a
            symlink onto the night's calibrated sub — so recurse once resolved.

        Returns None when the trail cannot be followed; the caller then leaves
        the frame alone rather than moving a file it cannot identify.
        """
        real = Path(os.path.realpath(member))
        if real.parent.name == "LIGHTS":
            return real

        m = re.match(r"^pp_(.+)_(\d+)\.fit$", real.name)
        if not m:
            return None
        filter_name, index = m.group(1), int(m.group(2))

        conversion = real.parent / f"{filter_name}_conversion.txt"
        if not conversion.exists():
            return None
        for line in conversion.read_text().splitlines():
            if " -> " not in line:
                continue
            src, dest = line.rsplit(" -> ", 1)
            dest_m = re.search(r"_(\d+)\.fit'?$", dest.strip())
            if not dest_m or int(dest_m.group(1)) != index:
                continue
            src_path = Path(src.strip().strip("'"))
            resolved = Path(os.path.realpath(src_path))
            return resolved if resolved.exists() else None
        return None

    def _quarantine_misregistered(self, seq_name: str) -> None:
        """Move framing outliers out of LIGHTS/, or leave the sequence alone.

        Runs between `register -2pass` (which computes the transforms) and
        `seqapplyreg -framing=min` (which dies on them), so a rogue sub is
        caught before it can take the channel down.
        """
        process_dir = self.cwd()
        seq_path = process_dir / f"pp_{seq_name}_.seq"
        frames = read_seq_registration(seq_path)
        if not frames:
            return

        first = process_dir / f"pp_{seq_name}_{frames[0].index:05d}.fit"
        try:
            header = fits.getheader(os.path.realpath(first))
            width, height = int(header["NAXIS1"]), int(header["NAXIS2"])
        except (OSError, KeyError, ValueError):
            return

        outliers = find_framing_outliers(frames, width, height)
        if not outliers:
            return
        if len(outliers) > QUARANTINE_MAX_OUTLIER_FRAC * len(frames):
            # Not a clear minority, so there is no way to tell the good group
            # from the bad one — two nights at genuinely different rotator
            # angles look exactly like this. Say so loudly and let the human
            # decide; never silently discard half a target.
            self.siril.log(
                f"WARNING: {len(outliers)} of {len(frames)} frames in "
                f"{seq_name} disagree on framing — too many to call outliers. "
                f"Nothing disposed of. Registration will likely fail; inspect "
                f"the subs and move the bad ones to {DISPOSED_DIRNAME}/ by hand."
            )
            for index, reason in sorted(outliers.items()):
                self.siril.log(f"  frame {index}: {reason}")
            return

        disposed: list[Path] = []
        reasons: dict[Path, str] = {}
        for index, reason in sorted(outliers.items()):
            member = process_dir / f"pp_{seq_name}_{index:05d}.fit"
            source = self._resolve_source_light(member)
            if source is None:
                self.siril.log(
                    f"WARNING: frame {index} of {seq_name} is a framing "
                    f"outlier ({reason}) but its source light could not be "
                    f"resolved — leaving it in place."
                )
                continue
            disposed_dir = source.parent.parent / DISPOSED_DIRNAME
            disposed_dir.mkdir(parents=True, exist_ok=True)
            target = disposed_dir / source.name
            shutil.move(str(source), str(target))
            disposed.append(source)
            reasons[source] = reason
            self.siril.log(f"DISPOSED {source.name}: {reason}")

        if not disposed:
            return

        self._write_disposal_note(disposed, reasons, seq_name)
        raise FramesQuarantined(disposed, reasons)

    @staticmethod
    def _write_disposal_note(
        disposed: list[Path], reasons: dict[Path, str], seq_name: str
    ) -> None:
        """Append to DISPOSED/README.txt so the move is never a silent one."""
        stamp = time.strftime("%Y-%m-%d %H:%M:%S")
        by_dir: dict[Path, list[Path]] = {}
        for src in disposed:
            by_dir.setdefault(src.parent.parent / DISPOSED_DIRNAME, []).append(
                src
            )
        for disposed_dir, sources in by_dir.items():
            note = disposed_dir / "README.txt"
            with open(note, "a") as f:
                if note.stat().st_size == 0:
                    f.write(
                        "Frames moved here by astro_hibou because their "
                        "framing was grossly inconsistent with the rest of "
                        "their sequence, which makes Siril's "
                        "`seqapplyreg -framing=min` fail (empty intersection).\n"
                        "They are kept, never deleted. Move one back into "
                        "LIGHTS/ to reprocess it.\n"
                    )
                f.write(f"\n[{stamp}] sequence {seq_name}\n")
                for src in sources:
                    f.write(f"  {src.name}\n    reason: {reasons[src]}\n")

    def _run_graxpert_bge(self, what: str) -> None:
        """GraXpert AI background extraction on the loaded image, in place.

        Write-back verified like the SyQon tools: the pyscript can fail to push
        its result and exit 0, which would have us save the untouched frame and
        cache the step as done. See _run_syqon.
        """
        before = self._image_signature()
        self.siril.cmd(
            "pyscript",
            "GraXpert-AI.py",
            "-bge",
            "-correction subtraction",
            "-smoothing 0.5",
        )
        if self._image_signature() == before:
            raise RuntimeError(
                f"GraXpert background extraction left {what} unchanged — "
                f"check Siril's log. Refusing to cache it as done."
            )
        self.siril.undo_save_state("GraXpert Background Extraction")

    def subtract_sky_gradient(self, seq_name: str, num_files: int) -> None:
        """GraXpert AI background extraction on every calibrated sub, in place,
        before registration and stacking.

        Why per sub and not once on the combined master
        ----------------------------------------------
        Nights are not comparable images. Measured on M 101's luminance:

            night        sky level    per-sub sigma    gradient (p-p, absolute)
            2026-07-07   1.79e-02     1.26e-03         1.08e-03
            2026-07-08   4.75e-03     4.73e-04         5.64e-05

        A 3.8x sky pedestal, a 2.66x per-sub noise ratio, and a **19x** gradient.
        Pooling those subs and running a single background extraction on the
        combined master can only remove the *average* gradient — each night's
        deviation from it stays baked in, and no later step can separate them
        again. Subtracting per sub makes every frame share a flat, common
        background, so pixel rejection compares like with like and the stack's
        normalisation has a single scalar to find instead of a surface.

        Which model: `subsky -rbf`, not a polynomial and not GraXpert
        -------------------------------------------------------------
        Measured on three real subs per night, as the residual background
        structure (64-px block MAD) left after the fit, in units of that sub's
        own noise floor:

            model                       n07-07   n07-08   cross-night corr
            subsky 1                     5.53x    1.50x       +0.030
            subsky 2                     4.05x    1.44x       +0.072
            subsky 4                     1.98x    1.53x       +0.149
            subsky -rbf  (defaults)      1.87x    1.50x       +0.147
            subsky -rbf  samples=30 smooth=0.1
                                         1.77x    1.44x       +0.111
            GraXpert AI BGE, smoothing 0.5
                                         4.15x    1.58x       +0.113

        A plane leaves the bad night at 5.5x its noise floor, *and* what it
        leaves is uncorrelated between nights (+0.03) — so it is precisely the
        per-night component that the master-level BGE can never remove.
        GraXpert, despite being the right tool on a high-SNR master, only
        reaches 4.15x on a single sub: it is not built for this SNR.

        1.50x is the floor, not zero: it is what a *plane* leaves on the good
        night, and a plane cannot represent the real extended sky (IFN) by
        construction. `subsky -rbf` at defaults leaves the good night at exactly
        that same 1.50x, so it is removing the moon gradient and nothing else.
        Pushing further (samples=30, smooth=0.1) drops the good night to 1.44x —
        below the plane's floor — which is the signature of the model starting
        to eat real signal. Defaults it is.

        Corollary: the IFN worry is real but bounded, and the measurement above
        bounds it directly. (Arithmetically it was never large: the IFN is ~0.09 %
        of sky, ~4.2e-06 in one luminance sub, against a 64-px block noise floor
        of 9.2e-06 — SNR 0.45.)

        `subsky` preserves the pedestal (verified: median 1.654e-02 -> 1.631e-02
        on a real sub), so `-norm=add` downstream still has a level to work
        with. It also runs headless, so this step is verifiable without the GUI.
        GraXpert still runs once on the combined master, where the SNR earns it.
        """
        process_dir = self.cwd()
        subs = sorted(process_dir.glob(f"pp_{seq_name}_[0-9]*.fit"))
        if not subs:
            # Before is_done: an empty output set makes the History check
            # vacuously true, which would report "already done" for a
            # sequence whose calibrated subs are simply not there.
            self.siril.log(
                f"subtract_sky_gradient: no pp_{seq_name}_*.fit found; skipping"
            )
            return
        if self.history.is_done(
            process_dir,
            "subtract_sky_gradient",
            detail=seq_name,
            outputs=subs,
            inputs=subs,
        ):
            self.siril.log("Step already done, skipping")
            return
        self._step(f"Sky gradient per sub: {seq_name} ({len(subs)} subs)")
        for n, sub in enumerate(subs, 1):
            self.open_image(sub.stem)
            self.siril.cmd("subsky", "-rbf")
            self.siril.cmd("save", sub.stem)
            if n % 10 == 0 or n == len(subs):
                self._step(f"  {seq_name}: {n}/{len(subs)} subs")
        self.history.mark_done(
            process_dir, "subtract_sky_gradient", detail=seq_name
        )

    def register_lights(self, seq_name: str) -> None:
        process_dir = self.cwd()
        if self.history.is_done(
            process_dir,
            "register_lights",
            detail=seq_name,
            outputs=[process_dir / f"r_pp_{seq_name}_.seq"],
        ):
            self.siril.log("Step already done, skipping")
            return
        self.siril.cmd(
            "register",
            f"pp_{seq_name}",
            "-transf=homography",
            "-2pass",
            "-minpairs=10",
        )
        # Raises FramesQuarantined if it moved anything: the sequence on disk
        # no longer matches what `register` just measured, so the caller has to
        # rebuild it from the surviving lights rather than press on.
        self._quarantine_misregistered(seq_name)
        self.siril.cmd(
            "seqapplyreg",
            f"pp_{seq_name}",
            "-framing=min",
            "-interp=lanczos4",
        )
        self.history.mark_done(
            process_dir, "register_lights", detail=seq_name
        )

    def stack_lights(
        self,
        seq_name: str,
        num_files: int,
        *,
        apply_quality_filters: bool = True,
    ) -> None:
        master_name = f"master_{seq_name.replace('r_pp_', '')}"
        master_path = self.cwd() / f"{master_name}.fit"
        if self.history.is_done(
            self.cwd(),
            "stack_lights",
            detail=seq_name,
            outputs=[master_path],
        ):
            self.siril.log("Step already done, skipping")
            return
        self.siril.log(f"Stacking {seq_name}")
        # Stacking parameters follow the measured conclusions recorded in the
        # project notes (CLAUDE.md, "Pre-processing pipeline"), which supersede
        # Siril's generic guidance. Every value here was chosen against this
        # rig's own data, not from the manual:
        #
        #   - Rejection: `rej p 0.2 0.2` (percentile clipping) at EVERY stack
        #     size. On this data it removed ~16x more hot pixels than winsorized
        #     sigma AND gave the lowest background noise (sigma clipping barely
        #     rejects on the high side of a small stack; GESDT rejects hard but
        #     adds ~45% noise). It is also what stops single-frame satellite
        #     trails surviving into the thin 14-15 frame colour masters: with
        #     percentile + `add` at full frame count the trail drops to the
        #     noise floor (M 51, measured 2026-07-15). No frame-count branching
        #     — percentile wins at 8, 15 and 55 frames alike.
        #
        #   - Normalisation: `-norm=add`, never a scale term. Light pollution
        #     and moonlight are ADDITIVE; Siril estimates the scale factor from
        #     the frame MAD, which for a sky-limited sub tracks the Moon, so a
        #     scale term divides a moonlit frame's real signal along with its
        #     noise (measured: `addscale` made the moonlit night SNR worse).
        #
        #   - Weighting: `-weight=noise` (weights by 1/variance). Dropping it
        #     costs ~13% SNR; `wfwhm` weights on star sharpness and is blind to
        #     sky noise entirely.
        #
        #   - Frame selection: `-filter-round=3k` ONLY. The wfwhm/nbstars/round
        #     percentile cuts discarded good frames (43% of one L stack) and
        #     made the master ~46% noisier for nothing — `-weight=noise` already
        #     down-weights poor frames, so cutting them as well double-counts.
        #     `-filter-round=3k` is a cheap guard against a genuinely trailed
        #     frame and normally rejects nothing.
        #
        #   - Tiny sets (< QUALITY_FILTER_MIN_FRAMES) get NO whole-frame filter:
        #     any `-filter-*` cut on a 2-4 frame sequence can leave fewer than
        #     the 2-image stacking minimum ("the filtering options do not allow
        #     processing at least two images"). Per-pixel `rej` never removes
        #     whole frames, so it cannot trip that.
        #     `apply_quality_filters=False` forces the no-filter path outright
        #     (used where the inputs are already-cleaned masters).
        rej = "rej p 0.2 0.2"
        if not apply_quality_filters or num_files < QUALITY_FILTER_MIN_FRAMES:
            seq_filter = ""
        else:
            seq_filter = "-filter-round=3k"
        args = [
            "stack",
            seq_name,
            rej,
            "-norm=add",
            "-weight=noise",
        ]
        if seq_filter:
            args.append(seq_filter)
        args.append(f"-out={master_name}")
        self.siril.cmd(*args)
        self.open_image(master_path.name)
        self.siril.cmd("unclipstars")
        self.siril.cmd("platesolve")
        self.siril.cmd("save", master_name)
        self.history.mark_done(
            self.cwd(), "stack_lights", detail=seq_name
        )

    def extract_bg(self, filter_type: str) -> None:
        master_path = self.cwd() / f"master_{filter_type}.fit"
        # extract_bg rewrites master_<filter>.fit in place, so input and
        # output are the same file. After a successful run, the saved
        # mtime is slightly older than mark_done's recorded time, so
        # is_done passes on re-entry. When create_master_channel rewrites
        # the master with a fresh non-BGE stack, the bumped mtime exceeds
        # the previous completion and we re-run.
        if self.history.is_done(
            self.cwd(),
            "extract_bg",
            detail=filter_type,
            outputs=[master_path],
            inputs=[master_path],
        ):
            self.siril.log("Step already done, skipping")
            return
        self._step(f"Background extraction: {filter_type}")
        # Load the master explicitly rather than relying on a preceding
        # stack_lights having left it loaded: on a resumed run
        # create_master_channel is cached and loads nothing, so GraXpert
        # would otherwise fail with "No image or sequence loaded".
        if not master_path.exists():
            self.siril.log(
                f"extract_bg: {master_path.name} missing; skipping"
            )
            return
        self.open_image(master_path.name)
        self._run_graxpert_bge(f"master_{filter_type}")
        self.siril.cmd("save", f"master_{filter_type}")
        self.history.mark_done(
            self.cwd(), "extract_bg", detail=filter_type
        )

    # --- recombination -------------------------------------------------

    def compose(self, options: list[str]) -> None:
        # No outer guard: every inner step (prepare_compose_sequence,
        # compose_lrgb, compose_rgb, compose_halrgb_*, compose_sho) tracks
        # its own inputs/outputs and self-invalidates when the master
        # channels are refreshed. A wrapper-level "done" record would mask
        # those mtime checks and stop new-day data from reaching the recomb.
        self._step("Recombination")
        with cwd_at(self.siril, self.cwd() / "process"):
            self.prepare_compose_sequence(options)
            if "LRGB" in options:
                self.compose_lrgb()
            if "RGB" in options:
                self.compose_rgb()
            if "HaLRGB-R" in options:
                self.compose_halrgb_r()
            if "HaLRGB-L" in options:
                self.compose_halrgb_l()
            if any(o in SHO_PALETTE_OPTIONS for o in options):
                self.compose_sho(options)

    def prepare_compose_sequence(self, options: list[str]) -> None:
        process_dir = self.cwd()
        filter_codes: set[str] = set()
        for opt in options:
            for code in option_filter_codes(opt):
                filter_codes.add(code)
        filter_names_sorted = sorted(FILTER_NAMES[c] for c in filter_codes)

        master_paths = [
            process_dir / f"master_{n}.fit" for n in filter_names_sorted
        ]
        aligned_paths = [
            process_dir / f"aligned_{n}.fit" for n in filter_names_sorted
        ]
        if self.history.is_done(
            process_dir,
            "prepare_compose_sequence",
            outputs=aligned_paths,
            inputs=master_paths,
        ):
            self.siril.log("Step already done, skipping")
            return
        self._step("Aligning channel masters")

        compose_dir = process_dir / "compose"
        if compose_dir.exists():
            shutil.rmtree(compose_dir)
        compose_dir.mkdir(parents=True, exist_ok=True)
        # `convert` numbers frames alphabetically by file name; sorting the
        # symlinks here keeps the i+1 ordering of r_compose_seq_NNNNN.fit
        # in lockstep with filter_names_sorted.
        for filter_name in filter_names_sorted:
            (compose_dir / f"{filter_name}.fit").symlink_to(
                process_dir / f"master_{filter_name}.fit"
            )

        with cwd_at(self.siril, compose_dir):
            self.siril.cmd("convert", "compose_seq")
            # -2pass picks the reference by quality+framing and computes
            # transforms only; seqapplyreg then exports, with -framing=min
            # cropping to the area common to all frames.
            self.siril.cmd(
                "register",
                "compose_seq",
                "-transf=homography",
                "-2pass",
                "-minpairs=10",
            )
            self.siril.cmd(
                "seqapplyreg",
                "compose_seq",
                "-framing=min",
                "-interp=lanczos4",
            )
            for i, filter_name in enumerate(filter_names_sorted):
                shutil.copy2(
                    compose_dir / f"r_compose_seq_{i + 1:05d}.fit",
                    process_dir / f"aligned_{filter_name}.fit",
                )
        # Manual-crop runs skip the automatic coverage crop entirely: the
        # user crops the recombined master by hand (see do_process pause).
        if not self.manual_crop:
            self._coverage_crop_aligned(aligned_paths)
        self.history.mark_done(process_dir, "prepare_compose_sequence")

    def _coverage_crop_aligned(
        self,
        aligned_paths: list[Path],
        *,
        edge_threshold: float = COVERAGE_EDGE_THRESHOLD,
        margin: int = 8,
    ) -> None:
        """Trim the ragged, mostly-uncovered outer border off the aligned
        channels so the recombined image doesn't carry black edges (and the
        colored slivers Parallax rings on) into deconvolution.

        seqapplyreg -framing=min already aligns the channels, but a mosaic's
        outer edge is stepped and its corners (field rotation) are partially
        uncovered. We trim inward from each side only while that whole edge
        row/column is *mostly* uncovered (covered fraction < edge_threshold),
        then a few px more. Interior gaps — thin panel seams, a rotated
        corner that is still mostly covered — are deliberately tolerated:
        demanding a 100%-covered rectangle throws away huge good regions of a
        ~97%-covered mosaic (a single interior seam pixel is enough to
        collapse it). Any tiny residual black is cosmetic and cleaned up by
        hand.
        """
        datasets: list[np.ndarray] = []
        for p in aligned_paths:
            with fits.open(p) as h:
                arr = h[0].data
            if arr.ndim == 3:
                arr = arr[0]
            datasets.append(arr.astype(np.float32))

        H, W = datasets[0].shape
        # Coverage test: a pixel is covered when it is finite and above a
        # small floor. Uncovered areas are Siril's registration fill (exact 0,
        # or occasionally NaN / small negatives from lanczos overshoot); the
        # covered sky pedestal sits well above 1e-5, so this cleanly separates
        # the two regardless of fill representation.
        common = np.logical_and.reduce(
            [np.isfinite(d) & (d > 1e-5) for d in datasets]
        )
        if common.all():
            self.siril.log("Coverage already uniform; no crop needed")
            return

        # Per-edge coverage fraction. Peel inward from each side only while
        # the outermost row/column is mostly uncovered; stop at the first
        # edge that is >= edge_threshold covered (interior seams/corners are
        # left alone). A small fixed margin clears the coverage transition.
        col = common.mean(axis=0)
        row = common.mean(axis=1)
        x0 = 0
        while x0 < W and col[x0] < edge_threshold:
            x0 += 1
        x1 = W
        while x1 > x0 and col[x1 - 1] < edge_threshold:
            x1 -= 1
        y0 = 0
        while y0 < H and row[y0] < edge_threshold:
            y0 += 1
        y1 = H
        while y1 > y0 and row[y1 - 1] < edge_threshold:
            y1 -= 1
        x0 += margin
        y0 += margin
        x1 -= margin
        y1 -= margin

        w = x1 - x0
        h = y1 - y0
        if w < 100 or h < 100:
            self.siril.log(
                f"Coverage crop rectangle too small ({w}x{h}); "
                "leaving aligned channels untouched"
            )
            return
        if (x0, y0, x1, y1) == (0, 0, W, H):
            self.siril.log("Coverage already uniform; no crop needed")
            return
        self.siril.log(
            f"Coverage crop: ({x0},{y0}) {w}x{h} "
            f"(dropped L={x0} R={W - x1} T={y0} B={H - y1})"
        )
        for p in aligned_paths:
            self.siril.cmd("load", p.name)
            self.siril.cmd("crop", str(x0), str(y0), str(w), str(h))
            self.siril.cmd("save", p.stem)

    def compose_lrgb(self) -> None:
        """Compose the colour master (RGB + SPCC). **The L is deliberately NOT
        folded in here** — see below.

        Folding the luminance into the *linear* colour data (``rgbcomp -lum=``)
        desaturates the result to gray: the deep L pushes the nebula to the
        bright end, where a subsequent stretch compresses the channels together
        and the colour washes out. Confirmed by reproduction — `rgbcomp -lum`
        (and every equivalent, incl. an exact ``rgb·L/mean(rgb)`` transfer)
        comes out gray under stretch, while the same channels *without* L stay
        vividly pink. Siril's GUI "Composition TSL" avoids it, but there is no
        CLI/pyscript equivalent. The correct place for the L→RGB combination is
        **after stretching** (the classic LRGB workflow, and what you do by hand
        in the compositor). So this stage stops at a colour-calibrated RGB
        master; the luminance is available as ``aligned_luminance.fit`` /
        ``master_luminance.fit`` to combine post-stretch.
        """
        process_dir = self.cwd()
        out = process_dir / "lrgb.fit"
        inputs = [
            process_dir / f"aligned_{c}.fit" for c in ("red", "green", "blue")
        ]
        if self.history.is_done(
            process_dir, "compose_lrgb", outputs=[out], inputs=inputs
        ):
            self.siril.log("Step already done, skipping")
            return
        self._step("Composing RGB colour master (L combined post-stretch)")
        self.linear_match("aligned_red.fit", "aligned_green.fit")
        self.linear_match("aligned_blue.fit", "aligned_green.fit")
        # No -lum= : folding L into linear data greys the colour (see docstring).
        self.siril.cmd(
            "rgbcomp",
            "aligned_red.fit",
            "aligned_green.fit",
            "aligned_blue.fit",
            "-out=lrgb.fit",
        )
        self.siril.cmd("load", "lrgb.fit")
        self.color_calibrate()
        self.siril.cmd("save", "lrgb")
        self.history.mark_done(process_dir, "compose_lrgb")

    def compose_rgb(self) -> None:
        process_dir = self.cwd()
        out = process_dir / "rgb.fit"
        inputs = [
            process_dir / f"aligned_{c}.fit" for c in ("red", "green", "blue")
        ]
        if self.history.is_done(
            process_dir, "compose_rgb", outputs=[out], inputs=inputs
        ):
            self.siril.log("Step already done, skipping")
            return
        self._step("Composing RGB")
        self.linear_match("aligned_red.fit", "aligned_green.fit")
        self.linear_match("aligned_blue.fit", "aligned_green.fit")
        self.siril.cmd(
            "rgbcomp",
            "aligned_red.fit",
            "aligned_green.fit",
            "aligned_blue.fit",
            "-out=rgb.fit",
        )
        self.siril.cmd("load", "rgb.fit")
        self.color_calibrate()
        self.siril.cmd("save", "rgb")
        self.history.mark_done(process_dir, "compose_rgb")

    def compose_halrgb_r(self) -> None:
        """RGB colour master with Ha blended into the red channel.

        R' = R + w * mask * max(Ha - R, 0), where w = self.ha_weight and the
        mask gates the blend to pixels that actually emit Ha (see _blend_ha).
        Ha is
        linear-matched to R first so the blend stays photometric; the Ha lives
        in the red *colour* channel, so it survives fine. As with compose_lrgb,
        the L is NOT folded into the linear master (it would grey the colour) —
        the luminance is combined post-stretch.
        """
        process_dir = self.cwd()
        out = process_dir / "halrgb_r.fit"
        inputs = [
            process_dir / f"aligned_{c}.fit"
            for c in ("red", "green", "blue", "luminance", "ha")
        ]
        w = self.ha_weight
        detail = f"w={w:.2f} masked"
        if self.history.is_done(
            process_dir,
            "compose_halrgb_r",
            detail=detail,
            outputs=[out],
            inputs=inputs,
        ):
            self.siril.log("Step already done, skipping")
            return
        self._step(f"Composing HaLRGB-R (w={w:.2f})")
        self.linear_match("aligned_red.fit", "aligned_green.fit")
        self.linear_match("aligned_blue.fit", "aligned_green.fit")
        self.linear_match("aligned_ha.fit", "aligned_red.fit")
        self._blend_ha("aligned_red", "blended_red", w)
        # No -lum= : folding L into linear data greys the colour (see
        # compose_lrgb). Ha is in the red colour channel and survives.
        self.siril.cmd(
            "rgbcomp",
            "blended_red.fit",
            "aligned_green.fit",
            "aligned_blue.fit",
            "-out=halrgb_r.fit",
        )
        self.siril.cmd("load", "halrgb_r.fit")
        self.color_calibrate()
        self.siril.cmd("save", "halrgb_r")
        self.history.mark_done(process_dir, "compose_halrgb_r", detail=detail)

    def compose_halrgb_l(self) -> None:
        """RGB colour master + a Ha-enhanced luminance for post-stretch.

        The Ha-enhanced luminance L' = L + w * mask * max(Ha - L, 0) is
        computed and saved as ``blended_luminance.fit``. The mask gates the
        blend to the pixels that actually emit Ha (see _blend_ha), which
        matters more here than in the red channel: the old global blend made
        this 1.64x noisier than pure L, with 80.8 % of its variance coming
        from Ha — on the one channel that carries all the detail.

        L' is NOT folded into the linear colour master, because combining any
        luminance into linear colour data greys it (see compose_lrgb). So this
        mode outputs the colour-calibrated RGB master and leaves
        ``blended_luminance.fit`` on disk to combine after stretching, where
        the Ha contrast boost belongs.
        """
        process_dir = self.cwd()
        out = process_dir / "halrgb_l.fit"
        inputs = [
            process_dir / f"aligned_{c}.fit"
            for c in ("red", "green", "blue", "luminance", "ha")
        ]
        w = self.ha_weight
        detail = f"w={w:.2f} masked"
        if self.history.is_done(
            process_dir,
            "compose_halrgb_l",
            detail=detail,
            outputs=[out],
            inputs=inputs,
        ):
            self.siril.log("Step already done, skipping")
            return
        self._step(f"Composing HaLRGB-L (w={w:.2f})")
        self.linear_match("aligned_red.fit", "aligned_green.fit")
        self.linear_match("aligned_blue.fit", "aligned_green.fit")
        self.linear_match("aligned_ha.fit", "aligned_luminance.fit")
        # blended_luminance.fit is kept for the post-stretch L combination;
        # NOT folded in here (folding L into linear colour greys it — see
        # compose_lrgb). The linear master is RGB colour only.
        self._blend_ha("aligned_luminance", "blended_luminance", w)
        self.siril.cmd(
            "rgbcomp",
            "aligned_red.fit",
            "aligned_green.fit",
            "aligned_blue.fit",
            "-out=halrgb_l.fit",
        )
        self.siril.cmd("load", "halrgb_l.fit")
        self.color_calibrate()
        self.siril.cmd("save", "halrgb_l")
        self.history.mark_done(process_dir, "compose_halrgb_l", detail=detail)

    def compose_sho(self, options: list[str]) -> None:
        process_dir = self.cwd()
        if self.history.is_done(
            process_dir,
            "compose_sho",
            inputs=[
                process_dir / f"aligned_{c}.fit"
                for c in ("sii", "ha", "oiii")
            ],
        ):
            self.siril.log("Step already done, skipping")
            return
        self._step("Composing SHO palette")

        # No pre-scaling pass — linear_match already does a slope/intercept
        # regression per pair, so an independent median-ratio scale beforehand
        # just gets partially undone. Carry the aligned files through under
        # the "scaled_*" names the downstream pixel-math expressions expect.
        for code in ("sii", "ha", "oiii"):
            shutil.copy2(
                process_dir / f"aligned_{code}.fit",
                process_dir / f"scaled_{code}.fit",
            )
        self.linear_match("scaled_oiii.fit", "scaled_ha.fit")
        self.linear_match("scaled_sii.fit", "scaled_ha.fit")

        target_image: str | None = None
        if "SHO" in options:
            self.recomb_sho(["sii", "ha", "oiii"])
            target_image = "sho.fit"
        if "HOO" in options:
            self.recomb_sho(["ha", "oiii", "oiii"])
            target_image = target_image or "hoo.fit"
        if "OHS" in options:
            self.recomb_sho(["oiii", "ha", "sii"])
            target_image = target_image or "ohs.fit"
        if "HSO" in options:
            self.recomb_sho(["ha", "sii", "oiii"])
            target_image = target_image or "hso.fit"
        if "Forax" in options:
            self.recomb_forax()
            target_image = target_image or "forax.fit"

        if target_image is not None:
            self.open_image(target_image)
        self.history.mark_done(process_dir, "compose_sho")

    def color_calibrate(self) -> None:
        """SPCC if all four config strings are filled, otherwise PCC.

        Both commands need a WCS solution; rgbcomp doesn't necessarily
        propagate it from the channel masters, so platesolve first.
        Re-solving an already-solved frame is fast.
        """
        self.siril.cmd("platesolve")
        if SPCC_R_FILTER and SPCC_G_FILTER and SPCC_B_FILTER and SPCC_SENSOR:
            # Siril's spcc parser requires the *entire* -arg=value token to
            # be enclosed in quotes when the value contains spaces — quoting
            # only the value (-arg="value with spaces") is rejected.
            self.siril.cmd(
                "spcc",
                f'"-monosensor={SPCC_SENSOR}"',
                f'"-rfilter={SPCC_R_FILTER}"',
                f'"-gfilter={SPCC_G_FILTER}"',
                f'"-bfilter={SPCC_B_FILTER}"',
                f'"-whiteref={SPCC_WHITE_REF}"',
            )
        else:
            self.siril.log(
                "SPCC filters not configured; using PCC. Set SPCC_*_FILTER "
                "constants for spectral calibration."
            )
            self.siril.cmd("pcc")

    def linear_match(self, image: str, ref: str) -> None:
        self.siril.log(f"linear_match: image={image} ref={ref}")
        self.open_image(image)
        self.siril.cmd("linear_match", ref, "0 0.92")
        self.siril.cmd("save", Path(image).stem)

    def pixel_math(self, expression: str) -> None:
        """Evaluate a Siril PixelMath `expression`, leaving the result loaded.

        **The expression must reach Siril as a single quoted token.** Siril
        splits a command line on spaces, and `pm` then evaluates only the first
        token, silently ignoring the rest — no error, no warning. Every
        expression here has spaces around its `+`, so an unquoted
        `pm 0.5*$aligned_red$ + 0.5*$aligned_ha$` evaluated as
        `0.5*$aligned_red$` and threw the Ha term away. That is exactly what
        happened to HaLRGB-R and HaLRGB-L (blended_red came out bit-identical
        to `0.5 * aligned_red`) and to both Foraxx channels, from the first run
        until 2026-07-09. Quote it, and never build a `pm` call by hand.
        """
        self.siril.log(f"pm: {expression}")
        self.siril.cmd("pm", f'"{expression}"')

    def _blend_ha(self, base: str, out: str, w: float) -> None:
        """Blend `aligned_ha` into `base` only where Ha emits; save as `out`.

            out = base + w * mask * max(Ha - base, 0)

        `mask` is 1 inside an Ha-emitting region and 0 in the sky, so the sky
        keeps the base channel's own noise exactly. A *global* blend cannot do
        this: Ha is a 3 nm band, linear_match scales it ~4x to reach the base's
        level, and its noise comes with it. Real Ha covers under 1 % of the
        frame, so a constant weight buys signal almost nowhere and pays Ha's
        noise everywhere — which is what turned M 101's sky brown (see the
        ha_weight comment for the measured tables).

        The gate is the continuum-cancelled excess `Ha - base` (both already
        linear-matched, so a source with no line emission cancels). Smoothing
        it by HA_MASK_BLUR_PX cuts its noise ~4x without touching a knot, so
        the threshold sits far above the sky.

        The increment is rectified because line emission may only ever be
        *added* to the continuum, never subtracted from it. A star is bright in
        continuum and faint through a 3 nm band, so its excess is strongly
        negative; a star sitting inside an HII knot has the knot's mask over it
        (the mask is smoothed, the star is not) and a signed blend would gouge
        its core — measured at up to 3.4e-02 on M 101, over the 0.73 % of the
        frame where the mask is on but Ha < base. Rectifying costs nothing:
        99.8 % of the knot Ha survives and the frame noise is unchanged.

        Caller must have linear-matched aligned_ha to `base` first.
        """
        self.open_image(f"{base}.fit")
        base_data = self.siril.get_image_pixeldata()
        if base_data is None:
            raise RuntimeError(f"No image loaded — cannot blend Ha into {base}")
        base_data = base_data.astype(np.float32)
        ha = fits.getdata(self.cwd() / "aligned_ha.fit").astype(np.float32)
        if ha.shape != base_data.shape:
            raise RuntimeError(
                f"Ha blend shape mismatch: aligned_ha {ha.shape} vs "
                f"{base} {base_data.shape}"
            )

        excess = (ha - np.median(ha)) - (base_data - np.median(base_data))
        smoothed = gaussian_filter(excess, HA_MASK_BLUR_PX)
        sigma = 1.4826 * np.median(np.abs(smoothed - np.median(smoothed)))
        if sigma <= 0:
            raise RuntimeError(
                f"Ha excess over {base} has zero spread — refusing to blend"
            )
        lo = HA_MASK_THRESHOLD_SIGMA * sigma
        mask = np.clip((smoothed - lo) / (HA_MASK_RAMP_SIGMA * sigma), 0.0, 1.0)

        blended = base_data + w * mask * np.maximum(ha - base_data, 0.0)
        with self.siril.image_lock():
            self.siril.set_image_pixeldata(blended)
        self.siril.undo_save_state(f"Ha blend (masked, w={w:.2f})")
        self.siril.cmd("save", out)
        self.siril.log(
            f"Ha blend into {base}: w={w:.2f}, mask covers "
            f"{100 * float((mask > 0).mean()):.2f} % of the frame "
            f"({100 * float((mask >= 1.0).mean()):.3f} % at full weight)"
        )

    def recomb_sho(self, filters: list[str]) -> None:
        cwd = self.cwd()
        if self.history.is_done(
            cwd, "recompose_sho", detail="".join(filters)
        ):
            self.siril.log("Step already done, skipping")
            return
        red = f"scaled_{filters[0]}"
        green = f"scaled_{filters[1]}"
        blue = f"scaled_{filters[2]}"
        output = f"{filters[0][0]}{filters[1][0]}{filters[2][0]}"
        self.siril.cmd("rgbcomp", red, green, blue, f"-out={output}")
        self.history.mark_done(
            cwd, "recompose_sho", detail="".join(filters)
        )

    def recomb_forax(self) -> None:
        cwd = self.cwd()
        if self.history.is_done(cwd, "recompose_forax"):
            self.siril.log("Step already done, skipping")
            return
        self._step("Foraxx recombination")
        # Stretched templates that drive the blending masks. A single
        # autostretch is the classic Foraxx setup; tweak this if you want
        # a more contrasty (stronger) palette separation.
        self.open_image("scaled_ha.fit")
        self.siril.cmd("autostretch")
        self.siril.cmd("save", "TH")
        self.open_image("scaled_oiii.fit")
        self.siril.cmd("autostretch")
        self.siril.cmd("save", "TO")
        self.siril.cmd("close")

        self.pixel_math("($TO$^~$TO$)*$scaled_sii$ + ~($TO$^~$TO$)*$scaled_ha$")
        self.siril.cmd("save", "forax_red")
        self.siril.cmd("close")

        self.pixel_math(
            "(($TO$*$TH$)^~($TO$*$TH$))*$scaled_ha$ + "
            "~(($TO$*$TH$)^~($TO$*$TH$))*$scaled_oiii$"
        )
        self.siril.cmd("save", "forax_green")
        self.siril.cmd("close")

        self.linear_match("forax_red", "scaled_oiii")
        self.linear_match("forax_green", "scaled_oiii")
        self.siril.cmd(
            "rgbcomp", "forax_red", "forax_green", "scaled_oiii", "-out=forax"
        )
        self.history.mark_done(cwd, "recompose_forax")

    # --- post-processing ----------------------------------------------

    def process(self, recombinations: list[str]) -> None:
        """Pre-stretch processing of each recombined image.

        The pipeline stops after deconv -> denoise -> star removal on
        purpose: those are the last steps that benefit from linear data.
        Stretching, star recombination, and final cosmetic work happen by
        hand in Siril and GIMP afterwards. That's why we leave the
        `starless_*_denoised.fit` and `starmask_*_denoised.fit` files on
        disk and exit.
        """
        # Option labels don't all map to filenames by lowercasing
        # (HaLRGB-R -> halrgb_r), so go through an explicit table.
        with cwd_at(self.siril, self.cwd() / "process"):
            current_dir = self.cwd()
            done: list[str] = []
            for opt in recombinations:
                image = RECOMBINATION_FILES.get(opt, opt.lower())
                if (current_dir / f"{image}.fit").exists():
                    self._step(f"Processing {mode_label(image)}")
                    self.do_process(image)
                    done.append(image)
            for image in done:
                if self.cluster_mode:
                    self.siril.log(
                        f"{mode_label(image)} processed; final image is "
                        f"{image}_cluster.fit"
                    )
                else:
                    self.siril.log(
                        f"{mode_label(image)} processed; starless and starmask "
                        "are ready"
                    )

    def _manual_crop_pause(self, image: str) -> None:
        """Load the recombined master, and when manual_crop is on, block until
        the user has cropped it by hand in Siril and pressed Continue, then
        persist whatever image is loaded so the following deconvolve picks up
        the crop.

        **Always leaves ``<image>.fit`` loaded**, crop or no crop: this is the
        single load of ``do_process``'s SyQon chain, which then runs Parallax →
        Prism → Starless in place on it. With no crop this must still load, or
        the chain silently deconvolves whatever image Siril happened to hold —
        for the second and later recombinations of a run that is the *previous*
        image's starless output, so e.g. ``halrgb_r_deconvolved.fit`` came out
        as a re-deconvolved star-free LRGB.

        Cached as its own History step. Without this, a re-run whose
        ``do_process`` isn't marked done (e.g. it crashed further down at
        denoise) would pause and **re-save** ``<image>.fit`` again — bumping
        its mtime above the cached deconvolution's completion time and forcing
        a needless ~40-min re-deconvolve. Using ``<image>.fit`` as both input
        and output keeps the right dependency: the crop-save leaves the
        master's mtime just under this step's completion (valid → skip next
        run), but if recombination later rewrites the master its mtime exceeds
        completion and the crop correctly re-runs.
        """
        cwd = self.cwd()
        out = cwd / f"{image}.fit"
        if not self.manual_crop:
            self._load_master(image)
            return
        if self.history.is_done(
            cwd, "manual_crop", detail=image, outputs=[out], inputs=[out],
        ):
            self.siril.log("Step already done, skipping")
            self._load_master(image)
            return
        self._load_master(image)
        self._pause(
            f"Crop {image}.fit in Siril now (Recadrer), then press Continue. "
            "The pipeline will save your crop and carry on."
        )
        # Persist the user's crop (the interactive Recadrer modified Siril's
        # loaded image in place) so deconvolve() reloads the cropped master.
        self.siril.cmd("save", image)
        self.history.mark_done(cwd, "manual_crop", detail=image)

    def do_process(self, image: str) -> None:
        if self.cluster_mode:
            self.do_process_cluster(image)
            return
        cwd = self.cwd()
        final_out = cwd / f"starless_{image}_denoised.fit"
        starmask_out = cwd / f"starmask_{image}_denoised.fit"
        if self.history.is_done(
            cwd,
            "do_process",
            detail=image,
            outputs=[final_out, starmask_out],
            inputs=[cwd / f"{image}.fit"],
        ):
            self.siril.log("Step already done, skipping")
        else:
            # Siril's GUI SIGSEGVs when it frees/replaces a large master that
            # is already loaded — the crash is on the *second* huge load/close
            # (capture logs: the first load always succeeds, the next
            # load/close dies while purging the previous frame). The SyQon
            # tools all apply *in place*, so load the master exactly ONCE and
            # chain Parallax -> Prism -> Starless on the loaded image, saving a
            # checkpoint between each — never reload mid-chain. Per-step resume
            # is traded away for not crashing; deconvolution (the expensive
            # stage) keeps its own cache so a resume skips straight to denoise.
            inp = cwd / f"{image}.fit"
            deconv_out = cwd / f"{image}_deconvolved.fit"
            denoise_out = cwd / f"{image}_denoised.fit"
            deconv_done = self.history.is_done(
                cwd, "deconvolve", detail=image,
                outputs=[deconv_out], inputs=[inp],
            )
            # A cached denoise is only usable if the deconvolution it consumed
            # is itself still valid. History compares mtimes one link at a
            # time, so a rebuilt <image>.fit invalidates `deconvolve` while
            # leaving `denoise` looking done — its recorded input, the *stale*
            # <image>_deconvolved.fit, has not changed. Without this cascade a
            # new night of subs skips Parallax and Prism entirely and star
            # removal runs on the previous run's pixels. Observed on M 101
            # 2026-07-10: lrgb.fit rebuilt at 12:57, lrgb_denoised.fit left at
            # the previous day's 17:22, and do_process cached as complete.
            if deconv_done:
                denoise_done = self.history.is_done(
                    cwd, "denoise", detail=image,
                    outputs=[denoise_out], inputs=[deconv_out],
                )
            else:
                # Drop the record rather than merely ignoring it: a lingering
                # `denoise` entry would go stale-but-present in .history.
                self.history.invalidate(cwd, "denoise", detail=image)
                self.history.invalidate(
                    cwd, "remove_stars", detail=f"{image}_denoised"
                )
                denoise_done = False
            # Load the single huge master ONCE — the furthest-completed
            # checkpoint — then chain the remaining SyQon tools in place; never
            # reload (the GUI SIGSEGVs freeing/replacing a loaded master: the
            # first load succeeds, the next load/close dies).
            # Via _load_master, never a bare `load`: by the time a second
            # recombination resumes here, the previous mode's master is still
            # loaded, and replacing one huge image with another is the exact
            # transition that SIGSEGVs the GUI. _load_master closes first.
            if denoise_done:
                self.siril.log("Denoise cached; loading denoised master for star removal")
                self._load_master(denoise_out.stem)
            elif deconv_done:
                self.siril.log("Deconvolution cached; loading deconvolved master")
                self._load_master(deconv_out.stem)
                self._step(f"Denoising {image}")
                self._run_prism()
                self._neutralize_background()
                self.siril.cmd("save", denoise_out.stem)
                self.history.mark_done(cwd, "denoise", detail=image)
            else:
                # The one load of the chain: always leaves <image>.fit loaded,
                # cropped by hand first when manual_crop is on.
                self._manual_crop_pause(image)
                self._step(f"Deconvolving {image}")
                self._run_parallax()
                self.siril.cmd("save", deconv_out.stem)
                self.history.mark_done(cwd, "deconvolve", detail=image)
                self._step(f"Denoising {image}")
                self._run_prism()
                self._neutralize_background()
                self.siril.cmd("save", denoise_out.stem)
                self.history.mark_done(cwd, "denoise", detail=image)
            # Star removal, in place on the loaded denoised master. Starless
            # writes starless_/starmask_ from the loaded filename ({image}
            # _denoised). It hard-fails (producing nothing) if it cannot obtain
            # its models — _run_starless proves it wrote, so a failed run is
            # not falsely cached as done.
            self._step(f"Removing stars: {image}_denoised")
            self._run_starless(final_out, starmask_out)
            self.history.mark_done(cwd, "remove_stars", detail=f"{image}_denoised")
            self.history.mark_done(cwd, "do_process", detail=image)
        write_metadata_sidecar(
            final_out,
            mode=mode_label(image),
            common_name_fr=self.common_name_fr,
            common_name_en=self.common_name_en,
        )
        if self.write_stretch_me:
            self._write_stretch_me(image)

    def do_process_cluster(self, image: str) -> None:
        """Cluster path: no star removal. Deconvolve then denoise on linear
        data, save a linear pre-stretch checkpoint, autostretch, recover
        clipped star cores. Designed for fields where there is no faint
        extended structure to preserve, just point sources over background.

        Two linear checkpoints are kept: `<image>_cluster_deconvolved.fit`
        (deconv only, before Prism denoise) is the branch point for the
        VeraLux/Silentium continuation so pixels aren't denoised twice, and
        `<image>_cluster_prestretch.fit` (deconv + denoise) is the
        redo-the-stretch-by-hand checkpoint. The final save targets yet
        another file, so neither checkpoint is overwritten.
        """
        cwd = self.cwd()
        final_out = cwd / f"{image}_cluster.fit"
        deconv_out = cwd / f"{image}_cluster_deconvolved.fit"
        prestretch_out = cwd / f"{image}_cluster_prestretch.fit"
        detail = f"{image}_cluster"
        if self.history.is_done(
            cwd,
            "do_process",
            detail=detail,
            outputs=[final_out],
            inputs=[cwd / f"{image}.fit"],
        ):
            self.siril.log("Step already done, skipping")
            self._load_master(final_out.stem)
        else:
            # Leaves <image>.fit loaded (cropped, when manual_crop is on) —
            # the single load; the SyQon tools then apply in place.
            self._manual_crop_pause(image)
            self._step(f"Cluster: deconvolve {image}")
            self._run_parallax()
            # Deconv-only linear checkpoint (pre-denoise) for the Silentium
            # branch; the loaded image is unchanged by the save.
            self.siril.cmd("save", deconv_out.stem)
            # Capture the stretch parameters HERE, while the frame still has its
            # noise. Siril's `autostretch` on the denoised frame would derive a
            # 16x harsher midtone and amplify Prism's residual bias into
            # coloured continents. See _autostretch_params.
            stretch_params = self._autostretch_params(
                self.siril.get_image_pixeldata()
            )
            self._step(f"Cluster: denoise {image}")
            self._run_prism()
            self._neutralize_background()
            self._step(f"Cluster: save pre-stretch checkpoint {image}")
            self.siril.cmd("save", prestretch_out.stem)
            self._step(f"Cluster: stretch {image} (pre-denoise parameters)")
            self._apply_stretch(stretch_params)
            self._step(f"Cluster: recover star cores {image}")
            self.siril.cmd("unclipstars")
            self.siril.cmd("save", final_out.stem)
            self._load_master(final_out.stem)
            self.history.mark_done(cwd, "do_process", detail=detail)
        write_metadata_sidecar(
            final_out,
            mode=mode_label(image),
            common_name_fr=self.common_name_fr,
            common_name_en=self.common_name_en,
        )

    # --- SyQon engine wrappers -----------------------------------------
    # Deconv, denoise, and star removal are the SyQon suite, run via pyscript
    # (same mechanism as GraXpert background extraction). Each tool applies to
    # the loaded image and pins its model edition through its own config JSON
    # (Parallax=pro, Prism=deep, Starless=Axiom V3). They only run under the
    # interactive GUI — Siril initialises its Python there; every non-GUI mode
    # (siril-cli, siril -s, siril -p) reports "python not ready" and cannot run
    # a pyscript. The recombined-master loads around these steps go through
    # _load_master (close-before-load) to dodge a GUI segfault on large images.

    def _image_signature(self) -> str:
        """Hash of Siril's currently loaded pixel data.

        Used to prove a SyQon tool actually pushed its result back before the
        pipeline saves the buffer and caches the step as done. sirilpy moves
        the pixels over shared memory, so this costs a fraction of a second
        next to a multi-minute inference run.
        """
        data = self.siril.get_image_pixeldata()
        if data is None:
            raise RuntimeError("No image loaded — cannot sign pixel data")
        return hashlib.blake2b(
            np.ascontiguousarray(data).tobytes(), digest_size=16
        ).hexdigest()

    def _run_syqon(
        self, tool: str, *args: str, expect_change: bool = False,
        label: str | None = None,
    ) -> None:
        """Run a SyQon tool through the syqon_logged.py wrapper so its output
        streams into Siril's **log console** (with timestamp + extrapolated
        ETA), for all three tools.

        Write-back verification (``expect_change``)
        -------------------------------------------
        The SyQon tools push their result with ``set_image_pixeldata`` inside a
        ``try/except Exception`` that merely *prints* on failure and exits 0.
        A tool can therefore burn its full inference time, fail to update
        Siril's image, and leave the caller saving the untouched input buffer
        under the output name — the step then caches as done and every later
        stage silently consumes unprocessed data. Observed on M 101:
        ``halrgb_r_denoised.fit`` came out bit-identical to
        ``halrgb_r_deconvolved.fit`` after an 8-minute Prism run.

        So hash the loaded pixels before and after: if the tool claims success
        without touching the image, fail loudly instead of caching a lie.
        ``label`` (the undo/HISTORY annotation) is only stamped once the change
        is proven, so a FITS ``HISTORY`` card never attests to work that did
        not happen.

        The wrapper runs the real tool in-process (`runpy`) on a single sirilpy
        connection the tool reuses (its `SirilInterface()` is monkeypatched),
        redirects the tool's fds 1/2 onto a private pipe it drains, and forwards
        each line to `SirilInterface.log`. That also removes the 64 KiB-pipe
        deadlock (the pipe is drained continuously). The earlier "wrapper
        failure" was actually the GUI load segfault killing Siril before the
        pyscript ran — fixed by the single-load `do_process` chain.
        """
        before = self._image_signature() if expect_change else None
        self.siril.cmd("pyscript", "syqon_logged.py", tool, *args)
        if expect_change and self._image_signature() == before:
            raise RuntimeError(
                f"SyQon {tool} exited without modifying Siril's loaded image "
                f"(pixel data unchanged). The tool swallows write-back errors "
                f"— check Siril's log for '[{tool}]' lines such as 'Could not "
                f"update Siril image'. Refusing to save an unprocessed buffer."
            )
        if label is not None:
            self.siril.undo_save_state(label)

    def _pin_syqon_config(self, tool: str, values: dict) -> None:
        """Pin a SyQon tool's JSON config before invoking it.

        The tools read `<siril configdir>/syqon_<tool>_config.json`, merged over
        their own defaults, and their GUIs rewrite it on every interactive
        session. Knobs that have no CLI flag — Parallax's `mode` (i.e. *which
        model runs*), Starless's `stretch_method` / `ihs_target` — are therefore
        whatever the last GUI session happened to leave behind, which makes a
        pipeline run irreproducible. Write them explicitly instead.

        Only the listed keys are touched; anything else in the file is left
        alone, so a knob the pipeline has no opinion about still follows the
        tool's default. A config that is missing or corrupt is simply rewritten
        — the tools fall back to their defaults for absent keys anyway.
        """
        path = Path(self.siril.get_siril_configdir()) / f"syqon_{tool}_config.json"
        try:
            cfg = json.loads(path.read_text())
            if not isinstance(cfg, dict):
                cfg = {}
        except (OSError, ValueError):
            cfg = {}
        cfg.update(values)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(cfg, indent=2))

    def _run_starless(self, *outputs: Path) -> None:
        """Run SyQon Starless and prove it actually wrote its outputs.

        Starless is the one SyQon tool that writes files itself rather than
        pushing pixels back into Siril, so `_run_syqon(expect_change=True)`
        cannot check it. It hard-fails, producing nothing, when it cannot
        obtain its model — and `pyscript` does not surface that as an
        exception. Asserting only that the outputs *exist* therefore passes on
        a previous run's leftovers, and the step caches as done over stale
        pixels. Observed on M 101 2026-07-10: `remove_stars:lrgb_denoised` was
        recorded 14 s after the master was rebuilt, while both
        `starless_lrgb_denoised.fit` and `starmask_lrgb_denoised.fit` still
        carried the previous day's mtime.

        So compare mtimes across the call: an output that is absent, or whose
        mtime did not move, means the tool wrote nothing.
        """
        before = {
            p: (p.stat().st_mtime if p.exists() else None) for p in outputs
        }
        self._pin_syqon_config("starless", STARLESS_CONFIG)
        self._run_syqon("Starless.py", "--axiom3")
        stale = [
            p.name
            for p in outputs
            if not p.exists() or p.stat().st_mtime == before[p]
        ]
        if stale:
            raise RuntimeError(
                f"SyQon Starless produced no fresh output "
                f"({', '.join(stale)}) — the tool failed (e.g. it could not "
                f"obtain its model) and left any existing file untouched. "
                f"Check Siril's log for '[Starless.py]' lines. Not marking done."
            )

    @staticmethod
    def _mtf(x: np.ndarray, midtone: float) -> np.ndarray:
        """Siril's midtone transfer function, on data already black-clipped.

        The final clip is not cosmetic: `num / den` is evaluated in float32 and
        rounds to `1.0000001` for x just under 1, so without it `_apply_stretch`
        emits out-of-range pixels — which read as clipped star cores in the
        cluster path's saved output.
        """
        x = np.clip(x, 0.0, 1.0)
        num = (midtone - 1.0) * x
        den = (2.0 * midtone - 1.0) * x - midtone
        y = np.where(x <= 0.0, 0.0, np.where(x >= 1.0, 1.0, num / den))
        return np.clip(y, 0.0, 1.0)

    @staticmethod
    def _autostretch_params(
        data: np.ndarray, shadows_clip: float = -2.8, target_bg: float = 0.25
    ) -> list[tuple[float, float]]:
        """Per-channel (black_point, midtone) for Siril's unlinked autostretch.

        **Compute these from the PRE-denoise frame, always.** Autostretch places
        its black point at `median + shadows_clip * sigma` and solves a midtone
        that maps the background to `target_bg`. Both depend on sigma, and a
        denoised frame has almost none left: on M 101 Prism took the background
        MAD from 5.9e-05 to 3.7e-06, and autostretch answered by pulling the
        midtone from 0.00049 to 0.00003 — 16x harsher — which blew the galaxy
        core to white, lifted the sky out of black, and dragged Prism's own
        low-frequency residual (3.7 % of the original noise, but 59 % of what
        survives) into view as green and magenta continents. Stretching the very
        same denoised pixels with the deconvolved frame's parameters gives a
        clean image. The denoise was never the problem; deriving the stretch
        from it was.
        """
        params: list[tuple[float, float]] = []
        for i in range(data.shape[0]):
            ch = data[i]
            med = float(np.median(ch))
            sigma = 1.4826 * float(np.median(np.abs(ch - med)))
            lo = max(0.0, med + shadows_clip * sigma)
            norm = (med - lo) / (1.0 - lo)
            midtone = ((target_bg - 1.0) * norm) / (
                (2.0 * target_bg - 1.0) * norm - target_bg
            )
            params.append((lo, midtone))
        return params

    def _apply_stretch(self, params: list[tuple[float, float]]) -> None:
        """Apply per-channel (black_point, midtone) to the loaded image.

        Done in numpy and pushed back rather than via Siril's `autostretch`,
        which would recompute the parameters from the image in front of it —
        the exact thing we must not do.
        """
        data = self.siril.get_image_pixeldata()
        if data is None:
            raise RuntimeError("No image loaded — cannot stretch")
        out = np.empty_like(data, dtype=np.float32)
        for i, (lo, midtone) in enumerate(params):
            out[i] = self._mtf((data[i] - lo) / (1.0 - lo), midtone)
        with self.siril.image_lock():
            self.siril.set_image_pixeldata(out)
        self.siril.undo_save_state("Autostretch (pre-denoise parameters)")

    def _neutralize_background(self) -> None:
        """Force the three channels' sky medians to agree, in place.

        Parallax and Prism both normalise each channel independently before
        inference, and each hands back a small per-channel DC offset. Measured
        on M 101, the spread between the R/G/B sky medians (as a fraction of the
        sky above HyperMetric's anchor) grows 0.12 % -> 0.58 % -> 0.80 % across
        lrgb -> deconvolved -> denoised, with green always highest. A stretch
        anchors just under the sky and then divides by what is left, so a 0.8 %
        offset becomes a flat olive cast over the whole frame.

        Subtracting a constant per channel is the honest correction: the sky is
        neutral, and a DC offset carries no signal. It leaves object colour
        untouched. Verified to take the spread to exactly 0.000 %.
        """
        data = self.siril.get_image_pixeldata()
        if data is None or data.ndim != 3 or data.shape[0] != 3:
            return  # mono: nothing to neutralize
        medians = [float(np.median(data[i])) for i in range(3)]
        target = float(np.mean(medians))
        offsets = [target - m for m in medians]
        if max(abs(o) for o in offsets) < 1e-9:
            return
        out = np.empty_like(data, dtype=np.float32)
        for i, off in enumerate(offsets):
            out[i] = data[i] + off
        with self.siril.image_lock():
            self.siril.set_image_pixeldata(out)
        self.siril.undo_save_state("Background neutralisation")
        self.siril.log(
            "Background neutralised: offsets R/G/B = "
            + " ".join(f"{o:+.3e}" for o in offsets)
        )

    def _run_parallax(self) -> None:
        """Deconvolve/sharpen the loaded image in place (SyQon Parallax).

        Aberration correction stays on (its config default); star reduction
        is forced off (`--star-level 0`) so only the deblur runs. Applies in
        place — the caller is responsible for saving.

        `--sharpen` is Parallax's `sharpen_alpha`, a **blend fraction**, not a
        strength: `out = in + alpha * (sharpened - in)`. At 0.5 half the
        sharpening is discarded. Upstream default is 1.0; so is
        deconv_strength.

        At 1.0 Parallax pushes star cores past full scale — measured on M 101's
        LRGB master, `lrgb_deconvolved.fit` holds 1220 / 1339 / 1249 pixels at
        >= 0.999 in R / G / B, against 0 in the master it was given. Clipped
        cores are not merely blown: the channels clip by different amounts, so
        the star reads as a colour.

        **Do NOT "fix" that with `unclipstars` here.** _Tried 2026-07-10,
        reverted the same hour._ `unclipstars` reconstructs a clipped star's true
        peak from its wings and then rescales the WHOLE image so that peak lands
        at 1.0. It is a pure global multiply — verified headlessly on synthetic
        frames: exact no-op when nothing is clipped, and `after = 0.47649 *
        before` (no offset, max residual 5e-09) for a star clipped at 2x its true
        peak. On this master, where Parallax clips 1220 pixels over broad cores,
        the profile fit extrapolated a peak of ~4385x and divided everything by
        it: the sky went 1.257e-03 -> 2.866e-07 and the frame's minimum to 0.0.
        The command is safe after *stacking* (a handful of clipped pixels, scale
        ~1) and unsafe after a full-strength deconvolution. If the clipped cores
        matter, lower `deconv_strength` instead.
        """
        self._pin_syqon_config(
            "parallax",
            {**PARALLAX_CONFIG, "sharpen_alpha": self.deconv_strength,
             "star_level": 0.0},
        )
        self._run_syqon(
            "Parallax.py",
            "--edition pro",
            "--star-level 0",
            f"--sharpen {self.deconv_strength:.2f}",
            expect_change=True,
            label="SyQon Parallax deconvolve",
        )

    def _run_prism(self) -> None:
        """Denoise the loaded image in place (SyQon Prism, deep model).

        `--modulation` is a **blend fraction**, not a strength dial:
        `out = modulation * denoised + (1 - modulation) * original`. At 0.5
        exactly half the untouched, noisy input is mixed back in — the master
        comes out with half its noise intact. Full strength (1.0) is right.

        What full strength does NOT do is ruin the image. Prism leaves a
        low-frequency residual bias of ~3.7 % of the noise it was shown — an
        ordinary, unremarkable figure for a neural denoiser. But it also drops
        the background MAD from 5.9e-05 to 3.7e-06, so that same bias becomes
        **59 %** of the noise that survives. Anything downstream that derives a
        black point from the image's own sigma (Siril's `autostretch`) then
        amplifies the bias into visible coloured continents. The denoise is
        fine; the stretch must not be computed from it. See
        _autostretch_params. Applies in place — the caller saves.

        **`--stretch-target` is 0.10.** _It was moved to 0.25 on 2026-07-12 to
        match a hand-driven run, and moved straight back the same evening once
        the cost showed up on screen as a magenta galaxy nucleus. Do not raise
        it again without measuring the nucleus._

        Prism v2.2.0 stretches the frame to a target median before inference
        and inverts afterwards. At 0.25 the stretch is steep enough that
        M 101's nucleus (linear 0.0208) lands at 0.966 in the network's input,
        inside the top 3 % of its range; the model overshoots, `pred.clamp(0,
        1)` bites, and the inverse maps it back to 1.0 linear. Measured on
        M 101's own pixels, same crop, same weights, only the target changing:

            target 0.10 -> nucleus 0.0229,   4 newly saturated px
            target 0.25 -> nucleus 1.0000,  26 newly saturated px
            target 0.40 -> nucleus 1.0000,  57 newly saturated px
            ihs    0.40 -> nucleus 0.0145 (-30 %), 0 px

        **The magenta galaxy nucleus is NOT caused by this flag, and does not
        reach the final image.** It looked damning: at 0.25, M 101's nucleus
        goes 0.0071 -> 0.2753 (39x) against 0.0055 -> 0.0652 (12x) at 0.10, and
        the starless core comes out R/G 2.19 instead of 1.38. Two checks kill
        that story:

        - The operator set the median to 0.1 in **both** Parallax and Prism and
          saw no change. The two archived runs differed by **Parallax** (old
          model vs the v1.2 rewrite, 83f9ea5), not by this target.
        - Starless moves **99.2 %** of the nucleus into the **star mask**
          (0.2731 of 0.2753). The 0.8 % left in the starless is the difference
          of two nearly-equal large numbers, so its colour is numerical noise —
          `use_amp: true` makes it non-deterministic (identical settings gave
          R/G 1.17 one run, 2.19 the next). Screen the mask back, which is the
          real workflow, and the core returns at R/G 1.238. The pink dot exists
          only in an intermediate.

        **Still unexplained:** the ~39x nucleus inflation is real and does reach
        the image through the star mask. No knob has been shown to control it.
        Measure before blaming a setting — that mistake was made twice in one
        evening.

        Star cores clip too, and recomposition here is a GIMP **screen /
        lighten** layer of the star mask over the hand-stretched starless.
        Screen can only brighten, so a flat-topped core comes back as a white
        disc with colour only in its wings. (The mask's own pedestal is
        ~1.7e-07, so screening it does not lift the sky — measured.) If bright
        stars go white, `deconv_strength` — Parallax's sharpen alpha, which
        pushes the cores past full scale — is the lever, not `unclipstars`,
        which rescales the whole frame; see _run_parallax.

        Pass the method explicitly, and pin it: these values live in
        `<configdir>/syqon_prism_config.json`, which the GUI rewrites, so an
        unspecified flag is whatever the last interactive run left behind.
        """
        self._pin_syqon_config(
            "prism",
            {**PRISM_CONFIG,
             "modulation": int(round(self.denoise_strength * 100))},
        )
        self._run_syqon(
            "Prism.py",
            "--model deep",
            f"--modulation {self.denoise_strength:.2f}",
            "--stretch-method statistical",
            f"--stretch-target {PRISM_STRETCH_TARGET:.2f}",
            expect_change=True,
            label="SyQon Prism denoise",
        )

    def deconvolve(self, image: str) -> None:
        """Deconvolve/sharpen the recombined master on linear data with
        stars present (SyQon Parallax). SyQon handles stars in place, so
        there is a single deconv path — no separate starless-only mode.
        """
        cwd = self.cwd()
        inp = cwd / f"{image}.fit"
        out = cwd / f"{image}_deconvolved.fit"
        if self.history.is_done(
            cwd, "deconvolve", detail=image, outputs=[out], inputs=[inp],
        ):
            self.siril.log("Step already done, skipping")
            self._load_master(out.stem)
            return
        self._step(f"Deconvolving {image}")
        self._load_master(f"{image}.fit")
        self._run_parallax()
        self.siril.cmd("save", out.stem)
        self._load_master(out.stem)
        self.history.mark_done(cwd, "deconvolve", detail=image)

    def denoise(self, image: str) -> None:
        """Denoise the deconvolved full-frame master on linear data, before
        star removal (SyQon Prism). Input is deconvolve()'s output.
        """
        cwd = self.cwd()
        inp = cwd / f"{image}_deconvolved.fit"
        out = cwd / f"{image}_denoised.fit"
        if self.history.is_done(
            cwd, "denoise", detail=image, outputs=[out], inputs=[inp],
        ):
            self.siril.log("Step already done, skipping")
            self._load_master(out.stem)
            return
        self._step(f"Denoising {image}")
        self._load_master(f"{image}_deconvolved.fit")
        self._run_prism()
        self._neutralize_background()
        self.siril.cmd("save", out.stem)
        self._load_master(out.stem)
        self.history.mark_done(cwd, "denoise", detail=image)

    def remove_stars(self, image: str, src_stem: str) -> tuple[Path, Path]:
        """Remove stars from `<src_stem>.fit` with SyQon Starless (Axiom
        V3), the StarNet++ replacement. Starless names its outputs from the
        loaded image's filename, so this writes `starless_<src_stem>.fit`
        and `starmask_<src_stem>.fit` into the working dir and leaves the
        starless loaded. Returns (starless_path, starmask_path).
        """
        cwd = self.cwd()
        src = cwd / f"{src_stem}.fit"
        starless = cwd / f"starless_{src_stem}.fit"
        starmask = cwd / f"starmask_{src_stem}.fit"
        if self.history.is_done(
            cwd, "remove_stars", detail=src_stem,
            outputs=[starless, starmask], inputs=[src],
        ):
            self.siril.log("Step already done, skipping")
            self._load_master(starless.stem)
            return starless, starmask
        self._step(f"Removing stars: {src_stem}")
        # Load so Starless derives its output basename from this file.
        self._load_master(src_stem)
        # Axiom V3 pinned; the user runs Starless offline with no Zenith
        # fallback model available. Starless writes both FITS files itself,
        # so _run_starless verifies the write rather than trusting exit 0.
        self._run_starless(starless, starmask)
        self._load_master(starless.stem)
        self.history.mark_done(cwd, "remove_stars", detail=src_stem)
        return starless, starmask

    # --- VeraLux: checkpoint + interactive continuation ---------------

    def _stretch_me_dir(self) -> Path:
        return self.cwd() / "_STRETCH_ME"

    def _target_tag(self) -> str:
        """Target id used in checkpoint/reference names: ``M 101`` -> ``M101``.

        Every non-alphanumeric character goes, not just whitespace. The naming
        convention is ``<date>_<target>-<MODE>``, so a hyphen in the target
        would collide with the separator — which is exactly why the exports
        have always called ``M8 - M20`` ``M8M20``.
        """
        return re.sub(r"[^0-9A-Za-z]", "", self.root_dir.name) or "target"

    def _stretch_me_base(self, image: str) -> str:
        """``2026-07-10_M101-LRGB`` — the stem the checkpoint files share.

        The date is the run date, not the last night that contributed data.
        Deriving the latter per mode is doable (each mode uses a known set of
        filters, and the night folders are named for the night) but the run
        date is close enough in practice: the pipeline is run the day after
        the last session, or the same day.
        """
        return f"{date.today():%Y-%m-%d}_{self._target_tag()}-{mode_label(image)}"

    def find_stretch_me(self, image: str, kind: str) -> Path | None:
        """Locate a checkpoint file without knowing the date it was stamped.

        Consumers downstream of the pipeline (the VeraLux launcher) run later
        — possibly on another day — so they cannot rebuild the basename. Glob
        on the date-independent part instead, newest first; ISO dates sort
        lexicographically, so plain string order is chronological order.
        """
        pattern = f"*_{self._target_tag()}-{mode_label(image)}_{kind}"
        matches = sorted(self._stretch_me_dir().glob(pattern), reverse=True)
        return matches[0] if matches else None

    def _trash_superseded(self, out_dir: Path, image: str, keep: set[str]) -> None:
        """Send earlier-dated copies of this target+mode to the trash.

        The date is part of the name, so a re-run writes new files beside the
        old ones instead of overwriting them — three 104 MB FITS per mode, per
        run. These are copies (``process/starless_*.fit`` is the original), so
        removing them is safe. `gio trash`, never `rm`: this drive is the only
        copy of Raws/, and trashy misresolves its mount point.
        """
        pattern = f"*_{self._target_tag()}-{mode_label(image)}_*"
        stale = [p for p in out_dir.glob(pattern) if p.name not in keep]
        if not stale:
            return
        try:
            subprocess.run(
                ["gio", "trash", *(str(p) for p in stale)],
                check=True, capture_output=True, text=True,
            )
        except (OSError, subprocess.CalledProcessError) as exc:
            self.siril.log(
                f"_STRETCH_ME: could not trash {len(stale)} superseded file(s); "
                f"leaving them in place ({exc})"
            )
            return
        self.siril.log(
            f"_STRETCH_ME: trashed {len(stale)} superseded file(s) from an "
            f"earlier run: {', '.join(p.name for p in stale)}"
        )

    def _write_stretch_me(self, image: str) -> None:
        """Copy the pre-stretch pair into a clearly-named _STRETCH_ME/
        folder with a README. This is the default hand-off: stretch the
        denoised-linear STARLESS by hand; the linear STARS mask feeds star
        recomposition. Always runs (write_stretch_me defaults True).
        """
        cwd = self.cwd()
        starless = cwd / f"starless_{image}_denoised.fit"
        starmask = cwd / f"starmask_{image}_denoised.fit"
        if not starless.exists():
            self.siril.log(
                f"_STRETCH_ME: {starless.name} missing; skipping checkpoint"
            )
            return
        out_dir = self._stretch_me_dir()
        out_dir.mkdir(exist_ok=True)
        base = self._stretch_me_base(image)
        out_starless = out_dir / f"{base}_STARLESS.fit"
        out_stars = out_dir / f"{base}_STARS.fit"
        out_preview = out_dir / f"{base}_STARLESS_preview.jpg"
        self._trash_superseded(
            out_dir, image,
            keep={out_starless.name, out_stars.name, out_preview.name},
        )
        self._step(f"Checkpoint -> _STRETCH_ME/{out_starless.name}")
        shutil.copy2(starless, out_starless)
        if starmask.exists():
            shutil.copy2(starmask, out_stars)
        else:
            self.siril.log(
                f"_STRETCH_ME: {starmask.name} missing; STARS not written"
            )
        # Two measurements of the same pre-denoise frame: asinh params drive the
        # rendered preview and the on-screen image (representative), MTF params
        # feed the README's printed numbers (for anyone using Siril's own
        # autostretch). Both derive from <image>_deconvolved.fit, never the
        # denoised starless.
        asinh_params = self._preview_params(image)
        mtf_params = self._prestretch_params(image)
        if asinh_params is not None:
            self._write_stretch_preview(image, out_preview, asinh_params)
        (out_dir / "README.txt").write_text(
            "_STRETCH_ME - pre-stretch hand-off pairs.\n\n"
            "  *_STARLESS.fit : denoised, LINEAR starless. Stretch by hand.\n"
            "  *_STARS.fit    : LINEAR star mask. Feed to star recomposition\n"
            "                   (VeraLux StarComposer / GIMP); stars go in\n"
            "                   linear, over the stretched starless.\n"
            "  *_STARLESS_preview.jpg\n"
            "                 : a representative asinh render of the STARLESS -\n"
            "                   near-black sky, arms visible. Judge the data on\n"
            "                   THIS, not on Siril's display autostretch - that\n"
            "                   recomputes the stretch from the denoised frame\n"
            "                   and invents coloured blotches (see below). The\n"
            "                   numbers below are for a Siril MTF autostretch and\n"
            "                   do not describe the preview's asinh curve.\n\n"
            "Files are named <YYYY-MM-DD>_<target>-<MODE>_{STARLESS,STARS}.fit,\n"
            "the date being the processing run's.\n\n"
            + ("" if mtf_params is None else self._stretch_hint(image, mtf_params))
        )
        # Last: leave the preview on screen. Done after the README so a failure
        # to load never costs the checkpoint files themselves.
        if asinh_params is not None:
            self._load_preview(out_starless, asinh_params)

    def _prestretch_params(self, image: str) -> list[tuple[float, float]] | None:
        """Autostretch parameters measured on the PRE-denoise frame.

        Do NOT autostretch the STARLESS directly. Prism removed ~94 % of its
        noise, and Siril's autostretch sets its black point at median - 2.8*sigma
        — so on the denoised frame it computes a far harsher midtone (measured on
        M 101: 6.2x at modulation 0.85, ~16x at 1.0) and lifts Prism's own
        low-frequency residual into visible coloured blotches. (It does NOT blow
        the core — Prism does that, by clamping it to 1.0 under its own internal
        stretch; see _run_prism. No stretch can undo a saturated pixel.) Take
        them from
        <image>_deconvolved.fit while it still has its noise. (Same pixels,
        honest stretch => clean image.)

        Shared by the README hint and the preview render, so the JPEG a human
        looks at is stretched with exactly the numbers the README prints.
        """
        src = self.cwd() / f"{image}_deconvolved.fit"
        if not src.exists():
            return None
        try:
            data = np.asarray(fits.getdata(src), dtype=np.float32)
            if data.ndim == 2:
                data = data[np.newaxis, ...]
            return self._autostretch_params(data)
        except Exception as exc:  # noqa: BLE001 - best-effort
            self.siril.log(f"_STRETCH_ME: could not measure stretch params: {exc}")
            return None

    def _preview_params(self, image: str) -> list[tuple[float, float, float]] | None:
        """asinh preview parameters, all measured on the PRE-denoise frame.

        Returns per-channel ``(black_point, span, beta)``. Same invariant as
        ``_prestretch_params`` — nothing comes from the denoised frame's
        collapsed sigma — but the curve is asinh, not MTF, so the preview is
        representative rather than a flat grey screen-stretch. See the
        PREVIEW_* constants for why.

        ``beta`` is solved per channel so the reference median lands at
        ``PREVIEW_TARGET_BG`` after the curve: ``asinh(beta * x_med) /
        asinh(beta) = TARGET_BG``, bisected in log space.
        """
        src = self.cwd() / f"{image}_deconvolved.fit"
        if not src.exists():
            return None
        try:
            ref = np.asarray(fits.getdata(src), dtype=np.float32)
            if ref.ndim == 2:
                ref = ref[np.newaxis, ...]
            params: list[tuple[float, float, float]] = []
            for i in range(ref.shape[0]):
                med = float(np.median(ref[i]))
                sig = 1.4826 * float(np.median(np.abs(ref[i] - med)))
                bp = max(0.0, med - PREVIEW_BLACK_OFFSET * sig)
                white = float(np.percentile(ref[i], 99.8))
                span = max(white - bp, 1e-9)
                x_med = (med - bp) / span
                lo, hi = 1.0, 1e7
                for _ in range(60):
                    beta = (lo * hi) ** 0.5
                    if np.arcsinh(beta * x_med) / np.arcsinh(beta) > PREVIEW_TARGET_BG:
                        hi = beta
                    else:
                        lo = beta
                params.append((bp, span, (lo * hi) ** 0.5))
            return params
        except Exception as exc:  # noqa: BLE001 - best-effort
            self.siril.log(f"_STRETCH_ME: could not measure preview params: {exc}")
            return None

    @staticmethod
    def _apply_asinh(
        data: np.ndarray, params: list[tuple[float, float, float]]
    ) -> np.ndarray:
        """asinh stretch a (C,H,W) array with per-channel (bp, span, beta)."""
        out = np.empty_like(data, dtype=np.float32)
        for i in range(data.shape[0]):
            bp, span, beta = params[min(i, len(params) - 1)]
            x = np.clip((data[i] - bp) / span, 0.0, 1.0)
            out[i] = np.arcsinh(beta * x) / np.arcsinh(beta)
        return np.clip(out, 0.0, 1.0)

    def _write_stretch_preview(
        self, image: str, dest: Path, params: list[tuple[float, float, float]]
    ) -> None:
        """Render the STARLESS with the asinh preview stretch, as a JPEG.

        The checkpoint FITS is linear, so the only way to look at it is through
        some stretch — and Siril's *display* autostretch recomputes one from the
        loaded frame's sigma. On a denoised starless that is the very mistake
        the README warns against, so opening the checkpoint to "check it" shows
        coloured continents, a dark halo and a blown core that exist nowhere in
        the data. This preview is the honest, and representative, view of the
        same pixels: a glance at the hand-off point can then never mislead.
        """
        starless = self.cwd() / f"starless_{image}_denoised.fit"
        try:
            data = np.asarray(fits.getdata(starless), dtype=np.float32)
            if data.ndim == 2:
                data = data[np.newaxis, ...]
            rgb = self._apply_asinh(data, params)
            arr = (rgb * 255.0).astype(np.uint8)
            arr = arr[0] if arr.shape[0] == 1 else np.transpose(arr, (1, 2, 0))
            img = Image.fromarray(arr)
            img.thumbnail((PREVIEW_MAX_PX, PREVIEW_MAX_PX), Image.LANCZOS)
            img.save(dest, quality=92, optimize=True)
        except Exception as exc:  # noqa: BLE001 - preview is best-effort
            self.siril.log(f"_STRETCH_ME: could not render preview: {exc}")
            return
        self._step(f"Checkpoint -> _STRETCH_ME/{dest.name}")

    def _load_preview(
        self, target: Path, params: list[tuple[float, float, float]]
    ) -> None:
        """Leave the preview on screen as the loaded image, at full resolution.

        Ends each mode showing what the data actually looks like, rather than
        the linear starless — which Siril's display autostretch would render as
        coloured continents and a blown core (see _prestretch_params). Same
        asinh curve as the JPEG, applied to Siril's in-memory buffer.

        Loads the ``_STRETCH_ME`` **copy**, not ``process/starless_*.fit``: the
        stretch is applied to the in-memory buffer and never saved, but if a
        stray Ctrl+S in Siril ever did save it, it must land on a regenerable
        copy and not on the pristine starless. This drive is the only copy.
        """
        if not target.exists():
            return
        try:
            self._load_master(str(target))
            buf = self.siril.get_image_pixeldata()
            if buf is None:
                raise RuntimeError("no image loaded")
            out = self._apply_asinh(np.asarray(buf, dtype=np.float32), params)
            with self.siril.image_lock():
                self.siril.set_image_pixeldata(out)
            self.siril.undo_save_state("asinh preview (pre-denoise parameters)")
        except (CommandError, SirilError, RuntimeError) as exc:
            self.siril.log(f"_STRETCH_ME: could not load preview: {exc}")
            return
        self.siril.log(
            f"Showing {target.name} under the asinh preview stretch. "
            "The file on disk is untouched and still linear — this is a preview, "
            "do not save it."
        )

    def _stretch_hint(self, image: str, params: list[tuple[float, float]]) -> str:
        """README block naming the pre-denoise stretch parameters."""
        src = self.cwd() / f"{image}_deconvolved.fit"
        lines = [
            "AUTOSTRETCH PARAMETERS - measured on the PRE-denoise frame.",
            "",
            "  Do NOT let autostretch derive these from the STARLESS: it has",
            "  almost no noise left, so autostretch computes a far harsher",
            "  midtone, blows the core, and drags the denoiser's low-frequency",
            "  residual into view as coloured blotches. Set them by hand:",
            "",
        ]
        for chan, (lo, midtone) in zip("RGB", params):
            lines.append(f"    {chan}: black point {lo:.6f}   midtone {midtone:.6f}")
        lines.append("")
        lines.append(f"  (from {src.name}, shadows clip -2.8 sigma, target bg 0.25)")
        lines.append("")
        lines.append("  VeraLux HyperMetric: leave 'Adaptive Anchor' TICKED (default) and")
        lines.append("  ignore the numbers above - its anchor comes from the smoothed")
        lines.append("  histogram, not from sigma, so it is safe on a denoised frame.")
        lines.append("  Untick it and the 0.5-percentile anchor lands under the sky; HMS")
        lines.append("  then divides the background by ~0 to rebuild colour, and the")
        lines.append("  denoiser's residual erupts as green/magenta blotches.")
        return "\n".join(lines) + "\n"

    # --- stats --------------------------------------------------------

    def _day_dir(self, day: str) -> Path | None:
        """Resolve a day label to its on-disk directory.

        Multi-day layouts put LIGHTS under root/<day>/; single-day layouts
        can have root *be* the day directory, with LIGHTS at the root.
        """
        candidate = self.root_dir / day
        if (candidate / "LIGHTS").is_dir():
            return candidate
        if (self.root_dir / "LIGHTS").is_dir() and self.root_dir.stem == day:
            return self.root_dir
        return None

    @staticmethod
    def _count_registered(process_dir: Path, filter_name: str) -> int:
        """Count r_pp_<filter>_NNNNN.fit frames written by seqapplyreg."""
        if not process_dir.is_dir():
            return 0
        pattern = re.compile(
            rf"^r_pp_{re.escape(filter_name)}_\d+\.fits?$"
        )
        return sum(
            1 for f in process_dir.iterdir() if pattern.match(f.name)
        )

    @staticmethod
    def _stack_summary(
        process_dir: Path, filter_name: str
    ) -> tuple[int, float]:
        """Read STACKCNT and integration time from the per-day master.

        Falls back to STACKCNT * EXPTIME if LIVETIME is missing.
        """
        master = process_dir / f"master_{filter_name}.fit"
        if not master.exists():
            return 0, 0.0
        try:
            with fits.open(master) as hdul:
                hdr = hdul[0].header
                stackcnt = int(hdr.get("STACKCNT", 0) or 0)
                livetime_raw = hdr.get("LIVETIME")
                if livetime_raw is not None:
                    livetime = float(livetime_raw)
                else:
                    exptime = float(hdr.get("EXPTIME", 0.0) or 0.0)
                    livetime = stackcnt * exptime
        except (OSError, ValueError, TypeError):
            return 0, 0.0
        return stackcnt, livetime

    def collect_stats(
        self, days: list[str], options: list[str]
    ) -> dict:
        """Summarise the per-day captured/registered/stacked frame counts
        plus integration time for the filters the run actually touched.

        Counts come straight from disk so the dialog reflects what is
        really there, not what the pipeline thinks it produced.
        """
        target_filters = self._target_filter_names(options)
        per_day: dict[str, dict[str, dict]] = {}
        totals: dict[str, dict] = {
            fn: {
                "captured": 0,
                "registered": 0,
                "stacked": 0,
                "integration_s": 0.0,
            }
            for fn in target_filters
        }

        for day in days:
            day_dir = self._day_dir(day)
            if day_dir is None:
                continue
            day_stats: dict[str, dict] = {}
            lights_dir = day_dir / "LIGHTS"
            process_dir = day_dir / "process"
            captured_counts: dict[str, int] = {}
            if lights_dir.is_dir():
                for entry in lights_dir.iterdir():
                    if not entry.is_file():
                        continue
                    m = re.search(RE_LIGHTS, entry.name)
                    if not m:
                        continue
                    ft = m.group(2).lower()
                    captured_counts[ft] = captured_counts.get(ft, 0) + 1
            for filter_name in target_filters:
                captured = captured_counts.get(filter_name, 0)
                registered = self._count_registered(process_dir, filter_name)
                stacked, integration_s = self._stack_summary(
                    process_dir, filter_name
                )
                day_stats[filter_name] = {
                    "captured": captured,
                    "registered": registered,
                    "stacked": stacked,
                    "integration_s": integration_s,
                }
                totals[filter_name]["captured"] += captured
                totals[filter_name]["registered"] += registered
                totals[filter_name]["stacked"] += stacked
                totals[filter_name]["integration_s"] += integration_s
            per_day[day] = day_stats

        filter_order = sorted(
            target_filters,
            key=lambda n: FILTER_DISPLAY_ORDER.get(
                FILTER_CODE_FROM_NAME.get(n, ""), 99
            ),
        )
        grand_total_s = sum(t["integration_s"] for t in totals.values())
        return {
            "per_day": per_day,
            "totals": totals,
            "filter_order": filter_order,
            "grand_total_s": grand_total_s,
        }


# --- GUI --------------------------------------------------------------------


class PipelineWorker(QObject):
    """Runs a supplied `run_fn()` on a QThread, surfacing progress and final
    state via Qt signals. Cancellation is cooperative — set by `cancel()`
    and checked by the pipeline at every `_step` boundary, plus a SIGTERM
    nudge to any running SyQon / GraXpert subprocess so a long-running
    deconv, denoise, or star-removal pass doesn't pin the worker until
    completion.

    `run_fn` runs on the worker thread and returns the stats dict emitted by
    `finished` (or `{}`). Each front-end (single-target, mosaic, VeraLux)
    supplies its own closure — it should already have set the pipeline's
    tunable attributes (deconv_strength, cluster_mode, common names, VeraLux
    flags, …) before the thread starts.
    """

    progress = pyqtSignal(str)
    finished = pyqtSignal(dict)
    failed = pyqtSignal(str)
    # Emitted (with the prompt) when the pipeline blocks for a manual step;
    # the GUI shows a Continue affordance and calls resume() to unblock.
    paused = pyqtSignal(str)

    def __init__(
        self,
        pipeline: Pipeline,
        run_fn: Callable[[], dict],
    ) -> None:
        super().__init__()
        self.pipeline = pipeline
        self.run_fn = run_fn
        self._cancel_requested = False
        self._resume_event = threading.Event()

    def cancel(self) -> None:
        if self._cancel_requested:
            return
        self._cancel_requested = True
        # Unblock a manual-crop pause so the worker can raise and exit.
        self._resume_event.set()
        self._kill_external_subprocesses()

    def resume(self) -> None:
        """Called from the GUI thread to release a manual-step pause."""
        self._resume_event.set()

    def _pause(self, message: str) -> None:
        """Runs on the worker thread: announce the pause to the GUI, then
        block until resume()/cancel() sets the event."""
        self._resume_event.clear()
        self.paused.emit(message)
        self._resume_event.wait()
        if self._cancel_requested:
            raise PipelineCancelled()

    def _kill_external_subprocesses(self) -> None:
        """Send SIGTERM to any running SyQon or GraXpert process so a
        cancel click takes effect mid-stage instead of waiting for the
        Siril command to return. The Siril command then surfaces a
        CommandError, which run() reclassifies as a cancellation.
        """
        try:
            import psutil
        except ImportError:
            return
        # The SyQon tools run as pyscript children named Parallax.py /
        # Prism.py / Starless.py; GraXpert (still used for background
        # extraction) as GraXpert-AI.py. Match those script basenames in
        # the cmdline — Siril's own process carries none of them. "starnet"
        # is kept for any legacy StarNet child still lingering.
        targets = ("graxpert", "parallax", "prism", "starless", "starnet")
        killed = 0
        for proc in psutil.process_iter(["pid", "name", "cmdline"]):
            try:
                info = proc.info
                cmdline = " ".join(info.get("cmdline") or []).lower()
                name = (info.get("name") or "").lower()
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue
            if any(t in cmdline or t in name for t in targets):
                try:
                    proc.terminate()
                    killed += 1
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    pass
        if killed:
            try:
                self.pipeline.siril.log(
                    f"Cancel: terminated {killed} external process(es)"
                )
            except Exception:
                pass

    def run(self) -> None:
        self.pipeline.progress_callback = self.progress.emit
        self.pipeline.cancel_check = self._raise_if_cancelled
        self.pipeline.pause_callback = self._pause
        try:
            stats = self.run_fn() or {}
            self.finished.emit(stats)
        except PipelineCancelled:
            self.failed.emit("Cancelled")
        except CommandError as e:
            # If the user cancelled, a Siril command will likely surface
            # a CommandError because we killed GraXpert mid-call. Treat
            # that as the cancellation, not a hard failure.
            if self._cancel_requested:
                self.failed.emit("Cancelled")
            else:
                self.failed.emit(f"Error running command: {e}")
        except SirilError as e:
            if self._cancel_requested:
                self.failed.emit("Cancelled")
            else:
                self.failed.emit(f"Error initializing script: {e}")
        except Exception as e:
            if self._cancel_requested:
                self.failed.emit("Cancelled")
            else:
                self.failed.emit(f"Unexpected error: {e}")
        finally:
            try:
                siril_cd(self.pipeline.siril, self.pipeline.root_dir)
            except Exception:
                pass
            self.pipeline.progress_callback = None
            self.pipeline.cancel_check = None
            self.pipeline.pause_callback = None

    def _raise_if_cancelled(self) -> None:
        if self._cancel_requested:
            raise PipelineCancelled()


def _format_duration(seconds: float) -> str:
    """Render a duration as `H h MM min` (or just minutes under an hour).

    Used by the post-run stats panel — astrophotographers think in
    integration hours, not seconds.
    """
    if seconds <= 0:
        return "0 min"
    total_min = int(round(seconds / 60.0))
    h, m = divmod(total_min, 60)
    if h == 0:
        return f"{m} min"
    return f"{h} h {m:02d} min"


class StatsDialog(QDialog):
    """Modal summary of the per-day frame counts and integration time
    produced by the run that just finished. Shown in place of the old
    bare success QMessageBox."""

    def __init__(self, stats: dict, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Processing complete")
        self.setModal(True)
        layout = QVBoxLayout(self)
        label = QLabel(self._format(stats))
        label.setTextFormat(Qt.TextFormat.RichText)
        label.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse
        )
        layout.addWidget(label)
        button_row = QHBoxLayout()
        button_row.addStretch(1)
        close_btn = QPushButton("Close")
        close_btn.clicked.connect(self.accept)
        button_row.addWidget(close_btn)
        layout.addLayout(button_row)

    @staticmethod
    def _format(stats: dict) -> str:
        per_day = stats.get("per_day", {}) or {}
        totals = stats.get("totals", {}) or {}
        filter_order = stats.get("filter_order", []) or []
        if not per_day:
            return "<b>Processing finished successfully.</b>"

        lines: list[str] = ["<b>Processing finished successfully.</b>"]
        for day in sorted(per_day):
            day_block = per_day[day] or {}
            day_lines: list[str] = []
            for filter_name in filter_order:
                fs = day_block.get(filter_name)
                if not fs:
                    continue
                if fs["captured"] == 0 and fs["stacked"] == 0:
                    continue
                display = FILTER_LABELS.get(filter_name, filter_name)
                day_lines.append(
                    f"&nbsp;&nbsp;• {display}: "
                    f"{fs['captured']} → {fs['registered']} registered → "
                    f"{fs['stacked']} stacked "
                    f"({_format_duration(fs['integration_s'])})"
                )
            if not day_lines:
                continue
            lines.append("")
            lines.append(f"<b>{day}</b>")
            lines.extend(day_lines)

        parts: list[str] = []
        for filter_name in filter_order:
            t = totals.get(filter_name)
            if not t or t["stacked"] == 0:
                continue
            display = FILTER_LABELS.get(filter_name, filter_name)
            parts.append(f"{t['stacked']} {display}")
        grand = stats.get("grand_total_s", 0.0) or 0.0
        if parts:
            lines.append("")
            lines.append(
                f"<b>Total:</b> {', '.join(parts)} "
                f"(total: {_format_duration(grand)})"
            )
        return "<br>".join(lines)


# --- discovery helpers ------------------------------------------------------


def get_available_days(siril) -> list[str]:
    current_dir = siril_cwd(siril)
    siril.log(f"looking for data in {current_dir}")
    folders = [f.name for f in current_dir.iterdir() if f.is_dir()]
    siril.log(f"folders found: {folders}")
    if "LIGHTS" in folders and "FLATS" in folders:
        return [current_dir.stem]
    return [
        folder for folder in folders if re.search(RE_DATE, folder)
    ]


def filters_in_lights(lights_dir: Path) -> set[str]:
    filters: set[str] = set()
    for entry in lights_dir.iterdir():
        if not entry.is_file():
            continue
        m = re.search(RE_LIGHTS, entry.name)
        if m:
            filters.add(m.group(2)[0].upper())
    return filters


def label_days(siril, days: list[str], single_day_root: Path) -> list[str]:
    labels: list[str] = []
    if len(days) > 1:
        for day in days:
            lights = siril_cwd(siril) / day / "LIGHTS"
            labels.append(f"{day} [{order_filters(filters_in_lights(lights))}]")
    elif days:
        # Single-day case: lights live either at root/LIGHTS (we're already
        # in the day dir) or at root/<day>/LIGHTS.
        candidates = [
            single_day_root / "LIGHTS",
            single_day_root / days[0] / "LIGHTS",
        ]
        filters: set[str] = set()
        for c in candidates:
            if c.is_dir():
                filters = filters_in_lights(c)
                break
        labels.append(f"{days[0]} [{order_filters(filters)}]")
    return labels


# --- shooting-mode helpers --------------------------------------------------


def filters_from_day_labels(labels: Iterable[str]) -> set[str]:
    """Pull the single-letter filter codes out of `[LRGB]`-style label tags.

    Each label produced by label_days() carries a bracketed filter string
    (e.g. "2025-08-20 [LRGBHO]"); this collects the union across labels.
    """
    filters: set[str] = set()
    for label in labels:
        for match in re.findall(r"\[([A-Z]+)\]", label):
            filters.update(match)
    return filters


def available_shooting_modes(filters: set[str]) -> list[ShootingMode]:
    """Which recombination families the captured filters can support."""
    modes: list[ShootingMode] = []
    if {"S", "H", "O"} <= filters:
        modes.append(ShootingMode.SHO)
    if {"L", "R", "G", "B"} <= filters:
        modes.append(ShootingMode.LRGB)
    if {"L", "R", "G", "B", "H"} <= filters:
        modes.append(ShootingMode.HALRGB)
    if {"R", "G", "B"} <= filters:
        modes.append(ShootingMode.RGB)
    return modes


def options_for_modes(modes: list[ShootingMode]) -> list[str]:
    """Expand shooting modes into the concrete recombination option labels
    offered in the GUI, in display order."""
    options: list[str] = []
    if ShootingMode.SHO in modes:
        options.extend(SHO_PALETTE_OPTIONS)
    if ShootingMode.LRGB in modes:
        options.append("LRGB")
    if ShootingMode.HALRGB in modes:
        options.extend(["HaLRGB-R", "HaLRGB-L"])
    if ShootingMode.RGB in modes:
        options.append("RGB")
    return options

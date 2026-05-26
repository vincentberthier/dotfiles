#!/usr/bin/env python3

import os
import re
import shutil
import sys
import time
from contextlib import contextmanager
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Callable, Iterable, Iterator

import sirilpy

sirilpy.ensure_installed("PyQt6", "astropy", "numpy", "PyYAML", "psutil")

import numpy as np
import yaml
from astropy.io import fits
from sirilpy import CommandError, SirilError
from PyQt6.QtCore import QObject, Qt, QThread, pyqtSignal
from PyQt6.QtWidgets import (
    QApplication,
    QButtonGroup,
    QCheckBox,
    QDialog,
    QDoubleSpinBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QRadioButton,
    QVBoxLayout,
    QWidget,
)


# --- Configuration ----------------------------------------------------------

DARK_PATH = Path(
    os.environ.get(
        "ASTRO_HIBOU_DARK_PATH",
        "/run/media/vincent/Corrbolg/Astro/Raws/Calibration",
    )
)
SIRIL_MIN_VERSION = "1.5.0"

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
    candidate = DARK_PATH / f"master_darks_{exposure}.fit"
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
        # Tunable post-processing knobs; the GUI overrides per run.
        self.deconv_full_image: bool = False
        self.deconv_strength: float = 0.5
        self.denoise_strength: float = 0.5
        # Cluster mode swaps the deepsky do_process path for one tailored
        # to star fields (no starnet, stellar deconv).
        self.cluster_mode: bool = False
        # Weight of Ha in the HaLRGB-R/L blends: channel = (1-w)*base + w*Ha.
        self.ha_weight: float = 0.5
        # Common names (FR/EN) entered in the GUI; threaded into the
        # YAML sidecar at the end of each per-target pipeline run.
        self.common_name_fr: str | None = None
        self.common_name_en: str | None = None
        # The data-night currently being processed; threaded into _step
        # so logs read e.g. "[2026-04-07] Master flat: blue".
        self.current_day: str | None = None

    # --- low-level helpers ---------------------------------------------

    def cwd(self) -> Path:
        return siril_cwd(self.siril)

    def cd(self, path) -> None:
        siril_cd(self.siril, path)

    def open_image(self, image_name) -> None:
        self.siril.cmd("load", f'"{image_name}"')

    def _step(self, message: str) -> None:
        """Announce a stage: yield to a pending cancel, log to siril, and
        emit a progress event. Use at the top of each user-visible stage.

        Prefixes the message with the data-night being processed when
        one is set (per-day prep work). Cross-day and post-recombination
        stages run with `current_day = None`, so no prefix.
        """
        if self.cancel_check is not None:
            self.cancel_check()
        prefix = f"[{self.current_day}] " if self.current_day else ""
        stamped = f"{prefix}{message}"
        self.siril.log(stamped)
        if self.progress_callback is not None:
            self.progress_callback(stamped)

    @contextmanager
    def _day_context(self, day: str) -> Iterator[None]:
        previous = self.current_day
        self.current_day = day
        try:
            yield
        finally:
            self.current_day = previous

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

    def process_single_day(
        self, day: str, mode: str, options: list[str]
    ) -> None:
        start_dir = self.cwd()
        with self._day_context(day):
            self._step(f"Processing day {day}")
            if start_dir.stem != day:
                self.cd(day)

            target_filters = self._target_filter_names(options)
            self.prepare_flats(target_filters)
            self.prepare_channels(target_filters)

            if mode == "full":
                self.compose(options)
                self.process(options)

            if self.cwd() != start_dir:
                self.cd(start_dir)

    def process_multiple_days(
        self, days: list[str], mode: str, options: list[str]
    ) -> None:
        start_dir = self.cwd()
        (start_dir / "process").mkdir(exist_ok=True)
        target_filters = self._target_filter_names(options)
        all_filters: set[str] = set()

        for day in days:
            with self._day_context(day):
                self._step(f"Day {day}")
                with cwd_at(self.siril, start_dir / day):
                    self.prepare_flats(target_filters)
                    day_filters = list(self.prepare_channels(target_filters))
                for filter_name in day_filters:
                    src = start_dir / day / "process" / f"master_{filter_name}.fit"
                    dest_dir = start_dir / "process" / filter_name
                    dest_dir.mkdir(exist_ok=True)
                    shutil.copy2(src, dest_dir / f"{day}.fit")
                all_filters.update(day_filters)

        for filter_name in all_filters:
            self._stack_filter_across_days(start_dir, filter_name)

        if mode == "full":
            self.compose(options)
            self.process(options)

        self.cd(start_dir)

    def _stack_filter_across_days(
        self, start_dir: Path, filter_name: str
    ) -> None:
        process_dir = start_dir / "process"
        filter_dir = process_dir / filter_name
        master_path = process_dir / f"master_{filter_name}.fit"
        files = sorted(f for f in filter_dir.iterdir() if f.is_file())
        if self.history.is_done(
            process_dir,
            "stack_filter_across_days",
            detail=filter_name,
            outputs=[master_path],
            inputs=files,
        ):
            self.siril.log(
                f"Cross-day master for {filter_name} up to date, skipping"
            )
            return
        self._step(f"Stacking {filter_name} across days")
        if len(files) == 1:
            shutil.copy2(files[0], master_path)
        else:
            # The sequence is about to be rebuilt from the current per-day
            # files; clear the inner register/stack records so they actually
            # re-run instead of short-circuiting on their previous completion.
            self.history.invalidate(
                process_dir, "register_lights", detail=filter_name
            )
            self.history.invalidate(
                process_dir, "stack_lights", detail=f"r_pp_{filter_name}"
            )
            with cwd_at(self.siril, filter_dir):
                self.siril.cmd("convert", f"pp_{filter_name}", "-out=../")
            with cwd_at(self.siril, process_dir):
                self.register_lights(filter_name)
                self.stack_lights(
                    f"r_pp_{filter_name}",
                    len(files),
                    apply_quality_filters=False,
                )
        self.history.mark_done(
            process_dir, "stack_filter_across_days", detail=filter_name
        )

    # --- flats ---------------------------------------------------------

    def prepare_flats(self, filters: set[str]) -> None:
        day_dir = self.cwd()
        self._step(f"Preparing flats: {day_dir.name}")
        if self.history.is_done(day_dir, "prepare_flats"):
            self.siril.log("Step already done, skipping")
            return
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
        self.history.mark_done(day_dir, "prepare_flats")

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
        if self.history.is_done(
            self.cwd(), "calibrate_flats", detail=seq_name
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

    def prepare_channels(self, filters: set[str]) -> Iterable[str]:
        day_dir = self.cwd()
        self._step(f"Preparing channels: {day_dir.name}")
        with cwd_at(self.siril, day_dir / "LIGHTS"):
            filter_files, filter_exposure = self.get_filter_files_exposure(
                RE_LIGHTS
            )
            if self.history.is_done(day_dir, "prepare_channels"):
                self.siril.log("Step already done, skipping")
                return list(filter_files.keys())
            lights_dir = self.cwd()
            for filter_type, files in filter_files.items():
                if filter_type not in filters:
                    continue
                self.create_master_channel(
                    filter_type, files, filter_exposure[filter_type]
                )
                self.extract_bg(filter_type)
                # create_master_channel and extract_bg leave us in
                # day/process; restore for the next iteration's symlinking.
                self.cd(lights_dir)
            self.history.mark_done(day_dir, "prepare_channels")
        return list(filter_files.keys())

    def create_master_channel(
        self, filter_type: str, files: list[str], exposure: str
    ) -> None:
        self._step(f"Master channel: {filter_type}")
        lights_dir = self.cwd()  # day/LIGHTS
        process_dir = lights_dir.parent / "process"
        master_path = process_dir / f"master_{filter_type}.fit"
        source_paths = [lights_dir / f for f in files]
        if self.history.is_done(
            lights_dir,
            "create_master_channel",
            detail=filter_type,
            outputs=[master_path],
            inputs=source_paths,
        ):
            self.siril.log("Step already done, skipping")
            return

        seq_dir = process_dir / filter_type
        if seq_dir.exists():
            shutil.rmtree(seq_dir)
        seq_dir.mkdir(parents=True, exist_ok=True)
        for f in files:
            (seq_dir / f).symlink_to(lights_dir / f)

        seq_name = filter_type
        with cwd_at(self.siril, seq_dir):
            self.siril.log("Converting files")
            self.siril.cmd("convert", seq_name, "-out=../")
        # Leave the caller in process_dir; calibrate/register/stack run there.
        self.cd(process_dir)
        self.calibrate_lights(seq_name, filter_type, exposure)
        self.register_lights(seq_name)
        self.stack_lights(f"r_pp_{seq_name}", len(files))
        self.history.mark_done(
            lights_dir, "create_master_channel", detail=filter_type
        )

    def calibrate_lights(
        self, seq_name: str, filter_type: str, exposure: str
    ) -> None:
        self.siril.log(
            f"Calibrating {seq_name} (filter={filter_type}, exposure={exposure})"
        )
        if self.history.is_done(
            self.cwd(), "calibrate_lights", detail=filter_type
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

    def register_lights(self, seq_name: str) -> None:
        if self.history.is_done(
            self.cwd(), "register_lights", detail=seq_name
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
        self.siril.cmd(
            "seqapplyreg",
            f"pp_{seq_name}",
            "-framing=min",
            "-interp=lanczos4",
        )
        self.history.mark_done(
            self.cwd(), "register_lights", detail=seq_name
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
        # Quality filters are useless — and harmful — on the cross-day
        # stack: the inputs are 2-3 per-day masters that have already had
        # their bad frames rejected upstream, and Siril's percentage
        # filter on a sequence that short keeps so few frames that the
        # stack errors out with "less than two images".
        #
        # For per-day stacks, k-sigma cutoffs (`2k`) need enough frames
        # for σ to be meaningful; on short sets fall back to a percentage
        # filter so we don't reject half the sequence on a noisy outlier
        # estimate.
        if not apply_quality_filters:
            seq_filter = ""
            rej = "rej sigma 2.0 3.5"
        elif num_files < 15:
            seq_filter = (
                "-filter-round=80% -filter-wfwhm=80% -filter-nbstars=80%"
            )
            rej = "rej sigma 2.0 3.5"
        else:
            seq_filter = (
                "-filter-round=2k -filter-wfwhm=2k -filter-nbstars=2k"
            )
            rej = "rej winsorized 2.0 3.5"
        args = [
            "stack",
            seq_name,
            rej,
            "-norm=mul",
            "-weight=wfwhm",
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
        if self.history.is_done(
            self.cwd(),
            "extract_bg",
            detail=filter_type,
            outputs=[master_path],
        ):
            self.siril.log("Step already done, skipping")
            return
        self._step(f"Background extraction: {filter_type}")
        self.siril.cmd(
            "pyscript",
            "GraXpert-AI.py",
            "-bge",
            "-correction subtraction",
            "-smoothing 0.5",
        )
        self.siril.undo_save_state("GraXpert Background Extraction")
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
        self._coverage_crop_aligned(aligned_paths)
        self.history.mark_done(process_dir, "prepare_compose_sequence")

    def _coverage_crop_aligned(
        self, aligned_paths: list[Path], *, coverage_eps: float = 1e-5
    ) -> None:
        # seqapplyreg -framing=min keeps any pixel covered by at least one
        # frame, but partial-coverage rows/cols at the boundary become
        # channel-mismatched in the composed RGB. The mismatch reads as a
        # faint colored sliver in linear data and GraXpert stellar deconv
        # rings on it into a hard dark stripe (visible in cluster mode after
        # autostretch; partly masked by StarNet in the regular path).
        # Restricting all aligned channels to the common-coverage rectangle
        # plus an adaptive inward margin removes the trigger.
        datasets: list[np.ndarray] = []
        for p in aligned_paths:
            with fits.open(p) as h:
                arr = h[0].data
            if arr.ndim == 3:
                arr = arr[0]
            datasets.append(arr.astype(np.float32))

        H, W = datasets[0].shape
        common = np.logical_and.reduce(
            [d > coverage_eps for d in datasets]
        )

        # Peel one side at a time, restricting subsequent peels to the
        # already-peeled bounds. This finds a fully-covered rectangle even
        # when uncovered pixels are limited to a single column/row in one
        # channel (cross-channel registration leaves these along the seam
        # between channel footprints; testing `common.all(axis=1)` on the
        # full frame would falsely mark every intersecting row as bad).
        x0_full, x1_full = 0, W
        y0_full, y1_full = 0, H
        while x0_full < x1_full and not common[:, x0_full].all():
            x0_full += 1
        while x1_full > x0_full and not common[:, x1_full - 1].all():
            x1_full -= 1
        while (
            y0_full < y1_full
            and not common[y0_full, x0_full:x1_full].all()
        ):
            y0_full += 1
        while (
            y1_full > y0_full
            and not common[y1_full - 1, x0_full:x1_full].all()
        ):
            y1_full -= 1
        if x1_full - x0_full < 100 or y1_full - y0_full < 100:
            self.siril.log(
                "Common-coverage rectangle too small "
                f"({x1_full - x0_full}x{y1_full - y0_full}); "
                "leaving aligned channels untouched"
            )
            return

        # Adaptive margin per side. Walk inward from the edge of the
        # fully-covered box on the channel-averaged image; stop at the
        # first row/col whose median is within 1σ of the interior noise.
        # Floor at 4 px (sub-pixel interpolation halo can extend slightly
        # past the coverage transition); cap at 40 px so a degenerate
        # field can't eat the frame.
        avg = np.mean(datasets, axis=0)
        interior = avg[
            y0_full + 60:y1_full - 60, x0_full + 60:x1_full - 60
        ]
        if interior.size == 0:
            self.siril.log(
                "Common-coverage region too small for adaptive margin; "
                "leaving aligned channels untouched"
            )
            return
        interior_med = float(np.median(interior))
        interior_mad = (
            float(np.median(np.abs(interior - interior_med))) + 1e-9
        )
        sigma = 1.4826 * interior_mad

        def walk(profile: np.ndarray) -> int:
            for i, v in enumerate(profile):
                if abs(float(v) - interior_med) < sigma:
                    return max(i, 4)
            return min(40, len(profile))

        depth = 40
        left_prof = np.median(
            avg[y0_full:y1_full, x0_full:x0_full + depth], axis=0
        )
        right_prof = np.median(
            avg[y0_full:y1_full, x1_full - depth:x1_full], axis=0
        )[::-1]
        top_prof = np.median(
            avg[y0_full:y0_full + depth, x0_full:x1_full], axis=1
        )
        bot_prof = np.median(
            avg[y1_full - depth:y1_full, x0_full:x1_full], axis=1
        )[::-1]

        m_left = walk(left_prof)
        m_right = walk(right_prof)
        m_top = walk(top_prof)
        m_bot = walk(bot_prof)

        x0 = x0_full + m_left
        x1 = x1_full - m_right
        y0 = y0_full + m_top
        y1 = y1_full - m_bot

        if (x0, y0, x1, y1) == (0, 0, W, H):
            self.siril.log("Coverage already uniform; no crop needed")
            return

        w = x1 - x0
        h = y1 - y0
        self.siril.log(
            f"Coverage crop: ({x0},{y0}) {w}x{h} "
            f"(dropped L={x0} R={W - x1} T={y0} B={H - y1})"
        )
        for p in aligned_paths:
            self.siril.cmd("load", p.name)
            self.siril.cmd("crop", str(x0), str(y0), str(w), str(h))
            self.siril.cmd("save", p.stem)

    def compose_lrgb(self) -> None:
        process_dir = self.cwd()
        out = process_dir / "lrgb.fit"
        inputs = [
            process_dir / f"aligned_{c}.fit"
            for c in ("red", "green", "blue", "luminance")
        ]
        if self.history.is_done(
            process_dir, "compose_lrgb", outputs=[out], inputs=inputs
        ):
            self.siril.log("Step already done, skipping")
            return
        self._step("Composing LRGB")
        self.linear_match("aligned_red.fit", "aligned_green.fit")
        self.linear_match("aligned_blue.fit", "aligned_green.fit")
        self.siril.cmd(
            "rgbcomp",
            "-lum=aligned_luminance.fit",
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
        """LRGB with Ha blended into the red channel.

        R' = (1-w) * R + w * Ha, where w = self.ha_weight. Ha is
        linear-matched to R first so the blend stays photometric;
        color calibration runs on the composed image, so the red
        channel it sees already includes the narrowband signal.
        """
        process_dir = self.cwd()
        out = process_dir / "halrgb_r.fit"
        inputs = [
            process_dir / f"aligned_{c}.fit"
            for c in ("red", "green", "blue", "luminance", "ha")
        ]
        w = self.ha_weight
        detail = f"w={w:.2f}"
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
        self.siril.cmd(
            "pm", f"{1 - w:.4f}*$aligned_red$ + {w:.4f}*$aligned_ha$"
        )
        self.siril.cmd("save", "blended_red")
        self.siril.cmd(
            "rgbcomp",
            "-lum=aligned_luminance.fit",
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
        """LRGB with Ha blended into the luminance channel.

        L' = (1-w) * L + w * Ha. Useful when you want to boost contrast
        on Ha-rich structure without shifting the color balance of the
        broadband channels.
        """
        process_dir = self.cwd()
        out = process_dir / "halrgb_l.fit"
        inputs = [
            process_dir / f"aligned_{c}.fit"
            for c in ("red", "green", "blue", "luminance", "ha")
        ]
        w = self.ha_weight
        detail = f"w={w:.2f}"
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
        self.siril.cmd(
            "pm",
            f"{1 - w:.4f}*$aligned_luminance$ + {w:.4f}*$aligned_ha$",
        )
        self.siril.cmd("save", "blended_luminance")
        self.siril.cmd(
            "rgbcomp",
            "-lum=blended_luminance.fit",
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

        self.siril.cmd(
            "pm", "($TO$^~$TO$)*$scaled_sii$ + ~($TO$^~$TO$)*$scaled_ha$"
        )
        self.siril.cmd("save", "forax_red")
        self.siril.cmd("close")

        self.siril.cmd(
            "pm",
            "(($TO$*$TH$)^~($TO$*$TH$))*$scaled_ha$ + "
            "~(($TO$*$TH$)^~($TO$*$TH$))*$scaled_oiii$",
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

        The pipeline stops at deconv + denoise on purpose: they're the
        last steps that benefit from linear data. Stretching, star
        recombination, and final cosmetic work happen by hand in Siril
        and GIMP afterwards. That's why we leave the
        `starless_*_denoised.fit` and `starmask_processing_*.fit` files
        on disk and exit.
        """
        # Option labels don't all map to filenames by lowercasing
        # (HaLRGB-R -> halrgb_r), so go through an explicit table.
        file_map = {
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
        with cwd_at(self.siril, self.cwd() / "process"):
            current_dir = self.cwd()
            done: list[str] = []
            for opt in recombinations:
                image = file_map.get(opt, opt.lower())
                if (current_dir / f"{image}.fit").exists():
                    self._step(f"Processing {image.upper()}")
                    self.do_process(image)
                    done.append(image)
            for image in done:
                if self.cluster_mode:
                    self.siril.log(
                        f"{image.upper()} processed; final image is "
                        f"{image}_cluster.fit"
                    )
                else:
                    self.siril.log(
                        f"{image.upper()} processed; starless and starmask "
                        "are ready"
                    )

    def do_process(self, image: str) -> None:
        if self.cluster_mode:
            self.do_process_cluster(image)
            return
        cwd = self.cwd()
        final_out = cwd / f"starless_{image}_denoised.fit"
        # Mode is part of the cache key so toggling deconv_full_image
        # invalidates the previous run rather than serving stale output.
        detail = f"{image}_{'full' if self.deconv_full_image else 'starless'}"
        if self.history.is_done(
            cwd,
            "do_process",
            detail=detail,
            outputs=[final_out],
            inputs=[cwd / f"{image}.fit"],
        ):
            self.siril.log("Step already done, skipping")
        else:
            self.siril.cmd("load", f"{image}.fit")
            if self.deconv_full_image:
                # Deconv first: stars get sharpened too, but StarNet then
                # works on cleaner data and tends to make tighter masks.
                self.deconvolve(image, on_full=True)
            self.siril.cmd("save", f"processing_{image}")
            self.siril.cmd("load", f"processing_{image}.fit")
            self.siril.cmd("starnet", "-stretch", "-upscale")
            self.siril.cmd("load", f"starless_processing_{image}.fit")
            if not self.deconv_full_image:
                # Deconv only on the starless layer: avoids ringing around
                # bright stars at the cost of overall sharpness.
                self.deconvolve(image, on_full=False)
            self.denoise(image)
            self.history.mark_done(cwd, "do_process", detail=detail)
        write_metadata_sidecar(
            final_out,
            mode=image.upper(),
            common_name_fr=self.common_name_fr,
            common_name_en=self.common_name_en,
        )

    def do_process_cluster(self, image: str) -> None:
        """Cluster path: no starnet, stellar deconv, autostretch, denoise,
        recover clipped star cores. Designed for fields where there is no
        faint extended structure to preserve, just point sources over
        background.
        """
        cwd = self.cwd()
        final_out = cwd / f"{image}_cluster.fit"
        detail = f"{image}_cluster"
        if self.history.is_done(
            cwd,
            "do_process",
            detail=detail,
            outputs=[final_out],
            inputs=[cwd / f"{image}.fit"],
        ):
            self.siril.log("Step already done, skipping")
            self.open_image(final_out.stem)
        else:
            self._step(f"Cluster: stellar deconvolve {image}")
            self.siril.cmd("load", f"{image}.fit")
            self.siril.cmd(
                "pyscript", "GraXpert-AI.py", "-deconv_stellar",
                f"-strength {self.deconv_strength:.2f}",
            )
            self.siril.undo_save_state("GraXpert Deconvolve Stellar")
            self._step(f"Cluster: autostretch {image}")
            self.siril.cmd("autostretch")
            self._step(f"Cluster: denoise {image}")
            self.siril.cmd(
                "pyscript", "GraXpert-AI.py", "-denoise",
                f"-strength {self.denoise_strength:.2f}",
            )
            self.siril.undo_save_state("GraXpert Denoise")
            self._step(f"Cluster: recover star cores {image}")
            self.siril.cmd("unclipstars")
            self.siril.cmd("save", final_out.stem)
            self.open_image(final_out.stem)
            self.history.mark_done(cwd, "do_process", detail=detail)
        write_metadata_sidecar(
            final_out,
            mode=image.upper(),
            common_name_fr=self.common_name_fr,
            common_name_en=self.common_name_en,
        )

    def deconvolve(self, image: str, *, on_full: bool) -> None:
        cwd = self.cwd()
        if on_full:
            out = cwd / f"{image}_deconvolved.fit"
            kind = "full"
        else:
            out = cwd / f"starless_{image}_deconvolved.fit"
            kind = "starless"
        detail = f"{image}_{kind}"
        if self.history.is_done(
            cwd, "deconvolve", detail=detail, outputs=[out]
        ):
            self.siril.log("Step already done, skipping")
            self.open_image(out.stem)
            return
        self._step(f"Deconvolving {image} ({kind})")
        self.siril.cmd(
            "pyscript", "GraXpert-AI.py", "-deconv_obj",
            f"-strength {self.deconv_strength:.2f}",
        )
        self.siril.undo_save_state("GraXpert Deconvolve Object")
        self.siril.cmd("save", out.stem)
        self.open_image(out.stem)
        self.history.mark_done(cwd, "deconvolve", detail=detail)

    def denoise(self, image: str) -> None:
        cwd = self.cwd()
        out = cwd / f"starless_{image}_denoised.fit"
        if self.history.is_done(
            cwd, "denoise", detail=image, outputs=[out]
        ):
            self.siril.log("Step already done, skipping")
            self.open_image(out.stem)
            return
        self._step(f"Denoising {image}")
        self.siril.cmd(
            "pyscript", "GraXpert-AI.py", "-denoise",
            f"-strength {self.denoise_strength:.2f}",
        )
        self.siril.undo_save_state("GraXpert Denoise")
        self.siril.cmd("save", out.stem)
        self.open_image(out.stem)
        self.history.mark_done(cwd, "denoise", detail=image)

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
    """Runs Pipeline.process_* on a QThread, surfacing progress and final
    state via Qt signals. Cancellation is cooperative — set by `cancel()`
    and checked by the pipeline at every `_step` boundary, plus a SIGTERM
    nudge to any running GraXpert subprocess so a long-running deconv or
    denoise doesn't pin the worker until completion.
    """

    progress = pyqtSignal(str)
    finished = pyqtSignal(dict)
    failed = pyqtSignal(str)

    def __init__(
        self,
        pipeline: Pipeline,
        days: list[str],
        mode: str,
        options: list[str],
        *,
        deconv_full_image: bool,
        deconv_strength: float,
        denoise_strength: float,
        cluster_mode: bool,
        ha_weight: float,
        common_name_fr: str = "",
        common_name_en: str = "",
    ) -> None:
        super().__init__()
        self.pipeline = pipeline
        self.days = days
        self.mode = mode
        self.options = options
        self.deconv_full_image = deconv_full_image
        self.deconv_strength = deconv_strength
        self.denoise_strength = denoise_strength
        self.cluster_mode = cluster_mode
        self.ha_weight = ha_weight
        self.common_name_fr = common_name_fr
        self.common_name_en = common_name_en
        self._cancel_requested = False

    def cancel(self) -> None:
        if self._cancel_requested:
            return
        self._cancel_requested = True
        self._kill_external_subprocesses()

    def _kill_external_subprocesses(self) -> None:
        """Send SIGTERM to any running GraXpert process so a cancel
        click takes effect mid-deconv/denoise instead of waiting for
        the pyscript call to return. The Siril command then surfaces
        a CommandError, which run() reclassifies as a cancellation.
        """
        try:
            import psutil
        except ImportError:
            return
        killed = 0
        for proc in psutil.process_iter(["pid", "name", "cmdline"]):
            try:
                info = proc.info
                cmdline = " ".join(info.get("cmdline") or []).lower()
                name = (info.get("name") or "").lower()
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue
            if "graxpert" in cmdline or "graxpert" in name:
                try:
                    proc.terminate()
                    killed += 1
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    pass
        if killed:
            try:
                self.pipeline.siril.log(
                    f"Cancel: terminated {killed} GraXpert process(es)"
                )
            except Exception:
                pass

    def run(self) -> None:
        self.pipeline.progress_callback = self.progress.emit
        self.pipeline.cancel_check = self._raise_if_cancelled
        self.pipeline.deconv_full_image = self.deconv_full_image
        self.pipeline.deconv_strength = self.deconv_strength
        self.pipeline.denoise_strength = self.denoise_strength
        self.pipeline.cluster_mode = self.cluster_mode
        self.pipeline.ha_weight = self.ha_weight
        self.pipeline.common_name_fr = self.common_name_fr
        self.pipeline.common_name_en = self.common_name_en
        try:
            if len(self.days) == 1:
                self.pipeline.process_single_day(
                    self.days[0], self.mode, self.options
                )
            else:
                self.pipeline.process_multiple_days(
                    self.days, self.mode, self.options
                )
            try:
                stats = self.pipeline.collect_stats(
                    self.days, self.options
                )
            except Exception as e:
                self.pipeline.siril.log(f"Stats collection failed: {e}")
                stats = {}
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


class Interface(QWidget):
    """Astro-Hibou launcher; delegates the actual work to a Pipeline."""

    def __init__(
        self, pipeline: Pipeline, days_list: list[str]
    ) -> None:
        super().__init__()
        self.setWindowTitle("Astro-Hibou processing")
        self.setWindowFlags(
            self.windowFlags() | Qt.WindowType.WindowStaysOnTopHint
        )
        self.pipeline = pipeline
        self.days_list = days_list

        self.day_checks: dict[str, QCheckBox] = {}
        self.option_checks: dict[str, QCheckBox] = {}
        self.mode_full: QRadioButton | None = None
        self.mode_partial: QRadioButton | None = None
        self.options_layout: QVBoxLayout | None = None
        self.options_group: QGroupBox | None = None
        self.deconv_full_check: QCheckBox | None = None
        self.deconv_strength_spin: QDoubleSpinBox | None = None
        self.denoise_strength_spin: QDoubleSpinBox | None = None
        self.common_name_fr_edit: QLineEdit | None = None
        self.common_name_en_edit: QLineEdit | None = None
        self.cluster_mode_check: QCheckBox | None = None
        self.ha_weight_spin: QDoubleSpinBox | None = None
        self.reset_history_btn: QPushButton | None = None
        self.proceed_btn: QPushButton | None = None
        self.cancel_btn: QPushButton | None = None
        self.status_label: QLabel | None = None
        self.progress_bar: QProgressBar | None = None

        self._thread: QThread | None = None
        self._worker: PipelineWorker | None = None

        self._setup_ui()
        self._update_option_section()
        self.adjustSize()
        self.setFixedSize(self.size())

    # --- layout -------------------------------------------------------

    def _setup_ui(self) -> None:
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(10, 10, 10, 10)

        if len(self.days_list) > 1:
            day_group = QGroupBox("Select Days")
            day_layout = QVBoxLayout()
            for day in sorted(self.days_list):
                cb = QCheckBox(day)
                cb.toggled.connect(self._on_day_toggled)
                self.day_checks[day] = cb
                day_layout.addWidget(cb)
            day_group.setLayout(day_layout)
            main_layout.addWidget(day_group)
        elif self.days_list:
            cb = QCheckBox(self.days_list[0])
            cb.setChecked(True)
            self.day_checks[self.days_list[0]] = cb

        mode_group = QGroupBox("Mode Selection")
        mode_layout = QVBoxLayout()
        self.mode_full = QRadioButton("Full")
        self.mode_partial = QRadioButton("Partial")
        self.mode_full.setChecked(True)
        button_group = QButtonGroup(self)
        button_group.addButton(self.mode_full)
        button_group.addButton(self.mode_partial)
        mode_layout.addWidget(self.mode_full)
        mode_layout.addWidget(self.mode_partial)
        mode_group.setLayout(mode_layout)
        main_layout.addWidget(mode_group)

        self.options_group = QGroupBox("Options")
        self.options_layout = QVBoxLayout()
        self.options_group.setLayout(self.options_layout)
        main_layout.addWidget(self.options_group)

        processing_options_group = QGroupBox("Processing options")
        po_layout = QVBoxLayout()
        self.cluster_mode_check = QCheckBox("Star cluster mode")
        po_layout.addWidget(self.cluster_mode_check)
        po_form = QFormLayout()
        self.ha_weight_spin = QDoubleSpinBox()
        self.ha_weight_spin.setRange(0.0, 1.0)
        self.ha_weight_spin.setSingleStep(0.05)
        self.ha_weight_spin.setDecimals(2)
        self.ha_weight_spin.setValue(0.5)
        po_form.addRow("Ha blend weight:", self.ha_weight_spin)
        po_layout.addLayout(po_form)
        processing_options_group.setLayout(po_layout)
        main_layout.addWidget(processing_options_group)

        processing_group = QGroupBox("Processing")
        proc_layout = QVBoxLayout()
        self.deconv_full_check = QCheckBox(
            "Deconvolve full image (sharper; uncheck for safer starless-only)"
        )
        self.deconv_full_check.setChecked(False)
        proc_layout.addWidget(self.deconv_full_check)
        proc_form = QFormLayout()
        self.deconv_strength_spin = QDoubleSpinBox()
        self.deconv_strength_spin.setRange(0.0, 1.0)
        self.deconv_strength_spin.setSingleStep(0.05)
        self.deconv_strength_spin.setDecimals(2)
        self.deconv_strength_spin.setValue(0.5)
        proc_form.addRow("Deconv strength:", self.deconv_strength_spin)
        self.denoise_strength_spin = QDoubleSpinBox()
        self.denoise_strength_spin.setRange(0.0, 1.0)
        self.denoise_strength_spin.setSingleStep(0.05)
        self.denoise_strength_spin.setDecimals(2)
        self.denoise_strength_spin.setValue(0.5)
        proc_form.addRow("Denoise strength:", self.denoise_strength_spin)
        # Common names — stamped into the YAML sidecar and consumed
        # downstream by the GIMP legend plug-in and the JPG metadata
        # injector. Pre-filled from any existing sidecar in the target.
        self.common_name_fr_edit = QLineEdit()
        self.common_name_fr_edit.setPlaceholderText("Nébuleuse Trifide, Galaxie du Sombrero…")
        proc_form.addRow("Nom commun (FR):", self.common_name_fr_edit)
        self.common_name_en_edit = QLineEdit()
        self.common_name_en_edit.setPlaceholderText("Trifid Nebula, Sombrero Galaxy…")
        proc_form.addRow("Common name (EN):", self.common_name_en_edit)
        self._prepopulate_common_names()
        proc_layout.addLayout(proc_form)
        self.reset_history_btn = QPushButton("Reset history")
        self.reset_history_btn.clicked.connect(self._on_reset_history)
        proc_layout.addWidget(self.reset_history_btn)
        processing_group.setLayout(proc_layout)
        main_layout.addWidget(processing_group)

        # Status row reserved at construction time so the window doesn't
        # change size when work starts.
        self.status_label = QLabel(" ")
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.progress_bar.setTextVisible(False)
        main_layout.addWidget(self.status_label)
        main_layout.addWidget(self.progress_bar)

        button_row = QHBoxLayout()
        button_row.addStretch(1)
        self.proceed_btn = QPushButton("Proceed")
        self.cancel_btn = QPushButton("Cancel")
        self.proceed_btn.clicked.connect(self._on_proceed)
        self.cancel_btn.clicked.connect(self._on_cancel_clicked)
        button_row.addWidget(self.proceed_btn)
        button_row.addWidget(self.cancel_btn)
        main_layout.addLayout(button_row)

    def _update_option_section(self) -> None:
        assert self.options_layout is not None
        while self.options_layout.count():
            item = self.options_layout.takeAt(0)
            w = item.widget()
            if w is not None:
                w.setParent(None)
                w.deleteLater()
        self.option_checks.clear()

        shooting_modes = self._available_shooting_modes()
        self.pipeline.siril.log(
            f"available shooting modes: {shooting_modes}"
        )

        options: list[str] = []
        if ShootingMode.SHO in shooting_modes:
            options.extend(SHO_PALETTE_OPTIONS)
        if ShootingMode.LRGB in shooting_modes:
            options.append("LRGB")
        if ShootingMode.HALRGB in shooting_modes:
            options.extend(["HaLRGB-R", "HaLRGB-L"])
        if ShootingMode.RGB in shooting_modes:
            options.append("RGB")

        for option in options:
            cb = QCheckBox(option)
            self.option_checks[option] = cb
            self.options_layout.addWidget(cb)

        self.adjustSize()
        self.setFixedSize(self.size())

    # --- selection helpers --------------------------------------------

    def _available_shooting_modes(self) -> list[ShootingMode]:
        filters: set[str] = set()
        for day_label in self._selected_days_labels():
            for match in re.findall(r"\[([A-Z]+)\]", day_label):
                filters.update(match)

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

    def _selected_days_labels(self) -> list[str]:
        return [day for day, cb in self.day_checks.items() if cb.isChecked()]

    def _selected_mode(self) -> str:
        assert self.mode_full is not None
        return "full" if self.mode_full.isChecked() else "partial"

    def _selected_options(self) -> list[str]:
        return [
            opt for opt, cb in self.option_checks.items() if cb.isChecked()
        ]

    def _is_valid(self) -> tuple[bool, str]:
        if not any(cb.isChecked() for cb in self.day_checks.values()):
            return False, "At least one day must be selected"
        if self.option_checks and not any(
            cb.isChecked() for cb in self.option_checks.values()
        ):
            return False, "At least one option must be selected"
        return True, ""

    # --- signal handlers ---------------------------------------------

    def _on_day_toggled(self, checked: bool) -> None:
        # If the user just unchecked the last day, revert: re-check the
        # sender so at least one day is always selected.
        if not any(cb.isChecked() for cb in self.day_checks.values()):
            sender = self.sender()
            if isinstance(sender, QCheckBox):
                sender.blockSignals(True)
                sender.setChecked(True)
                sender.blockSignals(False)
                return
        self._update_option_section()

    def _on_proceed(self) -> None:
        if self._is_running():
            return
        valid, message = self._is_valid()
        if not valid:
            QMessageBox.warning(self, "Invalid Selection", message)
            return

        days = [day.split()[0] for day in self._selected_days_labels()]
        mode = self._selected_mode()
        options = self._selected_options() or ["LRGB"]

        assert self.deconv_full_check is not None
        assert self.deconv_strength_spin is not None
        assert self.denoise_strength_spin is not None
        assert self.cluster_mode_check is not None
        assert self.ha_weight_spin is not None
        deconv_full_image = self.deconv_full_check.isChecked()
        deconv_strength = self.deconv_strength_spin.value()
        denoise_strength = self.denoise_strength_spin.value()
        cluster_mode = self.cluster_mode_check.isChecked()
        ha_weight = self.ha_weight_spin.value()
        assert self.common_name_fr_edit is not None
        assert self.common_name_en_edit is not None
        common_name_fr = self.common_name_fr_edit.text().strip()
        common_name_en = self.common_name_en_edit.text().strip()

        self._set_running(True, "Starting…")

        self._thread = QThread(self)
        self._worker = PipelineWorker(
            self.pipeline,
            days,
            mode,
            options,
            deconv_full_image=deconv_full_image,
            deconv_strength=deconv_strength,
            denoise_strength=denoise_strength,
            cluster_mode=cluster_mode,
            ha_weight=ha_weight,
            common_name_fr=common_name_fr,
            common_name_en=common_name_en,
        )
        self._worker.moveToThread(self._thread)
        self._thread.started.connect(self._worker.run)
        self._worker.progress.connect(self._on_worker_progress)
        self._worker.finished.connect(self._on_worker_finished)
        self._worker.failed.connect(self._on_worker_failed)
        # Tear-down: stop the thread and let Qt reclaim worker+thread once
        # the run-slot returns.
        self._worker.finished.connect(self._thread.quit)
        self._worker.failed.connect(self._thread.quit)
        self._thread.finished.connect(self._worker.deleteLater)
        self._thread.finished.connect(self._thread.deleteLater)
        self._thread.start()

    def _prepopulate_common_names(self) -> None:
        """Seed the FR/EN line edits from the most recent existing sidecar
        under the target root, so the user doesn't re-type the nicknames
        on every recombination."""
        assert self.common_name_fr_edit is not None
        assert self.common_name_en_edit is not None
        root = self.pipeline.root_dir
        candidates = list(root.glob("process/*.meta.yaml"))
        candidates += list(root.glob("*/process/*.meta.yaml"))
        candidates.sort(key=lambda p: p.stat().st_mtime, reverse=True)
        for sidecar in candidates:
            try:
                data = yaml.safe_load(sidecar.read_text(encoding="utf-8"))
            except (OSError, yaml.YAMLError):
                continue
            target = (data or {}).get("target") or {}
            fr = (target.get("common_name_fr") or "").strip()
            en = (target.get("common_name_en") or "").strip()
            if fr:
                self.common_name_fr_edit.setText(fr)
            if en:
                self.common_name_en_edit.setText(en)
            if fr or en:
                return

    def _on_reset_history(self) -> None:
        if self._is_running():
            return
        reply = QMessageBox.question(
            self,
            "Reset history",
            "Clear the cached step record? The next run will re-execute "
            "every step from scratch.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.Yes:
            self.pipeline.history.clear()
            QMessageBox.information(self, "History reset", "History cleared.")

    def _on_cancel_clicked(self) -> None:
        if self._is_running():
            assert self._worker is not None
            self._worker.cancel()
            if self.status_label is not None:
                self.status_label.setText("Cancelling…")
            if self.cancel_btn is not None:
                self.cancel_btn.setEnabled(False)
        else:
            self.close()

    def _on_worker_progress(self, message: str) -> None:
        if self.status_label is not None:
            self.status_label.setText(message)

    def _on_worker_finished(self, stats: dict) -> None:
        # After a successful run the pipeline cache has fully populated,
        # so re-clicking Proceed would be a no-op. Lock the inputs and
        # swap Cancel for Close.
        self._set_finished()
        StatsDialog(stats, parent=self).exec()

    def _on_worker_failed(self, message: str) -> None:
        self._set_running(False)
        if message == "Cancelled":
            QMessageBox.information(self, "Cancelled", "Processing cancelled")
        else:
            QMessageBox.critical(self, "Failed to execute", message)

    # --- running state plumbing --------------------------------------

    def _is_running(self) -> bool:
        return self._thread is not None and self._thread.isRunning()

    def _set_running(self, running: bool, status: str = " ") -> None:
        assert self.proceed_btn is not None
        assert self.cancel_btn is not None
        assert self.status_label is not None
        assert self.progress_bar is not None
        self.proceed_btn.setEnabled(not running)
        self.cancel_btn.setEnabled(True)
        self.cancel_btn.setText("Cancel processing" if running else "Cancel")
        self.status_label.setText(status if running else " ")
        # Indeterminate progress: the pipeline doesn't know its own length,
        # but the status label tracks the current stage.
        self.progress_bar.setRange(0, 0 if running else 100)
        if not running:
            self.progress_bar.setValue(0)
        if not running:
            self._thread = None
            self._worker = None

    def _set_finished(self) -> None:
        """Post-success state: Proceed stays disabled (the run is already
        cached on disk; clicking again would just no-op step by step),
        Cancel becomes Close so the same button dismisses the window."""
        assert self.proceed_btn is not None
        assert self.cancel_btn is not None
        assert self.status_label is not None
        assert self.progress_bar is not None
        self.proceed_btn.setEnabled(False)
        self.cancel_btn.setEnabled(True)
        self.cancel_btn.setText("Close")
        self.status_label.setText("Processing complete")
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(100)
        self._thread = None
        self._worker = None


# --- discovery + main -------------------------------------------------------


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


def main() -> None:
    siril = sirilpy.SirilInterface()
    try:
        siril.connect()
    except sirilpy.SirilConnectionError as e:
        print(f"Failed to connect to Siril: {e}", file=sys.stderr)
        return

    try:
        siril.cmd("requires", SIRIL_MIN_VERSION)
    except CommandError as e:
        print(f"Siril version requirement not met: {e}", file=sys.stderr)
        siril.disconnect()
        return

    root_dir = siril_cwd(siril)

    available_days = get_available_days(siril)
    siril.log(f"Found days: {available_days}")
    days = label_days(siril, available_days, root_dir)

    pipeline = Pipeline(siril, root_dir)

    try:
        qapp = QApplication.instance() or QApplication(sys.argv)
        qapp.setApplicationName("Astro-Hibou")
        qapp.setStyle("Fusion")
        window = Interface(pipeline, days)
        window.show()
        qapp.exec()
    except CommandError as e:
        print(f"Error running command: {e}", file=sys.stderr)
    except SirilError as e:
        print(f"Error initializing script: {e}", file=sys.stderr)
    finally:
        try:
            siril_cd(siril, root_dir)
        finally:
            siril.disconnect()


if __name__ == "__main__":
    main()

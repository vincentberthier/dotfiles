#!/usr/bin/env python3
"""GIMP 3 plug-in: Astro Legend.

Adds two right-aligned text layers in the bottom-right of the current
image:
  - "<Target> (<Mode>)"  — Z003 Medium Italic 64 pt
  - "<jour mois année>"  — Z003 Medium Italic 48 pt  (French format)

Data sources:
  - The open image's filename (YYYY-MM-DD_<target>-<mode>.<ext>) supplies
    the session date and the target token + mode.
  - The matching YAML sidecar under RAWS_ROOT enriches the target token
    to its catalog name (e.g. "M20" → "M 20").
  - When neither resolves, placeholder text is inserted instead.

Menu: Filters → Astro → Add astro legend
"""

import re
import sys
from pathlib import Path

import gi

gi.require_version("Gimp", "3.0")
gi.require_version("Gegl", "0.4")
from gi.repository import Gegl, GLib, GObject, Gimp  # noqa: E402

import yaml  # noqa: E402  (system PyYAML)


RAWS_ROOT = Path("/run/media/vincent/Corrbolg/Astro/Raws")

# YYYY-MM-DD_<target>-<mode>[-extra…].<ext>
RE_NAME = re.compile(
    r"^(?P<y>\d{4})-(?P<m>\d{2})-(?P<d>\d{2})"
    r"_(?P<target>[^_]+?)-(?P<mode>[A-Za-z]+)"
    r"(?:-[^_]+)*?"
    r"\.(?:xcf|tif|tiff|jpg|jpeg|png)$",
    re.IGNORECASE,
)

FRENCH_MONTHS = [
    "janvier", "février", "mars", "avril", "mai", "juin",
    "juillet", "août", "septembre", "octobre", "novembre", "décembre",
]

FONT_NAME = "Z003 Medium Italic"
OBJECT_SIZE = 64.0
DATE_SIZE = 48.0
MARGIN_PCT = 0.01    # of image width, applied to right and bottom
GAP_PX = 8           # vertical gap between the two lines


def _normalize(name: str) -> str:
    return re.sub(r"\s+", "", name or "").lower()


def _french_date(year: str, month: str, day: str) -> str:
    return f"{int(day)} {FRENCH_MONTHS[int(month) - 1]} {int(year)}"


def _iter_sidecars():
    """Yield sidecars across both Raws/ layouts (single-day + date-subfolder)."""
    yield from RAWS_ROOT.glob("*/process/*.meta.yaml")
    yield from RAWS_ROOT.glob("*/*/process/*.meta.yaml")


def _find_sidecar(target_token: str, mode: str) -> Path | None:
    target_n = _normalize(target_token)
    mode_u = mode.upper()
    fallbacks: list[Path] = []
    for sidecar in _iter_sidecars():
        try:
            with open(sidecar) as f:
                meta = yaml.safe_load(f) or {}
        except (OSError, yaml.YAMLError):
            continue
        if ((meta.get("acquisition") or {}).get("mode") or "").upper() != mode_u:
            continue
        sidecar_target = (meta.get("target") or {}).get("name") or ""
        if _normalize(sidecar_target) == target_n:
            return sidecar
        # Folder-name fallback (B33 → Horsehead Nebula folder, etc.).
        rel = sidecar.relative_to(RAWS_ROOT)
        if rel.parts and _normalize(rel.parts[0]) == target_n:
            fallbacks.append(sidecar)
    return fallbacks[0] if len(fallbacks) == 1 else None


def _resolve_metadata(image_path: str | None) -> tuple[str, str]:
    placeholder = ("Object (Mode)", "1 janvier 2026")
    if not image_path:
        return placeholder
    m = RE_NAME.match(Path(image_path).name)
    if not m:
        return placeholder
    date_str = _french_date(m["y"], m["m"], m["d"])
    target_token = m["target"]
    mode = m["mode"].upper()
    target_name = target_token
    sidecar = _find_sidecar(target_token, mode)
    if sidecar is not None:
        try:
            with open(sidecar) as f:
                meta = yaml.safe_load(f) or {}
            t = (meta.get("target") or {}).get("name")
            if t:
                target_name = t
        except (OSError, yaml.YAMLError):
            pass
    return f"{target_name} ({mode})", date_str


def add_legend(procedure, run_mode, image, drawables, config, data):
    image.undo_group_start()
    try:
        gimp_file = image.get_file()
        image_path = gimp_file.get_path() if gimp_file is not None else None
        object_text, date_text = _resolve_metadata(image_path)

        font = Gimp.Font.get_by_name(FONT_NAME)
        if font is None:
            Gimp.message(f"Font '{FONT_NAME}' not found. Install URW Z003 / gsfonts.")
            return procedure.new_return_values(
                Gimp.PDBStatusType.EXECUTION_ERROR, GLib.Error()
            )

        white = Gegl.Color.new("white")
        white.set_rgba(1.0, 1.0, 1.0, 1.0)
        unit_px = Gimp.Unit.pixel()

        Gimp.context_push()
        try:
            Gimp.context_set_foreground(white)
            obj_layer = Gimp.TextLayer.new(image, object_text, font,
                                           OBJECT_SIZE, unit_px)
            date_layer = Gimp.TextLayer.new(image, date_text, font,
                                            DATE_SIZE, unit_px)
        finally:
            Gimp.context_pop()

        for layer in (obj_layer, date_layer):
            layer.set_color(white)

        image.insert_layer(date_layer, None, 0)
        image.insert_layer(obj_layer, None, 0)

        img_w = image.get_width()
        img_h = image.get_height()
        margin = max(1, int(round(img_w * MARGIN_PCT)))

        date_w = date_layer.get_width()
        date_h = date_layer.get_height()
        obj_w = obj_layer.get_width()
        obj_h = obj_layer.get_height()

        date_x = img_w - date_w - margin
        date_y = img_h - date_h - margin
        obj_x = img_w - obj_w - margin
        obj_y = date_y - obj_h - GAP_PX

        date_layer.set_offsets(date_x, date_y)
        obj_layer.set_offsets(obj_x, obj_y)

        Gimp.displays_flush()
        return procedure.new_return_values(Gimp.PDBStatusType.SUCCESS, GLib.Error())
    finally:
        image.undo_group_end()


class AstroLegend(Gimp.PlugIn):
    def do_set_i18n(self, procname):
        return False

    def do_query_procedures(self):
        return ["python-fu-astro-legend"]

    def do_create_procedure(self, name):
        Gegl.init(None)
        proc = Gimp.ImageProcedure.new(
            self, name, Gimp.PDBProcType.PLUGIN, add_legend, None
        )
        proc.set_image_types("*")
        proc.set_sensitivity_mask(
            Gimp.ProcedureSensitivityMask.DRAWABLE
            | Gimp.ProcedureSensitivityMask.DRAWABLES
        )
        proc.set_documentation(
            "Add astro legend (object + date)",
            "Adds two right-aligned text layers in the bottom-right of the "
            "current image, pulling the target name from the matching YAML "
            "sidecar and the date from the filename.",
            name,
        )
        proc.set_menu_label("Add astro legend")
        proc.set_attribution("Vincent Berthier", "Vincent Berthier", "2026")
        proc.add_menu_path("<Image>/Filters/Astro")
        return proc


Gimp.main(AstroLegend.__gtype__, sys.argv)

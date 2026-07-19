#!/usr/bin/env python3
"""GIMP 3 plug-in: Astro Legend.

Adds two right-aligned text layers in the bottom-right of the current
image:
  - "<Target> - <Common name> (<Mode>)"  — Z003 Medium Italic 64 pt
  - "<jour mois année>"                  — Z003 Medium Italic 48 pt  (French)

Data sources:
  - Filename (YYYY-MM-DD_<target>-<mode>.<ext>) supplies the session date
    and the target token + mode.
  - Matching YAML sidecar under the process tree provides the catalog target name
    (target.name) and, once entered once, the French common name
    (target.common_name_fr).

Interactive run prompts for the common name + date, prefilling whatever is
already in the sidecar. Accepted values are written back to the sidecar so
re-runs don't ask again.

Menu: Filters → Astro → Add astro legend
"""

import os
import re
import sys
from pathlib import Path

import gi

gi.require_version("Gimp", "3.0")
gi.require_version("Gegl", "0.4")
from gi.repository import Gegl, GLib, GObject, Gimp  # noqa: E402

import yaml  # noqa: E402  (system PyYAML)


ASTRO_ROOT = Path("/run/media/vincent/Corrbolg/dso")

# The drive was reorganised 2026-07-20 (REORG_PLAN.md): the single `Raws/` tree
# became data / calibration / process / products, split by replaceability. An
# image handed to this plug-in can now sit under EITHER root -- exports live in
# products/, while pipeline intermediates live under process/ -- so the target
# folder is resolved against both.
TARGET_ROOTS = (ASTRO_ROOT / "products", ASTRO_ROOT / "data")

# process/ is its own tree now, mirroring data/ (<process root>/<target>/<night>),
# and is relocatable via the same env var the pipeline uses. The legacy in-data
# layout is still searched so sidecars written before the reorg resolve.
PROCESS_ROOT = Path(
    os.environ.get("ASTRO_HIBOU_PROCESS_PATH", str(ASTRO_ROOT / "process"))
)

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


# Recombination tokens that can appear in a pipeline filename, longest /
# most-specific first so 'halrgb_r' wins over the 'rgb' it contains.
#
# Both separators are listed. Pipeline intermediates keep the underscore
# ('halrgb_r_denoised.fit'); the _STRETCH_ME checkpoints and the exports use
# the hyphenated mode label ('2026-07-10_M101-HaLRGB-R_STARLESS.fit'). Order
# matters more than it looks: 'halrgb-r' must precede 'lrgb', which is a
# substring of it, or every HaLRGB image is silently labelled LRGB.
MODE_TOKENS = (
    "halrgb_r", "halrgb_l", "halrgb-r", "halrgb-l", "lrgb", "forax",
    "sho", "hoo", "ohs", "hso", "rgb",
)


def _target_folder(image_path: Path) -> str | None:
    """Target folder name: the first path component under a known root.

    Works wherever the file sits under the target (products/, data/, the
    process tree, …) — by convention one target per folder (e.g. 'M 4').
    """
    try:
        resolved = image_path.resolve()
    except OSError:
        return None
    for root in (*TARGET_ROOTS, PROCESS_ROOT):
        try:
            rel = resolved.relative_to(root.resolve())
        except (ValueError, OSError):
            continue
        if rel.parts:
            return rel.parts[0]
    return None


def _mode_from_name(name: str) -> str | None:
    low = name.lower()
    for tok in MODE_TOKENS:
        if tok in low:
            return tok
    return None


def _parse_ymd(value) -> tuple[str, str, str] | None:
    if not value:
        return None
    m = re.match(r"\s*(\d{4})-(\d{2})-(\d{2})", str(value))
    return (m.group(1), m.group(2), m.group(3)) if m else None


def _iter_sidecars():
    # Current layout: <process root>/<target>[/<night>]/*.meta.yaml
    yield from PROCESS_ROOT.glob("*/*.meta.yaml")
    yield from PROCESS_ROOT.glob("*/*/*.meta.yaml")
    # Legacy layout: the process dir nested inside each data dir.
    for root in TARGET_ROOTS:
        yield from root.glob("*/process/*.meta.yaml")
        yield from root.glob("*/*/process/*.meta.yaml")


def _mode_key(mode: str) -> str:
    """Compare modes ignoring case and separator.

    The same mode is spelled three ways across the pipeline: 'halrgb_r' in
    intermediate filenames, 'HaLRGB-R' in the checkpoint names, sidecars and
    exports, and 'HALRGB_R' in sidecars written before 2026-07-10. All three
    must resolve to the same sidecar.
    """
    return re.sub(r"[^a-z0-9]", "", (mode or "").lower())


def _find_sidecar(target_token: str, mode: str) -> Path | None:
    target_n = _normalize(target_token)
    mode_k = _mode_key(mode)
    fallbacks: list[Path] = []
    for sidecar in _iter_sidecars():
        try:
            with open(sidecar) as f:
                meta = yaml.safe_load(f) or {}
        except (OSError, yaml.YAMLError):
            continue
        if _mode_key((meta.get("acquisition") or {}).get("mode")) != mode_k:
            continue
        sidecar_target = (meta.get("target") or {}).get("name") or ""
        if _normalize(sidecar_target) == target_n:
            return sidecar
        if _normalize(_target_folder(sidecar) or "") == target_n:
            fallbacks.append(sidecar)
    return fallbacks[0] if len(fallbacks) == 1 else None


def _resolve_metadata(image_path: str | None) -> dict:
    """Walk filename + sidecar, return everything the dialog needs.

    Keys: target_label, mode, date_text, sidecar_path, common_name.
    Falls back to placeholders for any field that can't be resolved.
    """
    out = {
        "target_label": "Object",
        "mode": "MODE",
        "date_text": "1 janvier 2026",
        "sidecar_path": None,
        "common_name": "",
    }
    if not image_path:
        return out
    name = Path(image_path).name
    m = RE_NAME.match(name)
    date_from_filename = False
    if m:
        # Export-named file: target, mode and date come from the filename.
        out["date_text"] = _french_date(m["y"], m["m"], m["d"])
        out["target_label"] = m["target"]
        out["mode"] = m["mode"].upper()
        date_from_filename = True
        sidecar = _find_sidecar(m["target"], m["mode"])
    else:
        # File straight out of the pipeline (veralux_*, starless_*, *_cluster…):
        # target is the folder under products/ or data/, mode is the token in the name,
        # and the date is read from the sidecar below.
        target_folder = _target_folder(Path(image_path))
        mode_tok = _mode_from_name(name)
        if target_folder:
            out["target_label"] = target_folder
        if mode_tok:
            out["mode"] = mode_tok.upper()
        sidecar = (
            _find_sidecar(target_folder, mode_tok)
            if target_folder and mode_tok
            else None
        )
    if sidecar is None:
        return out
    try:
        with open(sidecar) as f:
            meta = yaml.safe_load(f) or {}
    except (OSError, yaml.YAMLError):
        return out
    target = meta.get("target") or {}
    if target.get("name"):
        out["target_label"] = target["name"]
    out["common_name"] = (target.get("common_name_fr") or "").strip()
    acq = meta.get("acquisition") or {}
    if acq.get("mode"):
        out["mode"] = str(acq["mode"]).upper()
    if not date_from_filename:
        ymd = _parse_ymd(
            acq.get("date_local")
            or acq.get("date_obs_utc")
            or acq.get("date_avg_utc")
        )
        if ymd:
            out["date_text"] = _french_date(*ymd)
    out["sidecar_path"] = sidecar
    return out


def _update_sidecar_common(sidecar: Path, common_name: str) -> None:
    """Write target.common_name_fr to the sidecar, preserving the leading
    comment header. Removes the field when common_name is empty."""
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
    if common_name:
        target["common_name_fr"] = common_name
    else:
        target.pop("common_name_fr", None)
    new_body = yaml.safe_dump(data, sort_keys=False, allow_unicode=True)
    sidecar.write_text(preamble + new_body, encoding="utf-8")


def _build_object_text(target_label: str, common: str, mode: str) -> str:
    if common:
        return f"{target_label} - {common} ({mode})"
    return f"{target_label} ({mode})"


def add_legend(procedure, run_mode, image, drawables, config, data):
    image.undo_group_start()
    try:
        gimp_file = image.get_file()
        image_path = gimp_file.get_path() if gimp_file is not None else None
        info = _resolve_metadata(image_path)

        # Prefill from filename/sidecar so the dialog opens with real data.
        config.set_property("common_name", info["common_name"])
        config.set_property("date_text", info["date_text"])

        if run_mode == Gimp.RunMode.INTERACTIVE:
            gi.require_version("GimpUi", "3.0")
            from gi.repository import GimpUi
            GimpUi.init("python-fu-astro-legend")
            dialog = GimpUi.ProcedureDialog(procedure=procedure, config=config)
            dialog.fill(None)
            if not dialog.run():
                dialog.destroy()
                return procedure.new_return_values(
                    Gimp.PDBStatusType.CANCEL, GLib.Error()
                )
            dialog.destroy()

        common = (config.get_property("common_name") or "").strip()
        date_text = (config.get_property("date_text") or "").strip() or info["date_text"]

        # Persist common name back so we don't ask again next time.
        if info["sidecar_path"] is not None and common != info["common_name"]:
            try:
                _update_sidecar_common(info["sidecar_path"], common)
            except (OSError, yaml.YAMLError) as e:
                Gimp.message(f"Could not update sidecar: {e}")

        object_text = _build_object_text(info["target_label"], common, info["mode"])

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
            "current image. Pulls the target name from the matching YAML "
            "sidecar, prompts for the common name (saved back to the "
            "sidecar), and takes the date from the filename.",
            name,
        )
        proc.set_menu_label("Add astro legend")
        proc.set_attribution("Vincent Berthier", "Vincent Berthier", "2026")
        proc.add_menu_path("<Image>/Filters/Astro")

        proc.add_string_argument(
            "common_name",
            "Nom commun",
            "Common name in French (e.g. 'Nébuleuse Trifide'). "
            "Saved to the sidecar's target.common_name_fr on accept.",
            "",
            GObject.ParamFlags.READWRITE,
        )
        proc.add_string_argument(
            "date_text",
            "Date",
            "Date label (French) shown below the object name.",
            "",
            GObject.ParamFlags.READWRITE,
        )
        return proc


Gimp.main(AstroLegend.__gtype__, sys.argv)

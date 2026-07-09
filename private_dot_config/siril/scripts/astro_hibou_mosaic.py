#!/usr/bin/env python3
# debug-statement-audit: ignore — the print() calls in main() are the CLI
# entrypoint's only way to surface fatal errors to stderr when this script is
# invoked outside the Siril GUI; they are intentional, not debug cruft.
"""Astro-Hibou — multi-panel mosaic launcher.

Processes a whole multi-panel project in one run. Point Siril's working
directory at the mosaic project root, which holds one subfolder per panel
named "… Panel N" (each panel is itself an ordinary single- or multi-night
target with LIGHTS/FLATS):

    Raws/M8 - M20/            <- launch here (Siril working directory)
      Panel 1/  (LIGHTS+FLATS, or YYYY-MM-DD/ night subdirs)
      Panel 2/
      ...
      process/  <- mosaic masters + recombined output land here

For every selected panel it builds the per-filter channel masters exactly as
the single-target pipeline does (calibrate → register → stack → background
extraction, all cached), then astrometrically assembles the panels of each
filter onto one union canvas (seqplatesolve → seqapplyreg -framing=max →
mosaic stack), and finally recombines (LRGB+SPCC / SHO / …) and — in full
mode — continues into deconv/denoise/star-removal to the _STRETCH_ME
checkpoint. All the heavy lifting is the shared library, astro_hibou_core.
"""

import re
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import sirilpy  # noqa: E402
from sirilpy import CommandError, SirilError  # noqa: E402
from PyQt6.QtCore import Qt, QThread  # noqa: E402
from PyQt6.QtWidgets import (  # noqa: E402
    QApplication,
    QButtonGroup,
    QCheckBox,
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

import astro_hibou_core as core  # noqa: E402

# A panel directory is any immediate subfolder whose name carries a
# "Panel <n>" token (case-insensitive), e.g. "M8 - M20 Panel 3".
PANEL_RE = re.compile(r"panel\s*(\d+)", re.IGNORECASE)

# Feathering width (px) blended across panel seams in the mosaic stack. The
# per-panel background extraction plus overlap normalization already match
# the panels; a modest feather hides any residual seam. Set 0 to disable.
MOSAIC_FEATHER_PX = 30


# --- panel discovery --------------------------------------------------------


def discover_panels(root: Path) -> list[Path]:
    """Immediate subfolders of `root` that look like mosaic panels, ordered
    by their panel number (falling back to name order)."""
    panels: list[tuple[int, Path]] = []
    for entry in sorted(root.iterdir()):
        if not entry.is_dir():
            continue
        m = PANEL_RE.search(entry.name)
        if m:
            panels.append((int(m.group(1)), entry))
    panels.sort(key=lambda t: t[0])
    return [p for _, p in panels]


def panel_filter_codes(panel: Path) -> set[str]:
    """The single-letter filter codes captured anywhere in a panel, across
    whichever layout it uses (LIGHTS at the panel root, or per-night
    subdirectories)."""
    filters: set[str] = set()
    lights_dirs: list[Path] = []
    if (panel / "LIGHTS").is_dir():
        lights_dirs.append(panel / "LIGHTS")
    else:
        for sub in panel.iterdir():
            if sub.is_dir() and re.search(core.RE_DATE, sub.name):
                if (sub / "LIGHTS").is_dir():
                    lights_dirs.append(sub / "LIGHTS")
    for lights in lights_dirs:
        filters |= core.filters_in_lights(lights)
    return filters


def panel_label(panel: Path) -> str:
    """"Panel 3 [LRGB]" — panel name plus its bracketed filter tag, matching
    the day-label convention so core.filters_from_day_labels() can read it."""
    codes = core.order_filters(panel_filter_codes(panel))
    return f"{panel.name} [{codes}]"


# --- mosaic pipeline --------------------------------------------------------


class MosaicPipeline(core.Pipeline):
    """Adds the panel-assembly front-end to the shared Pipeline: build each
    panel's channel masters, astrometrically combine them per filter onto a
    single canvas, then hand off to the inherited compose()/process()."""

    def process_mosaic(
        self, panels: list[Path], mode: str, options: list[str]
    ) -> None:
        root = self.root_dir
        (root / "process").mkdir(exist_ok=True)
        target_filters = self._target_filter_names(options)

        # Build each panel's masters, remembering which process/ dir holds
        # them and which filters that panel actually produced.
        filter_to_procs: dict[str, list[Path]] = {}
        for panel in panels:
            # _panel_context makes every sub-step's log line lead with this
            # panel (e.g. "[Panel 4] [2025-08-13] Master flat: red").
            with self._panel_context(panel.name):
                self._step(f"{panel.name}: building masters")
                produced, proc = self.build_masters_for_target(
                    panel, target_filters
                )
            for filter_name in produced:
                filter_to_procs.setdefault(filter_name, []).append(proc)

        # Color-calibrate each panel (SPCC) BEFORE assembling, so panels sit on
        # a common absolute color reference and the mosaic comes out uniform
        # instead of a per-panel patchwork (panels leave build_masters with
        # R:G:B scaling differing 2.4x on M8-M20).
        self._spcc_calibrate_panels(filter_to_procs)

        # Assemble each filter's panels into one mosaic master.
        for filter_name in sorted(filter_to_procs):
            self._combine_panels_filter(
                filter_name, filter_to_procs[filter_name]
            )

        # Recombination + post-processing run on the assembled masters in the
        # project's own process/ dir, exactly like a single target.
        with core.cwd_at(self.siril, root):
            self.compose(options)
            if mode == "full":
                self.process(options)
        self.cd(root)

    def _spcc_calibrate_panels(
        self, filter_to_procs: dict[str, list[Path]]
    ) -> None:
        """Color-calibrate each panel independently with SPCC before assembling.

        Panels shot on different nights leave ``build_masters`` with different
        per-channel scaling — each panel's per-filter stack is ``-norm=mul``
        normalized to *its own* reference frame, so the absolute R:G:B ratio
        (the color) is arbitrary per panel. Measured on M8-M20: R/G varied 2.4x
        and B/G 2.3x across the nine panels (panel 4 green, panel 8 red), and
        that intrinsic color survives the mosaic stack (``overlap_norm`` matches
        panel *levels* per channel but not cross-channel color), so the
        assembled mosaic is a color patchwork a single global SPCC can't fix.

        The physically-correct fix is a per-panel SPCC: for each panel,
        ``rgbcomp`` its R/G/B into a temporary color image, run the same
        ``color_calibrate`` (platesolve → SPCC with the Scorpio filters + IMX533
        sensor) the single-target path uses, then ``split`` the calibrated
        channels back over the R/G/B masters. Every panel then sits on the same
        absolute color reference — they match by construction *and* carry the
        right color, not a relative median. L is luminance, not color, so it is
        left untouched. Broadband only (needs R+G+B); narrowband palettes are
        false-color and calibrated differently. ``compose()``'s global SPCC
        still runs as a final unifying pass on the assembled mosaic.

        Cached per panel (``spcc_panel``, masters as input+output like
        ``manual_crop``): a resume skips a panel unless it was re-stacked
        underneath (a fresh stack is uncalibrated, so it re-SPCCs correctly and
        never double-calibrates).
        """
        color = ["red", "green", "blue"]
        if not all(f in filter_to_procs for f in color):
            self.siril.log(
                "Per-panel SPCC needs R+G+B; skipping (narrowband or mono mosaic)"
            )
            return
        procs = [
            pp
            for pp in filter_to_procs["green"]
            if all((pp / f"master_{f}.fit").exists() for f in color)
        ]
        for pp in procs:
            originals = [pp / f"master_{f}.fit" for f in color]
            outputs = [pp / f"master_{f}_spcc.fit" for f in color]
            # Prefer the "Panel N" ancestor for the label; single-night panels'
            # proc dir is <panel>/<date>/process, so pp.parent.name is a date.
            panel = next(
                (part for part in reversed(pp.parts) if PANEL_RE.search(part)),
                pp.parent.name,
            )
            if self.history.is_done(
                pp, "spcc_panel", outputs=outputs, inputs=originals
            ):
                self.siril.log(f"{panel}: already SPCC-calibrated, skipping")
                continue
            self._step(f"Per-panel SPCC: {panel}")
            try:
                self._spcc_one_panel(pp)
            except (CommandError, SirilError) as exc:
                # A panel too sparse for SPCC (or a solve failure) shouldn't sink
                # the whole mosaic — leave it uncalibrated and press on. Its
                # region may still show a cast; flag it loudly rather than fail.
                self.siril.log(
                    f"{panel}: per-panel SPCC failed ({exc}); leaving masters "
                    "uncalibrated for this panel"
                )
                continue
            self.history.mark_done(pp, "spcc_panel")

    def _spcc_one_panel(self, pp: Path) -> None:
        """Co-register a panel's R/G/B masters, SPCC the composite, and write
        the calibrated channels back over the masters.

        The three channel masters are stacked independently, so they differ in
        size and shift by a few px — ``rgbcomp`` rejects mismatched dimensions.
        So first align them (WCS-based, the panel masters are already solved):
        ``convert`` → ``seqplatesolve`` → ``seqapplyreg -framing=min
        -interp=area`` in a scratch subdir, then ``rgbcomp`` → ``color_calibrate``
        (platesolve + SPCC) → ``split`` into **new** master_{red,green,blue}_spcc
        files (never over the raw masters — the only copy on a no-backup drive
        and the pristine input a re-run needs). L is left untouched. The _spcc
        masters are co-registered + calibrated (cropped to the channels' common
        area); the mosaic combine (which prefers them) re-registers
        astrometrically anyway, so the crop is harmless.
        """
        color = ["red", "green", "blue"]
        reg = pp / "_spcc_reg"
        if reg.exists():
            shutil.rmtree(reg)
        reg.mkdir()
        try:
            for f in color:
                (reg / f"{f}.fit").symlink_to(pp / f"master_{f}.fit")
            with core.cwd_at(self.siril, reg):
                self.siril.cmd("convert", "spcc_seq")
                self.siril.cmd("seqplatesolve", "spcc_seq")
                # -interp=area (not lanczos4): lanczos overshoots at the crop
                # boundary, leaving a bright magenta ringing sliver at the panel
                # edge that shows up as a colored seam line in the mosaic. The
                # inter-channel shifts here are tiny (same pointing), so area
                # resampling is plenty and rings nothing. -framing=min crops to
                # the area all three channels cover (no valid color outside it);
                # a panel whose blue is much smaller than R/G — e.g. a
                # degenerate blue stack — is therefore cropped to the blue
                # extent, which is correct, not a bug in this step.
                self.siril.cmd(
                    "seqapplyreg", "spcc_seq",
                    "-framing=min", "-interp=area",
                )
            # convert numbers frames alphabetically → blue=1, green=2, red=3.
            order = sorted(color)

            def frame(name: str) -> str:
                return f"_spcc_reg/r_spcc_seq_{order.index(name) + 1:05d}"

            with core.cwd_at(self.siril, pp):
                self.siril.cmd(
                    "rgbcomp",
                    frame("red"),
                    frame("green"),
                    frame("blue"),
                    "-out=_panel_spcc",
                )
                self.siril.cmd("load", "_panel_spcc")
                self.color_calibrate()
                # NON-DESTRUCTIVE: write the calibrated channels to
                # master_<f>_spcc.fit, never over the raw master_<f>.fit (the
                # only copy on a no-backup drive, and the pristine input a
                # re-run needs). _combine_panels_filter prefers the _spcc files.
                self.siril.cmd(
                    "split",
                    "master_red_spcc",
                    "master_green_spcc",
                    "master_blue_spcc",
                )
                (pp / "_panel_spcc.fit").unlink(missing_ok=True)
        finally:
            shutil.rmtree(reg, ignore_errors=True)

    def _combine_panels_filter(
        self, filter_name: str, panel_procs: list[Path]
    ) -> None:
        """Astrometrically assemble every panel's `master_<filter>.fit` onto
        one union canvas and stack into the project's mosaic master.

        Registration is plate-solve based (`seqplatesolve` →
        `seqapplyreg -framing=max`) so panels that share little or no star
        overlap still align; the stack uses additive + overlap normalization
        with `-maximize` to emit the full mosaic canvas and an optional
        feather across the seams. Each panel master is already background-
        extracted, so no gradient pass runs on the assembled mosaic.
        """
        process_dir = self.root_dir / "process"
        master_path = process_dir / f"master_{filter_name}.fit"

        def panel_master(pp: Path) -> Path | None:
            # Prefer the per-panel SPCC-calibrated channel if present (broadband
            # R/G/B); fall back to the raw master (always for luminance, and for
            # any panel whose SPCC was skipped/failed).
            spcc = pp / f"master_{filter_name}_spcc.fit"
            raw = pp / f"master_{filter_name}.fit"
            if spcc.exists():
                return spcc
            return raw if raw.exists() else None

        sources = [p for p in map(panel_master, panel_procs) if p is not None]
        if not sources:
            self.siril.log(
                f"No panel masters for {filter_name}; skipping combine"
            )
            return

        # A filter present on a single panel has no mosaic to assemble —
        # adopt that panel's master directly so compose() still finds it.
        if len(sources) == 1:
            self._step(
                f"Mosaic {filter_name}: only one panel; adopting its master"
            )
            if self.history.is_done(
                process_dir,
                "combine_panels",
                detail=filter_name,
                outputs=[master_path],
                inputs=sources,
            ):
                self.siril.log("Step already done, skipping")
                return
            shutil.copy2(sources[0], master_path)
            self.history.mark_done(
                process_dir, "combine_panels", detail=filter_name
            )
            return

        if self.history.is_done(
            process_dir,
            "combine_panels",
            detail=filter_name,
            outputs=[master_path],
            inputs=sources,
        ):
            self.siril.log(
                f"Mosaic master for {filter_name} up to date, skipping"
            )
            return

        self._step(
            f"Mosaic {filter_name}: assembling {len(sources)} panels"
        )

        # Rebuild the pool dir from scratch so a stale sequence from a prior
        # run can't leak in. Panel-prefixed names keep frames ordered and
        # unique; `convert` then indexes them into one sequence.
        mosaic_dir = process_dir / f"mosaic_{filter_name}"
        if mosaic_dir.exists():
            shutil.rmtree(mosaic_dir)
        mosaic_dir.mkdir(parents=True, exist_ok=True)
        for i, src in enumerate(sources):
            (mosaic_dir / f"panel{i + 1:02d}_{filter_name}.fit").symlink_to(
                src
            )

        seq = f"mosaic_{filter_name}"
        with core.cwd_at(self.siril, mosaic_dir):
            self.siril.cmd("convert", seq, "-out=../")
        with core.cwd_at(self.siril, process_dir):
            # Astrometric registration onto the union canvas. Each panel
            # master already carries a WCS from its own stack's platesolve,
            # so a plain seqplatesolve reuses those solutions (and only solves
            # any that are missing) — safer than forcing a blind re-solve of a
            # faint narrowband master. If a panel ever lacks WCS, re-run with
            # `-force -nocache` here.
            self.siril.cmd("seqplatesolve", seq)
            self.siril.cmd(
                "seqapplyreg", seq, "-framing=max", "-interp=lanczos4"
            )
            args = [
                "stack",
                f"r_{seq}",
                "rej",
                "none",
                "-norm=addscale",
                "-output_norm",
                "-overlap_norm",
                "-maximize",
                "-filter-included",
                "-32b",
            ]
            if MOSAIC_FEATHER_PX > 0:
                args.append(f"-feather={MOSAIC_FEATHER_PX}")
            args.append(f"-out=master_{filter_name}")
            self.siril.cmd(*args)
            # Re-solve the assembled mosaic so compose()/SPCC have a WCS on
            # the full canvas rather than one inherited from a single panel.
            self.open_image(master_path.name)
            self.siril.cmd("platesolve")
            self.siril.cmd("save", f"master_{filter_name}")
        self.history.mark_done(
            process_dir, "combine_panels", detail=filter_name
        )


# --- GUI --------------------------------------------------------------------


class MosaicInterface(QWidget):
    """Panel picker + processing options for a mosaic project."""

    def __init__(
        self, pipeline: MosaicPipeline, panels: list[Path]
    ) -> None:
        super().__init__()
        self.setWindowTitle("Astro-Hibou mosaic")
        self.setWindowFlags(
            self.windowFlags() | Qt.WindowType.WindowStaysOnTopHint
        )
        self.pipeline = pipeline
        self.panels = panels
        self.panel_labels = {panel: panel_label(panel) for panel in panels}

        self.panel_checks: dict[Path, QCheckBox] = {}
        self.option_checks: dict[str, QCheckBox] = {}
        self.mode_full: QRadioButton | None = None
        self.mode_partial: QRadioButton | None = None
        self.options_layout: QVBoxLayout | None = None
        self.options_group: QGroupBox | None = None
        self.deconv_strength_spin: QDoubleSpinBox | None = None
        self.denoise_strength_spin: QDoubleSpinBox | None = None
        self.common_name_fr_edit: QLineEdit | None = None
        self.common_name_en_edit: QLineEdit | None = None
        self.ha_weight_spin: QDoubleSpinBox | None = None
        self.reset_history_btn: QPushButton | None = None
        self.proceed_btn: QPushButton | None = None
        self.cancel_btn: QPushButton | None = None
        self.status_label: QLabel | None = None
        self.progress_bar: QProgressBar | None = None

        self._thread: QThread | None = None
        self._worker: core.PipelineWorker | None = None

        self._setup_ui()
        self._update_option_section()
        self.adjustSize()
        self.setFixedSize(self.size())

    # --- layout -------------------------------------------------------

    def _setup_ui(self) -> None:
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(10, 10, 10, 10)

        panel_group = QGroupBox("Panels")
        panel_layout = QVBoxLayout()
        for panel in self.panels:
            cb = QCheckBox(self.panel_labels[panel])
            cb.setChecked(True)
            cb.toggled.connect(self._on_panel_toggled)
            self.panel_checks[panel] = cb
            panel_layout.addWidget(cb)
        panel_group.setLayout(panel_layout)
        main_layout.addWidget(panel_group)

        mode_group = QGroupBox("Mode Selection")
        mode_layout = QVBoxLayout()
        self.mode_full = QRadioButton("Full")
        self.mode_partial = QRadioButton("Partial")
        self.mode_full.setToolTip(
            "Build panels, assemble the mosaic, recombine, then deconvolve + "
            "denoise to the linear pre-stretch checkpoint."
        )
        self.mode_partial.setToolTip(
            "Build panels, assemble the mosaic, and recombine; stop on the "
            "linear recombined master, before deconv/denoise."
        )
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

        processing_group = QGroupBox("Processing")
        proc_layout = QVBoxLayout()
        proc_form = QFormLayout()
        self.ha_weight_spin = QDoubleSpinBox()
        self.ha_weight_spin.setRange(0.0, 1.0)
        self.ha_weight_spin.setSingleStep(0.05)
        self.ha_weight_spin.setDecimals(2)
        self.ha_weight_spin.setValue(0.3)
        proc_form.addRow("Ha blend weight:", self.ha_weight_spin)
        self.deconv_strength_spin = QDoubleSpinBox()
        self.deconv_strength_spin.setRange(0.0, 1.0)
        self.deconv_strength_spin.setSingleStep(0.05)
        self.deconv_strength_spin.setDecimals(2)
        self.deconv_strength_spin.setValue(1.0)
        self.deconv_strength_spin.setToolTip(
            "Parallax sharpen_alpha: blend fraction with the unsharpened\n"
            "input (out = in + a*(sharpened - in)). 1.0 = full sharpening."
        )
        proc_form.addRow("Deconv blend (1.0 = full):", self.deconv_strength_spin)
        self.denoise_strength_spin = QDoubleSpinBox()
        self.denoise_strength_spin.setRange(0.0, 1.0)
        self.denoise_strength_spin.setSingleStep(0.05)
        self.denoise_strength_spin.setDecimals(2)
        self.denoise_strength_spin.setValue(0.85)
        self.denoise_strength_spin.setToolTip(
            "Prism modulation: blend fraction with the NOISY input\n"
            "(out = m*denoised + (1-m)*original). 0.5 keeps half the noise."
        )
        proc_form.addRow("Denoise blend (1.0 = full):", self.denoise_strength_spin)
        self.common_name_fr_edit = QLineEdit()
        self.common_name_fr_edit.setPlaceholderText(
            "Nébuleuse de la Lagune…"
        )
        proc_form.addRow("Nom commun (FR):", self.common_name_fr_edit)
        self.common_name_en_edit = QLineEdit()
        self.common_name_en_edit.setPlaceholderText("Lagoon Nebula…")
        proc_form.addRow("Common name (EN):", self.common_name_en_edit)
        self._prepopulate_common_names()
        proc_layout.addLayout(proc_form)
        self.reset_history_btn = QPushButton("Reset history")
        self.reset_history_btn.clicked.connect(self._on_reset_history)
        proc_layout.addWidget(self.reset_history_btn)
        processing_group.setLayout(proc_layout)
        main_layout.addWidget(processing_group)

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

        # A recombination is offered when every selected panel carries the
        # filters it needs — otherwise the mosaic would have holes where a
        # panel lacks that channel.
        modes = core.available_shooting_modes(self._common_filter_codes())
        for option in core.options_for_modes(modes):
            cb = QCheckBox(option)
            self.option_checks[option] = cb
            self.options_layout.addWidget(cb)

        self.adjustSize()
        self.setFixedSize(self.size())

    # --- selection helpers --------------------------------------------

    def _selected_panels(self) -> list[Path]:
        return [p for p, cb in self.panel_checks.items() if cb.isChecked()]

    def _common_filter_codes(self) -> set[str]:
        """Filter codes shared by ALL selected panels (intersection), so a
        recombination is only offered when no panel would be missing."""
        selected = self._selected_panels()
        if not selected:
            return set()
        common: set[str] | None = None
        for panel in selected:
            codes = panel_filter_codes(panel)
            common = codes if common is None else (common & codes)
        return common or set()

    def _selected_mode(self) -> str:
        assert self.mode_full is not None
        return "full" if self.mode_full.isChecked() else "partial"

    def _selected_options(self) -> list[str]:
        return [
            opt for opt, cb in self.option_checks.items() if cb.isChecked()
        ]

    def _is_valid(self) -> tuple[bool, str]:
        if not self._selected_panels():
            return False, "At least one panel must be selected"
        if self.option_checks and not any(
            cb.isChecked() for cb in self.option_checks.values()
        ):
            return False, "At least one option must be selected"
        return True, ""

    # --- signal handlers ---------------------------------------------

    def _on_panel_toggled(self, checked: bool) -> None:
        if not self._selected_panels():
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

        panels = self._selected_panels()
        mode = self._selected_mode()
        options = self._selected_options() or ["LRGB"]

        assert self.deconv_strength_spin is not None
        assert self.denoise_strength_spin is not None
        assert self.ha_weight_spin is not None
        assert self.common_name_fr_edit is not None
        assert self.common_name_en_edit is not None

        p = self.pipeline
        p.deconv_strength = self.deconv_strength_spin.value()
        p.denoise_strength = self.denoise_strength_spin.value()
        p.ha_weight = self.ha_weight_spin.value()
        p.common_name_fr = self.common_name_fr_edit.text().strip()
        p.common_name_en = self.common_name_en_edit.text().strip()
        # Persist the nicknames now (not only at the end-of-run sidecar) so a
        # crash or early stop doesn't force re-typing them next launch.
        core.save_common_names(p.root_dir, p.common_name_fr, p.common_name_en)
        # A mosaic's crop cannot be guessed reliably, so always pause after
        # recombination for a hand crop before deconvolution.
        p.manual_crop = True

        def run_fn() -> dict:
            p.process_mosaic(panels, mode, options)
            return {}

        self._set_running(True, "Starting…")
        self._start_worker(run_fn)

    def _start_worker(self, run_fn) -> None:
        self._thread = QThread(self)
        self._worker = core.PipelineWorker(self.pipeline, run_fn)
        self._worker.moveToThread(self._thread)
        self._thread.started.connect(self._worker.run)
        self._worker.progress.connect(self._on_worker_progress)
        self._worker.paused.connect(self._on_worker_paused)
        self._worker.finished.connect(self._on_worker_finished)
        self._worker.failed.connect(self._on_worker_failed)
        self._worker.finished.connect(self._thread.quit)
        self._worker.failed.connect(self._thread.quit)
        self._thread.finished.connect(self._worker.deleteLater)
        self._thread.finished.connect(self._thread.deleteLater)
        self._thread.start()

    def _on_worker_paused(self, message: str) -> None:
        # The worker thread is blocked; prompt for the manual crop, then
        # release it. The recombined master is already loaded in Siril.
        worker = self._worker
        if worker is None:
            return
        if self.status_label is not None:
            self.status_label.setText("Waiting: crop the image in Siril…")
        QMessageBox.information(self, "Crop the mosaic", message)
        worker.resume()

    def _prepopulate_common_names(self) -> None:
        assert self.common_name_fr_edit is not None
        assert self.common_name_en_edit is not None
        root = self.pipeline.root_dir
        # Per-target cache first (written at run start, survives crashes);
        # fall back to scanning end-of-run sidecars for older targets.
        fr, en = core.load_common_names(root)
        if fr or en:
            if fr:
                self.common_name_fr_edit.setText(fr)
            if en:
                self.common_name_en_edit.setText(en)
            return
        candidates = list(root.glob("process/*.meta.yaml"))
        candidates.sort(key=lambda p: p.stat().st_mtime, reverse=True)
        for sidecar in candidates:
            try:
                data = core.yaml.safe_load(sidecar.read_text(encoding="utf-8"))
            except (OSError, core.yaml.YAMLError):
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
            "every step from scratch (panels included).",
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
        self._set_finished()
        QMessageBox.information(
            self, "Mosaic complete", "Mosaic processing finished."
        )

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
        self.progress_bar.setRange(0, 0 if running else 100)
        if not running:
            self.progress_bar.setValue(0)
            self._thread = None
            self._worker = None

    def _set_finished(self) -> None:
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


def main() -> None:
    siril = sirilpy.SirilInterface()
    try:
        siril.connect()
    except sirilpy.SirilConnectionError as e:
        print(f"Failed to connect to Siril: {e}", file=sys.stderr)
        return

    try:
        siril.cmd("requires", core.SIRIL_MIN_VERSION)
    except CommandError as e:
        print(f"Siril version requirement not met: {e}", file=sys.stderr)
        siril.disconnect()
        return

    root_dir = core.siril_cwd(siril)
    panels = discover_panels(root_dir)
    siril.log(f"Found {len(panels)} panels: {[p.name for p in panels]}")
    if not panels:
        print(
            f"No 'Panel N' subfolders found in {root_dir}. Launch this from "
            "the mosaic project root that holds the panel folders.",
            file=sys.stderr,
        )
        siril.disconnect()
        return

    pipeline = MosaicPipeline(siril, root_dir)

    try:
        qapp = QApplication.instance() or QApplication(sys.argv)
        qapp.setApplicationName("Astro-Hibou mosaic")
        qapp.setStyle("Fusion")
        window = MosaicInterface(pipeline, panels)
        window.show()
        qapp.exec()
    except CommandError as e:
        print(f"Error running command: {e}", file=sys.stderr)
    except SirilError as e:
        print(f"Error initializing script: {e}", file=sys.stderr)
    finally:
        try:
            core.siril_cd(siril, root_dir)
        finally:
            siril.disconnect()


if __name__ == "__main__":
    main()

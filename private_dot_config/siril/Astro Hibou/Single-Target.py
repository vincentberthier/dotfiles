#!/usr/bin/env python3
# debug-statement-audit: ignore — the four print() calls in main() are the
# CLI entrypoint's only way to surface fatal errors to stderr when this script
# is invoked outside the Siril GUI; they are intentional, not debug cruft.
"""Astro-Hibou — single-target processing launcher.

The GUI here is a thin front-end over the shared processing library
(astro_hibou_core.py, imported as `core`). It calibrates, stacks, recombines
(LRGB+SPCC / SHO / OHS / …), and — in full mode — continues into
deconv/denoise/star-removal to the linear pre-stretch checkpoint
(process/_STRETCH_ME/). Everything past that hand-off is manual, except the
optional interactive VeraLux continuation which lives in its own launcher,
VeraLux-Continuation.py.

Multi-panel mosaics are handled by Mosaic.py.
"""

import sys
from pathlib import Path

# Make the sibling core library importable regardless of Siril's working
# directory (Siril sets cwd to the data folder, not the script folder).
sys.path.insert(0, str(Path(__file__).resolve().parent / "lib"))

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


class Interface(QWidget):
    """Astro-Hibou launcher; delegates the actual work to a core.Pipeline."""

    def __init__(
        self, pipeline: core.Pipeline, days_list: list[str]
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
        self._worker: core.PipelineWorker | None = None

        self._setup_ui()
        self._update_option_section()
        core.fit_to_content(self)

    # --- layout -------------------------------------------------------

    def _setup_ui(self) -> None:
        outer = QVBoxLayout(self)
        outer.setContentsMargins(10, 10, 10, 10)
        # Every group goes inside a scroll area; the status row and the buttons
        # stay pinned outside it so Proceed/Cancel are always reachable however
        # many recombinations the selected days offer.
        content = QWidget()
        main_layout = QVBoxLayout(content)
        main_layout.setContentsMargins(0, 0, 0, 0)

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
        self.mode_full.setToolTip(
            "Calibrate, stack, recombine (LRGB+SPCC / SHO / OHS / ...), "
            "then deconvolve + denoise to the linear pre-stretch checkpoint."
        )
        self.mode_partial.setToolTip(
            "Calibrate, stack, and recombine (LRGB+SPCC / SHO / OHS / ...); "
            "stop on the linear recombined master, before deconv/denoise."
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
        proc_form = QFormLayout()
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
        self.denoise_strength_spin.setValue(0.90)
        self.denoise_strength_spin.setToolTip(
            "Prism modulation: blend fraction with the NOISY input\n"
            "(out = m*denoised + (1-m)*original). 0.5 keeps half the noise.\n"
            "Leave at 1.0 and derive the stretch from the PRE-denoise frame;\n"
            "lowering it only keeps grain to hide Prism's residual."
        )
        proc_form.addRow("Denoise blend (1.0 = full):", self.denoise_strength_spin)
        # Common names — stamped into the YAML sidecar and consumed
        # downstream by the GIMP legend plug-in and the JPG metadata
        # injector. Pre-filled from any existing sidecar in the target.
        self.common_name_fr_edit = QLineEdit()
        self.common_name_fr_edit.setPlaceholderText(
            "Nébuleuse Trifide, Galaxie du Sombrero…"
        )
        proc_form.addRow("Nom commun (FR):", self.common_name_fr_edit)
        self.common_name_en_edit = QLineEdit()
        self.common_name_en_edit.setPlaceholderText(
            "Trifid Nebula, Sombrero Galaxy…"
        )
        proc_form.addRow("Common name (EN):", self.common_name_en_edit)
        self._prepopulate_common_names()
        proc_layout.addLayout(proc_form)
        self.reset_history_btn = QPushButton("Reset history")
        self.reset_history_btn.clicked.connect(self._on_reset_history)
        proc_layout.addWidget(self.reset_history_btn)
        processing_group.setLayout(proc_layout)
        main_layout.addWidget(processing_group)
        main_layout.addStretch(1)
        outer.addWidget(core.scrollable(content), 1)

        # Status row reserved at construction time so the window doesn't
        # change size when work starts.
        self.status_label = QLabel(" ")
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.progress_bar.setTextVisible(False)
        outer.addWidget(self.status_label)
        outer.addWidget(self.progress_bar)

        button_row = QHBoxLayout()
        button_row.addStretch(1)
        self.proceed_btn = QPushButton("Proceed")
        self.cancel_btn = QPushButton("Cancel")
        self.proceed_btn.clicked.connect(self._on_proceed)
        self.cancel_btn.clicked.connect(self._on_cancel_clicked)
        button_row.addWidget(self.proceed_btn)
        button_row.addWidget(self.cancel_btn)
        outer.addLayout(button_row)

    def _update_option_section(self) -> None:
        assert self.options_layout is not None
        while self.options_layout.count():
            item = self.options_layout.takeAt(0)
            w = item.widget()
            if w is not None:
                w.setParent(None)
                w.deleteLater()
        self.option_checks.clear()

        modes = self._available_shooting_modes()
        self.pipeline.siril.log(f"available shooting modes: {modes}")

        for option in core.options_for_modes(modes):
            cb = QCheckBox(option)
            self.option_checks[option] = cb
            self.options_layout.addWidget(cb)

        core.fit_to_content(self)

    # --- selection helpers --------------------------------------------

    def _available_shooting_modes(self) -> list[core.ShootingMode]:
        filters = core.filters_from_day_labels(self._selected_days_labels())
        return core.available_shooting_modes(filters)

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

        assert self.deconv_strength_spin is not None
        assert self.denoise_strength_spin is not None
        assert self.cluster_mode_check is not None
        assert self.ha_weight_spin is not None
        assert self.common_name_fr_edit is not None
        assert self.common_name_en_edit is not None

        # Configure the pipeline before the worker thread starts. These are
        # plain attributes, set once here and only read on the worker thread.
        p = self.pipeline
        p.deconv_strength = self.deconv_strength_spin.value()
        p.denoise_strength = self.denoise_strength_spin.value()
        p.cluster_mode = self.cluster_mode_check.isChecked()
        p.ha_weight = self.ha_weight_spin.value()
        p.common_name_fr = self.common_name_fr_edit.text().strip()
        p.common_name_en = self.common_name_en_edit.text().strip()
        # Persist the nicknames now (not only at the end-of-run sidecar) so a
        # crash or early stop doesn't force re-typing them next launch.
        core.save_common_names(p.root_dir, p.common_name_fr, p.common_name_en)

        def run_fn() -> dict:
            p.process_target(days, mode, options)
            try:
                return p.collect_stats(days, options)
            except Exception as e:  # stats are best-effort
                p.siril.log(f"Stats collection failed: {e}")
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
        candidates += list(root.glob("*/process/*.meta.yaml"))
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

    def _on_worker_paused(self, message: str) -> None:
        # The worker thread is blocked on a manual step; prompt, then release.
        worker = self._worker
        if worker is None:
            return
        if self.status_label is not None:
            self.status_label.setText("Waiting: crop the image in Siril…")
        QMessageBox.information(self, "Crop the image", message)
        worker.resume()

    def _on_worker_finished(self, stats: dict) -> None:
        # After a successful run the pipeline cache has fully populated,
        # so re-clicking Proceed would be a no-op. Lock the inputs and
        # swap Cancel for Close.
        self._set_finished()
        core.StatsDialog(stats, parent=self).exec()

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

    available_days = core.get_available_days(siril)
    siril.log(f"Found days: {available_days}")
    days = core.label_days(siril, available_days, root_dir)

    pipeline = core.Pipeline(siril, root_dir)

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
            core.siril_cd(siril, root_dir)
        finally:
            siril.disconnect()


if __name__ == "__main__":
    main()

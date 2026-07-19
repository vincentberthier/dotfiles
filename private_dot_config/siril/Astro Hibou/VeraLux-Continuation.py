#!/usr/bin/env python3
# debug-statement-audit: ignore — the print() calls in main() are the CLI
# entrypoint's only way to surface fatal errors to stderr when this script is
# invoked outside the Siril GUI; they are intentional, not debug cruft.
"""Astro-Hibou — interactive VeraLux continuation launcher.

The main pipeline (astro_hibou.py) and the mosaic pipeline
(astro_hibou_mosaic.py) both stop at the linear pre-stretch checkpoint
(process/_STRETCH_ME/). This launcher continues past that point, building a
finished *reference* image with the real VeraLux GUI tools — it opens each
tool on the loaded image and blocks until you close its window, then saves and
moves to the next stage.

Point Siril's working directory at a target (or mosaic) that has already been
run through the pipeline in *full* mode. This launcher scans its process/
directory for the recombined images it left behind and offers to continue any
of them. Chain order (each stage skippable, all History-cached):

    Silentium (linear denoise) → HyperMetric Stretch → Revela → Curves →
    Vectra → StarComposer (recombine stars)

In cluster mode the point-source-incompatible stages (Revela, StarComposer)
are skipped automatically. All Siril primitives are the shared library,
astro_hibou_core.
"""

import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "lib"))

import sirilpy  # noqa: E402
from sirilpy import CommandError, SirilError  # noqa: E402
from PyQt6.QtCore import QSettings, Qt, QThread  # noqa: E402
from PyQt6.QtWidgets import (  # noqa: E402
    QApplication,
    QCheckBox,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

import astro_hibou_core as core  # noqa: E402

# Recombination image stems the pipeline can produce (core.Pipeline.process
# file_map values). Used to detect which finished images live in a process/
# directory.
KNOWN_IMAGES = (
    "lrgb",
    "rgb",
    "halrgb_r",
    "halrgb_l",
    "sho",
    "hoo",
    "ohs",
    "hso",
    "forax",
)


# --- discovery of continuable images ----------------------------------------


class Continuable:
    """One recombined image ready for the VeraLux continuation."""

    def __init__(self, process_dir: Path, image: str, cluster: bool) -> None:
        self.process_dir = process_dir
        self.image = image
        self.cluster = cluster

    def label(self, show_dir: bool) -> str:
        tag = core.mode_label(self.image)
        if self.cluster:
            tag += " (cluster)"
        if show_dir:
            tag += f"  —  {self.process_dir.parent.name}/process"
        return tag


def _process_dirs(root: Path) -> list[Path]:
    """Candidate process/ directories: the target root's own, plus one level
    down (single-night-in-subdir and mosaic-panel layouts)."""
    dirs: list[Path] = []
    if (root / "process").is_dir():
        dirs.append(root / "process")
    for sub in sorted(root.iterdir()):
        if sub.is_dir() and (sub / "process").is_dir():
            dirs.append(sub / "process")
    return dirs


def discover_continuables(root: Path) -> list[Continuable]:
    """Every recombined image under `root` that the pipeline left in a state
    the VeraLux continuation can pick up.

    Cluster images are detected by their linear checkpoints
    (`<image>_cluster_prestretch.fit` / `_cluster_deconvolved.fit`); regular
    images by their deconvolved frame or denoised starless.
    """
    found: list[Continuable] = []
    for process_dir in _process_dirs(root):
        for image in KNOWN_IMAGES:
            cluster_ready = (
                process_dir / f"{image}_cluster_prestretch.fit"
            ).exists() or (
                process_dir / f"{image}_cluster_deconvolved.fit"
            ).exists()
            regular_ready = (
                process_dir / f"starless_{image}_denoised.fit"
            ).exists() or (
                process_dir / f"{image}_deconvolved.fit"
            ).exists()
            if cluster_ready:
                found.append(Continuable(process_dir, image, cluster=True))
            elif regular_ready:
                found.append(Continuable(process_dir, image, cluster=False))
    return found


# --- VeraLux pipeline -------------------------------------------------------


class VeraLuxPipeline(core.Pipeline):
    """Adds the interactive VeraLux continuation to the shared Pipeline. The
    per-stage flags below are set from the GUI before the worker starts."""

    def __init__(self, siril, root_dir: Path) -> None:
        super().__init__(siril, root_dir)
        self.vlx_silentium: bool = True
        self.vlx_stretch: bool = True
        self.vlx_revela: bool = True
        self.vlx_curves: bool = True
        self.vlx_vectra: bool = True
        self.vlx_starcompose: bool = True

    def continue_veralux(self, image: str) -> None:
        """Dispatch to the regular or cluster continuation for one image,
        honouring the current cluster_mode flag."""
        if self.cluster_mode:
            self._veraluxify_cluster(image)
        else:
            self.veraluxify(image)

    @staticmethod
    def _pin_hypermetric_mode() -> None:
        """Open HyperMetric in **Scientific (Preserve)**, not Ready-to-Use.

        HyperMetric remembers its processing mode in
        `QSettings("VeraLux", "HyperMetricStretch")` -> `mode_ready`, which
        defaults to **True** (Ready-to-Use). That mode is the one path that
        cannot work on a Prism-denoised starless, and the launcher was handing
        it to the operator every time.

        Ready-to-Use ends in `adaptive_output_scaling()`, which sets
        `global_floor = max(min_L, median_L - 2.7*sigma)` and expands to the
        99th percentile. Prism deleted the noise that used to define `min_L`,
        so on a denoised starless the frame's minimum sits only 8.4e-05 under
        the sky instead of 1.01e-03: a 653x expansion instead of 373x, after
        which the MTF *lifts* the background 2.4x rather than compressing it.
        Measured 64-px background chroma structure: 0.00361 denoised vs
        0.00025 un-denoised — 14x. That is the green/magenta continents.

        No slider in that mode rescues it. `Log D` is inert (the output
        background is bit-identical at log D 0.00 and 2.00, because
        `adaptive_output_scaling` re-derives the tone map afterwards) and so is
        `Protect b`. Only `Target Bg` moves it, linearly (0.15 -> 0.05 takes
        chroma 0.00361 -> 0.00138) — i.e. it does not remove the residual, it
        just crushes the sky until the residual is too dark to see, taking the
        faint outer halo with it.

        Scientific (Preserve) skips `adaptive_output_scaling` entirely, so
        `log D` alone sets the stretch: chroma 0.00022 at the *same* background
        level, 16x cleaner. It rebuilds no contrast, so the result is flat —
        finish with Curves / Revela, or stretch by hand.

        This is a *default*, not a lock: the radio button is still there.
        """
        s = QSettings("VeraLux", "HyperMetricStretch")
        s.setValue("mode_ready", False)
        s.sync()

    def _veralux_stage(
        self, image: str, stage: str, script: str, src: Path
    ) -> Path:
        """Launch one in-place VeraLux GUI tool on `src`, block until the
        user closes its window, then save Siril's (now-modified) image to a
        per-stage output. Returns the stage output path.
        """
        cwd = self.cwd()
        out = cwd / f"veralux_{image}_{stage}.fit"
        if self.history.is_done(
            cwd, f"veralux_{stage}", detail=image,
            outputs=[out], inputs=[src],
        ):
            self.siril.log(f"VeraLux {stage}: already done, skipping")
            return out
        if stage == "stretch":
            self._pin_hypermetric_mode()
        self._step(
            f"VeraLux {stage}: opening {script} on {src.name} - "
            "process the image, then CLOSE the window to resume"
        )
        self.siril.cmd("load", f'"{src.stem}"')
        # Blocks until the VeraLux window is closed (same pyscript mechanism
        # as the GraXpert/StarNet calls). The tool writes its result back
        # into Siril's loaded image; we persist that under the stage name.
        self.siril.cmd("pyscript", script)
        self.siril.cmd("save", out.stem)
        self.history.mark_done(cwd, f"veralux_{stage}", detail=image)
        return out

    def veraluxify(self, image: str) -> None:
        """Optional interactive continuation past the linear checkpoint:
        run the enabled VeraLux GUI tools in chain order, each launched and
        waited-on, to build a finished *reference* image. Order: Silentium
        (linear denoise) -> HyperMetric Stretch -> Revela -> Curves ->
        Vectra -> StarComposer. Every stage is optional.
        """
        cwd = self.cwd()
        if self.vlx_silentium:
            # Silentium owns denoise for the reference branch, so it must
            # start from a starless that has NOT been Prism-denoised, or the
            # pixels get denoised twice. The main order denoises before star
            # removal, so no such starless exists yet — build one with a
            # dedicated star-removal pass on the deconv-only frame. The
            # Prism-denoised _STRETCH_ME checkpoint is left as a parallel
            # result.
            self.remove_stars(image, f"{image}_deconvolved")
            src = cwd / f"starless_{image}_deconvolved.fit"
        else:
            # No VeraLux denoise: start from the Prism-denoised starless so
            # the data is denoised before the stretch.
            src = cwd / f"starless_{image}_denoised.fit"
        if not src.exists():
            self.siril.log(
                f"VeraLux: {src.name} missing; nothing to continue from"
            )
            return
        scripts = {
            "silentium": "VeraLux_Silentium.py",
            "stretch": "VeraLux_HyperMetric_Stretch.py",
            "revela": "VeraLux_Revela.py",
            "curves": "VeraLux_Curves.py",
            "vectra": "VeraLux_Vectra.py",
        }
        chain = [
            ("silentium", self.vlx_silentium),
            ("stretch", self.vlx_stretch),
            ("revela", self.vlx_revela),
            ("curves", self.vlx_curves),
            ("vectra", self.vlx_vectra),
        ]
        current = src
        for stage, enabled in chain:
            if not enabled:
                continue
            current = self._veralux_stage(image, stage, scripts[stage], current)
        if self.vlx_starcompose:
            self._veralux_starcompose(image, current)

    def _veralux_starcompose(self, image: str, stretched: Path) -> None:
        """Launch StarComposer to screen the linear star mask back onto the
        stretched starless. StarComposer uses its own file pickers and saves
        to VeraLux_StarComposer_result.fit; we move that to a clearly-named
        REFERENCE image and tell the user which two files to pick.
        """
        cwd = self.cwd()
        ref = cwd / f"{self._stretch_me_base(image)}_REFERENCE.fit"
        result = cwd / "VeraLux_StarComposer_result.fit"
        if self.history.is_done(
            cwd, "veralux_starcompose", detail=image,
            outputs=[ref], inputs=[stretched],
        ):
            self.siril.log("VeraLux StarComposer: already done, skipping")
            return
        # The checkpoint carries the *pipeline* run's date, which is not this
        # launcher's; resolve it by glob rather than rebuilding the name.
        starmask = self.find_stretch_me(image, "STARS.fit")
        if starmask is None:
            self.siril.log(
                f"VeraLux StarComposer: no STARS mask found in "
                f"{self._stretch_me_dir().name}/ for {core.mode_label(image)}; "
                "skipping"
            )
            return
        self._step(
            "VeraLux StarComposer: opening - pick STARLESS = "
            f"{stretched.name} (stretched) and STARS = {starmask.name} "
            "(linear), then CLOSE the window to resume"
        )
        # Detect a fresh result by mtime rather than deleting the old one.
        before = result.stat().st_mtime if result.exists() else -1.0
        self.siril.cmd("pyscript", "VeraLux_StarComposer.py")
        if result.exists() and result.stat().st_mtime > before:
            shutil.move(str(result), str(ref))
            self.siril.log(f"VeraLux: reference image -> {ref.name}")
            self.history.mark_done(cwd, "veralux_starcompose", detail=image)
        else:
            self.siril.log(
                "VeraLux StarComposer: no fresh result produced "
                "(skipped or saved elsewhere)"
            )

    def _veraluxify_cluster(self, image: str) -> None:
        """Cluster-path VeraLux continuation. Branches from the LINEAR
        prestretch checkpoint (post stellar-deconv), since Silentium needs
        linear input and HyperMetric *is* the stretch. Revela (luminance
        structure) and StarComposer (needs the starless/starmask
        decomposition) don't fit point-source fields, so they're excluded.
        The normal autostretch `<image>_cluster.fit` is left intact as the
        baseline; this writes a VeraLux reference alongside it.
        """
        cwd = self.cwd()
        if self.vlx_silentium:
            # Silentium is the sole denoiser here, so branch from the
            # deconv-only linear checkpoint (before Prism denoise) to avoid
            # denoising twice.
            src = cwd / f"{image}_cluster_deconvolved.fit"
        else:
            # No Silentium: start from the Prism-denoised linear checkpoint.
            src = cwd / f"{image}_cluster_prestretch.fit"
        if not src.exists():
            self.siril.log(
                f"VeraLux: {src.name} missing; nothing to continue from"
            )
            return
        scripts = {
            "silentium": "VeraLux_Silentium.py",
            "stretch": "VeraLux_HyperMetric_Stretch.py",
            "curves": "VeraLux_Curves.py",
            "vectra": "VeraLux_Vectra.py",
        }
        chain = [
            ("silentium", self.vlx_silentium),
            ("stretch", self.vlx_stretch),
            ("curves", self.vlx_curves),
            ("vectra", self.vlx_vectra),
        ]
        current = src
        for stage, enabled in chain:
            if not enabled:
                continue
            current = self._veralux_stage(
                image, f"cluster_{stage}", scripts[stage], current
            )
        if current != src:
            ref = cwd / f"{self._stretch_me_base(image)}_REFERENCE.fit"
            shutil.copy2(current, ref)
            self.siril.log(f"VeraLux: cluster reference -> {ref.name}")


# --- GUI --------------------------------------------------------------------


class VeraLuxInterface(QWidget):
    """Pick the recombined image(s) to continue and which VeraLux stages to
    run, then drive the interactive chain."""

    STAGES = (
        ("silentium", "Silentium (denoise)"),
        ("stretch", "HyperMetric Stretch"),
        ("revela", "Revela (structure)"),
        ("curves", "Curves"),
        ("vectra", "Vectra (color)"),
        ("starcompose", "StarComposer (recombine stars)"),
    )

    def __init__(
        self, pipeline: VeraLuxPipeline, continuables: list[Continuable]
    ) -> None:
        super().__init__()
        self.setWindowTitle("Astro-Hibou VeraLux")
        self.setWindowFlags(
            self.windowFlags() | Qt.WindowType.WindowStaysOnTopHint
        )
        self.pipeline = pipeline
        self.continuables = continuables
        # Show the process-dir suffix only when there is ambiguity.
        self._show_dir = len({c.process_dir for c in continuables}) > 1

        self.image_checks: dict[int, QCheckBox] = {}
        self.stage_checks: dict[str, QCheckBox] = {}
        self.reset_history_btn: QPushButton | None = None
        self.proceed_btn: QPushButton | None = None
        self.cancel_btn: QPushButton | None = None
        self.status_label: QLabel | None = None
        self.progress_bar: QProgressBar | None = None

        self._thread: QThread | None = None
        self._worker: core.PipelineWorker | None = None

        self._setup_ui()
        core.fit_to_content(self)

    def _setup_ui(self) -> None:
        outer = QVBoxLayout(self)
        outer.setContentsMargins(10, 10, 10, 10)
        # The continuable-image list grows with the number of recombinations
        # found on disk, so it scrolls; the buttons stay pinned.
        content = QWidget()
        main_layout = QVBoxLayout(content)
        main_layout.setContentsMargins(0, 0, 0, 0)

        img_group = QGroupBox("Recombined images to continue")
        img_layout = QVBoxLayout()
        for i, cont in enumerate(self.continuables):
            cb = QCheckBox(cont.label(self._show_dir))
            cb.setChecked(i == 0)
            self.image_checks[i] = cb
            img_layout.addWidget(cb)
        img_group.setLayout(img_layout)
        main_layout.addWidget(img_group)

        stage_group = QGroupBox("VeraLux stages")
        stage_layout = QVBoxLayout()
        stage_layout.addWidget(
            QLabel(
                "Each opens its GUI; close the window to move on.\n"
                "Revela and StarComposer are skipped for cluster images."
            )
        )
        for key, label in self.STAGES:
            cb = QCheckBox(label)
            cb.setChecked(True)
            self.stage_checks[key] = cb
            stage_layout.addWidget(cb)
        stage_group.setLayout(stage_layout)
        main_layout.addWidget(stage_group)

        self.reset_history_btn = QPushButton("Reset history")
        self.reset_history_btn.clicked.connect(self._on_reset_history)
        main_layout.addWidget(self.reset_history_btn)
        main_layout.addStretch(1)
        outer.addWidget(core.scrollable(content), 1)

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

    # --- selection helpers --------------------------------------------

    def _selected(self) -> list[Continuable]:
        return [
            self.continuables[i]
            for i, cb in self.image_checks.items()
            if cb.isChecked()
        ]

    def _is_valid(self) -> tuple[bool, str]:
        if not self._selected():
            return False, "Select at least one image to continue"
        if not any(cb.isChecked() for cb in self.stage_checks.values()):
            return False, "Select at least one VeraLux stage"
        return True, ""

    # --- signal handlers ---------------------------------------------

    def _on_proceed(self) -> None:
        if self._is_running():
            return
        valid, message = self._is_valid()
        if not valid:
            QMessageBox.warning(self, "Invalid Selection", message)
            return

        selected = self._selected()
        p = self.pipeline
        p.vlx_silentium = self.stage_checks["silentium"].isChecked()
        p.vlx_stretch = self.stage_checks["stretch"].isChecked()
        p.vlx_revela = self.stage_checks["revela"].isChecked()
        p.vlx_curves = self.stage_checks["curves"].isChecked()
        p.vlx_vectra = self.stage_checks["vectra"].isChecked()
        p.vlx_starcompose = self.stage_checks["starcompose"].isChecked()

        def run_fn() -> dict:
            for cont in selected:
                p.cluster_mode = cont.cluster
                with core.cwd_at(self.pipeline.siril, cont.process_dir):
                    p.continue_veralux(cont.image)
            return {}

        self._set_running(True, "Starting…")
        self._start_worker(run_fn)

    def _start_worker(self, run_fn) -> None:
        self._thread = QThread(self)
        self._worker = core.PipelineWorker(self.pipeline, run_fn)
        self._worker.moveToThread(self._thread)
        self._thread.started.connect(self._worker.run)
        self._worker.progress.connect(self._on_worker_progress)
        self._worker.finished.connect(self._on_worker_finished)
        self._worker.failed.connect(self._on_worker_failed)
        self._worker.finished.connect(self._thread.quit)
        self._worker.failed.connect(self._thread.quit)
        self._thread.finished.connect(self._worker.deleteLater)
        self._thread.finished.connect(self._thread.deleteLater)
        self._thread.start()

    def _on_reset_history(self) -> None:
        if self._is_running():
            return
        reply = QMessageBox.question(
            self,
            "Reset history",
            "Clear the cached step record? VeraLux stages will re-run from "
            "scratch on the next proceed.",
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
            self, "VeraLux complete", "VeraLux continuation finished."
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
    continuables = discover_continuables(root_dir)
    siril.log(
        "VeraLux continuables: "
        f"{[(c.image, c.cluster) for c in continuables]}"
    )
    if not continuables:
        print(
            f"No recombined images found under {root_dir}. Run the pipeline "
            "in full mode first (astro_hibou.py or astro_hibou_mosaic.py).",
            file=sys.stderr,
        )
        siril.disconnect()
        return

    pipeline = VeraLuxPipeline(siril, root_dir)

    try:
        qapp = QApplication.instance() or QApplication(sys.argv)
        qapp.setApplicationName("Astro-Hibou VeraLux")
        qapp.setStyle("Fusion")
        window = VeraLuxInterface(pipeline, continuables)
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

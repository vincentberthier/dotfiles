# VeraLux interactive integration into astro_hibou.py — implementation spec

Status: IMPLEMENTED (py_compile + ruff pass). Backup of pre-change script:
`astro_hibou.py.bak-veralux`. Two items to confirm on the first real Siril run —
see "Open/verify" at the bottom.

## Decisions (agreed with user, 2026-06-13)

- **Interactive, not headless.** Do NOT extract VeraLux pure cores. Launch the real
  VeraLux GUI scripts via `siril.cmd("pyscript", "VeraLux_X.py")`, which blocks until
  the user closes the window (same mechanism as the existing `GraXpert-AI.py` calls).
  No fork, no version guard, no wrapper math. Scripts auto-update with the Siril repo.
- **Default stop = pre-stretch checkpoint.** Always write a clearly-identified pair to
  `process/_STRETCH_ME/`:
  - `<target>_<MODE>_STARLESS.fit` (= `starless_<image>_denoised.fit`, denoised, linear)
  - `<target>_<MODE>_STARS.fit` (= `starmask_processing_<image>.fit`, linear starmask)
  - `README.txt` (one line: which file is which + that STARS is the linear starmask for
    recombination, STARLESS is denoised-linear ready to stretch).
    `<target>` = `root_dir.name`; `<MODE>` = `image.upper()` (LRGB/SHO/…).
- **Optional interactive continuation** (opt-in, default OFF — builds a _reference_
  finished image). Chain order, each individually skippable:
  1. Silentium (denoise; can run pre-stretch on linear starless)
  2. HyperMetric Stretch (stretch the starless)
  3. Revela (structure/local-contrast, post-stretch)
  4. Curves (tonal, post-stretch)
  5. Vectra (selective LCH color grade, post-stretch)
  6. StarComposer (screen developed stars from linear starmask back onto stretched starless)

## Key facts about the VeraLux scripts (from source analysis)

- All operate on the **currently loaded Siril image** and write back via
  `set_image_pixeldata`, EXCEPT StarComposer, which opens its own file dialog to pick
  starless + starmask and saves to a hardcoded `VeraLux_StarComposer_result.fit`.
- StarComposer wants: starmask = LINEAR (it stretches stars internally via tonemap),
  starless = already STRETCHED. That's why STARS is kept linear in the checkpoint.
- IMX533 luminance-weight profile exists in StarComposer: "Sony IMX533 (ASI533)".
- Script filenames (resolve by basename via pyscript):
  VeraLux_Silentium.py, VeraLux_HyperMetric_Stretch.py, VeraLux_Revela.py,
  VeraLux_Curves.py, VeraLux_Vectra.py, VeraLux_StarComposer.py.

## astro_hibou.py integration points

- `Pipeline.__init__` (line ~471): add config attrs.
  - `self.write_stretch_me: bool = True`
  - `self.veralux_interactive: bool = False`
  - per-stage bools: `vlx_silentium/vlx_stretch/vlx_revela/vlx_curves/vlx_vectra/vlx_starcompose` (default True, gated by the master flag).
- `do_process` (line ~1551): after `mark_done`/sidecar, call `self._write_stretch_me(image)`
  and, if `self.veralux_interactive`, `self.veraluxify(image)`.
- New methods:
  - `_run_veralux(script, label)` → `_step(label)`; `self.siril.cmd("pyscript", script)` (blocks); log on resume.
  - `_write_stretch_me(image)` → mkdir `process/_STRETCH_ME`, copy the two files with new
    names (shutil.copy2), write README.txt. Cache via History (outputs exist).
  - `veraluxify(image)` → load denoised starless; for each enabled stage launch the
    script and `save` a stage checkpoint (e.g. `veralux_<stage>_<image>.fit`); StarComposer
    last (user picks files; then rename `VeraLux_StarComposer_result.fit` →
    `<target>_<MODE>_REFERENCE.fit`). History-gated per stage.
- GUI (`Interface._setup_ui` ~2110, `_on_proceed` ~2306, `PipelineWorker.run` ~1921): add
  a checkbox group mirroring the deconv/denoise controls; pass flags onto the Pipeline
  in the worker, same pattern as `deconv_strength`.

## Open/verify

- Confirm on first real run that `pyscript` blocks on the VeraLux Qt event loop
  (window-close), not returning immediately. Fallback if not: pause pipeline + Resume
  button, user launches VeraLux from Siril's Scripts menu.
- Corrbolg drive unmounted during this session — `process/` lives there; runtime only.

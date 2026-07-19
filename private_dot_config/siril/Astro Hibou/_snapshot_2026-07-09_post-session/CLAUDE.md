# Astrophotography Notes

Working directory for astrophotography: rig details, capture sessions, processing
notes, and reference data.

**See also:** [`PLANNED_UPGRADE.md`](PLANNED_UPGRADE.md) — dark-site rig
replacement plan (10″ Newt + IMX455 + NYX-101), with the filter-aperture open
question and backfocus checks still to resolve.

## Rig — imaging chain

| Component          | Model                                      | Notes                                                                |
| ------------------ | ------------------------------------------ | -------------------------------------------------------------------- |
| OTA                | **Askar PHQ80**                            | 80 mm aperture, 600 mm focal length, f/7.5, quadruplet flatfield APO |
| Reducer (optional) | Askar 0.7× (ASRED80PHQ)                    | When fitted: 420 mm @ f/5.25                                         |
| Camera             | **Player One Ares-M Pro**                  | Mono cooled, **IMX533** (1″ square, 3008 × 3008, 3.76 µm), 16-bit    |
| Filter wheel       | Player One Phoenix 7×2″                    | 7 positions                                                          |
| OAG                | Player One FHD-OAG MAX                     | Off-axis guider                                                      |
| Guide camera       | Player One Sedna-M                         | IMX178, 2.4 µm                                                       |
| Mount              | **Juwei-17**                               | Strain-wave                                                          |
| Focuser            | Gemini auto-focuser                        |                                                                      |
| Flat panel         | Gemini flat panel                          |                                                                      |
| Dew heating        | TS-Optics 12V (TSHDC25)                    | 70–90 mm dew shield                                                  |
| Computer / power   | RBFocus Gaius                              |                                                                      |
| Battery            | Omegon Pro 96k LiFePO4 (12V, 26Ah, 307 Wh) |                                                                      |

### Filters — Scorpio Astro

All filters are from **Scorpio Astro**, a single Chinese / AliExpress brand with
two product lines (filter ring labels read "Scorpio Astro"):

- **LRGB:** Scorpio Astro **ScorPlat** — 2″/36 mm broadband set
- **Narrowband:** Scorpio Astro **Scorpio 2** — SII 3 nm / Ha 3 nm / OIII 3 nm

**Filter wheel positions:** 1=L, 2=R, 3=G, 4=B, 5=SII, 6=Ha, 7=OIII

**Player One does not manufacture filters.** Only the cameras (Ares-M Pro, Sedna-M),
filter wheel (Phoenix), and OAG (FHD-OAG MAX) are Player One. The filters are a
separate brand entirely.

Scorpio Astro filters are not in Siril's upstream SPCC catalog, so a local entry
was built by visually digitizing the manufacturer's published transmission chart.
Lives at:

- `~/.local/share/siril-spcc-database/mono_filters/Scorpio_Astro_ScorPlat_LRGB.json`
- Generator: `build_scorplat_spcc.py` (re-run to regenerate if the chart values are
  revised; output goes to `scorplat_lrgb.json`, copy into the catalog dir).
- Filter names registered: `Scorpio L`, `Scorpio R`, `Scorpio G`, `Scorpio B`.
- `dataQualityMarker = 3` — chart-digitized, not measured. Edges ~±2–5 nm, plateau
  heights ~±5%. Replace with measured / vendor-published numeric data if it ever
  becomes available.

SPCC is now **active** in the processing pipeline — see Processing section.

### Filter offsets (autofocus, from N.I.N.A AF panel)

| Filter | Focus offset | AF exposure |
| ------ | ------------ | ----------- |
| L      | 0            | 4 s         |
| R      | −21          | 4 s         |
| G      | −7           | 4 s         |
| B      | 5            | 4 s         |
| SII    | 4            | 8 s         |
| Ha     | 3            | 8 s         |
| OIII   | 0            | 8 s         |

L is the AF reference filter; offsets are applied automatically.

### Image scale & FOV

| Config            | Focal length | Scale        | FOV (3008 × 3008)        |
| ----------------- | ------------ | ------------ | ------------------------ |
| Bare              | 600 mm       | **1.29″/px** | **1.08° × 1.08°** square |
| With 0.7× reducer | 420 mm       | 1.85″/px     | 1.54° × 1.54° square     |

Guide scale via OAG: 2.4 µm @ 600 mm = **0.825″/px**.

## Camera acquisition defaults

- **Gain 125, Offset 25** (all filters, all imaging types)
- **Sensor cooling target: −10 °C**
- **Binning 1×1** everywhere (including AF)
- **Save as FITS**
- **Image path:** `C:\Users\RBFocus\Documents\N.I.N.A\Images\`

## Sub exposures

Sub length is set so sky shot noise dominates read noise (~1 e- at gain 125, HCG).
That threshold scales with sky brightness, so the right length is site-dependent.

**Current site (Bortle 8–9, urban balcony):**

| Filter group | Sub length |
| ------------ | ---------- |
| L            | **60 s**   |
| R, G, B      | **120 s**  |
| SHO (3 nm)   | **300 s**  |

**Dark-site preset (Bortle 2, Valdeblore):**

| Filter group | Sub length |
| ------------ | ---------- |
| L            | **120 s**  |
| R, G, B      | **180 s**  |
| SHO (3 nm)   | **600 s**  |

Adjust per target only with cause (bright core → shorter L; very faint nebula →
longer narrowband). When in doubt: sample sky ADU on a single sub. Sky-limited
≈ sky shot noise > 3× read noise, i.e. sky electrons > 9 e-/px.

## Filter ratios

Time-budget logic: L should get ~2× the per-channel time of any RGB filter for
detail-dominated targets. The ratio in _frame count_ depends on L's sub length
relative to RGB's.

- **LRGB at current site (L=60 s, RGB=120 s):** **4:1:1:1** keeps L at 2× RGB
  total time (4 × 60 = 2 × 120). Push to 6:1:1:1 for detail-dominated targets.
- **LRGB at dark site (L=120 s, RGB=180 s):** **2:1:1:1** (rough parity, L
  slightly heavier). Push to 3:1:1:1 for detail-dominated targets.
- **LRGBHa (current site):** **4:1:1:1:2** — Ha matched to L's time budget at
  300 s subs (2 × 300 ≈ 4 × 60 within tolerance for the ratio engine; in
  practice the auto-balancer redistributes). Bump Ha for emission-dominated
  structure.
- **LRGBHa (dark site):** **2:1:1:1:1** with Ha=600 s — Ha gets the time it
  needs through the longer sub, not through frame count.

The N.I.N.A sequence enforces ratios via Orbuculum's **Auto Balancing Exposure**
instruction, which distributes exposures dynamically rather than fixing per-filter
counts up front.

## Dithering

- **Cadence:** every 1 sub (IMX533 is prone to walking noise — every-frame
  dithering breaks the pattern).
- **N.I.N.A dither pixels (guide scale):** **10 px** (≈6.4 imaging px). The
  plugin reports the imaging-scale equivalent on the Guider info panel; target
  is ≥5 imaging px of shift to break IMX533 walking noise. Conversion at this
  rig: `imaging_px = guide_px × 0.83 / 1.29 ≈ guide_px × 0.64`.
- **Settle:** 3 px tolerance, 15 s min, 60 s timeout. Dither in RA only OFF.

## Target selection rules

- **Apparent size > 2′** — anything smaller is meh at 600 mm.
- **Integrated magnitude < 9.5** (brighter than 9.5) — fainter targets aren't worth
  it on this rig.
- Skip clusters by default unless asked — not interesting.

## N.I.N.A — software stack

- **Scheduler / control:** N.I.N.A
- **Plate solver:** ASTAP (regular + blind fallback), 4 s exposure on L, 1′ pointing /
  1° rotation tolerance, 10 attempts × 2 min delay, 30° search radius
- **Autofocus:** Star HFR via Hocus Focus star detector, Trends + Hyperbolic fitting,
  step size 30, R² threshold 0.8, guiding disabled during AF
- **Meridian flip:** trigger 5 min after meridian (10 min max), recenter ON, no AF
  after flip, no rotation, scope settle 5 s

### Plugins installed

Advanced API · Connector · Filter Offset Calculator · Hocus Focus · Horizon Creator ·
Lightbucket · Orbitals · Orbuculum · Phd2 Tools · Remote Copy · Sequencer Powerups ·
Session Metadata · Shutdown PC · Smart Filters · Three Point Polar Alignment · Web
Session History Viewer

## Sequence template structure (`Advanced Sequence.json`)

**Start:** Connect equipment → 30 s wait → unpark → parallel (dew heater on, cool to
−10 °C, switch to L, open cover, slew to az 120° / alt 35°).

**Pre-Run:** Wait until Nautical Dusk −20 min → solve & sync → AF → start guiding →

- "Wait for dusk" container — `Loop Until Time` (Nautical Dusk −2 min), takes 15 s L snapshots.
- "Wait for target visible" container — Orbuculum `Loop While Next Target Below Horizon` (offset 1°), takes 15 s L snapshots.

The snapshots aren't saved as lights — they're a remote visual cloud check during waits (avoid going outside to look at the sky). 15 s is short enough not to overshoot the exit time and not to saturate during twilight.

Triggers on Pre-Run: AF every 30 min, Meridian Flip.

**Per target** (M104 in the current template):

1. Wait Until Above Horizon (offset 3°)
2. Wait For Time (Nautical Dusk −3 min)
3. Run AF
4. Plate-solve center
5. Start guiding
6. "LRGB Imaging" container — conditions: above horizon AND before Nautical Dawn.
   Inside: Orbuculum **Auto Balancing Exposure** (L:R:G:B = 2:1:1:1, 120 s each).
   Triggers: Center After Drift (2′), AF every 45 min, AF on ±3 °C temp change,
   AF on +10 % HFR over 10 samples, Meridian Flip, Restore Guiding, **Dither every
   1 sub**.
7. "LRGB Flats" container — Trained Flat Exposure × 4, 25 flats per filter at 0.2 s.
   Brightness per filter: L=3, R=22, G=10, B=12.

**Target-level PHD2 Tools triggers:**

- `RestartWhenSaturated`
- `InterruptWhenRMSAbove` — threshold 2.5, min 5 points, Mode 1

**End:** Stop guiding → parallel (switch to L, dew heater off, find home, warm
camera, light off, close cover) → park → 30 s wait → disconnect all → shut down PC.

Variants: SHO version (same shape, 300 s subs), LRGBHa version (LRGB plus 300 s Ha).

## PHD2 guiding settings

**Exposure:** 1.5 s. **Focal length:** 600 mm (OAG = imaging FL).
**Guide scale:** 0.825″/px (Sedna-M 2.4 µm @ 600 mm).

**Mount guide rate: 0.5× sidereal (≈7.5″/s), both axes.** Set 2026-07-08 (was
1.0×). Lower rate = finer correction resolution; standard for this strain-wave
mount. Set live over ASCOM (`GuideRateRightAscension`/`Declination`).
**Persistence across a power-cycle: verified 2026-07-09** — after the mount was
powered down and back up, ASCOM read back 0.5× on both axes and OnStep's own
`:GU#` status reported pulse-guide-rate index 1 (= 0.5×). (Not distinguished:
whether OnStep stores it in NV or the ASCOM driver re-applies it on connect —
immaterial, since every client here connects through that driver.) If it ever
does read 15″/s, re-apply with `gaius:~/set_guiderate_half.ps1` (mount powered,
not connected in N.I.N.A). The guide rate and the calibration step below are
**coupled**: at 1.0× the 250 ms step would give too few calibration steps.

**Calibration** (PHD2 `scope` settings)

- **Step 250 ms** (was 150 ms; sized for 0.5× → ~11 steps over 25 px). Distance 25 px.
- **Procedure (matters — Dec stiction):** calibrate at **Dec ≈ 0 near the
  meridian**, not at the target's declination; **pre-load the stiction** by
  jogging Dec North a couple seconds first, then calibrate from motion, not from
  rest. One clean calibration per night; don't let the session re-calibrate.
- Auto-restore calibration ON. A guide-rate change invalidates a stored
  calibration — clear it (done 2026-07-08 when the rate dropped to 0.5×).

**RA algorithm: Predictive PEC**

- Predictive weight 50 (`prediction_gain` 0.5), Reactive weight 60 (`control_gain` 0.6)
- Min move ~0.68 px, Period auto-computed (~1419 s, auto-adjust on, retain 40 %)
- Max RA duration 2500 ms

**Dec algorithm: Resist Switch**

- Aggressiveness 65, Min move ~1.05 px
- Fast switch for large deflections ON
- Backlash compensation **disabled** (this is stiction, not slack — comp makes it worse)
- Max Dec duration 2500 ms, Dec guide mode Auto

> **Min-move values are condition-dependent and GA-set.** The RA 0.68 / Dec 1.05
> above were auto-applied from the Guiding Assistant on a poor-seeing night
> (2026-07-07). A higher Dec min-move suits the stiction (fewer reversals), so
> don't reflexively lower it — **re-run GA on a good night to retune** rather
> than hand-editing.

**Star tracking:**

- Search region 30 px, Min HFD 2.5 / Max HFD 8.0 px
- Star Mass Detection off; Min SNR 8
- **Multi-star ON**
- Auto-restore calibration ON, Reverse Dec after meridian flip ON
- Stop guiding when mount slews ON, Use Dec compensation ON

> **Diagnostic note (2026-07-08 session, Valdeblore).** Guiding measured ~1.7″
> total RMS (worst subs 2.0″), Dec-dominated. Root cause was **Dec
> stiction corrupting calibration** (repeated `Rates` cal warnings, lurch in the
> backlash-clearing steps → PHD2 under-measured the Dec rate → over-pulsed Dec).
> High-frequency Dec was fine (GA 0.38–0.68″), so it was control, not seeing.
> Late-run star losses were a descending target into dawn (airmass 1.25→1.88,
> sky background ×2.6), **not** dew (heating was on). The 0.5× rate + step 250 ms
>
> - the Dec-0/meridian pre-load calibration above are the response. Separately,
>   the OnStep mount was found holding **stale Nice site coordinates** (43°40′/56 m)
>   while N.I.N.A had Valdeblore — fixed in the driver, and the fix **survived the
>   power-cycle** (verified 2026-07-09, see Operational state).

## Processing — Siril → GIMP → darktable

End-to-end chain after acquisition:

1. **Siril** — automated pipeline (`astro_hibou.py`) does pre-processing, recombination,
   then deconv → denoise → star removal (SyQon). Then **stretch by hand**:
   - **Deep-sky:** Generalised Hyperbolic Stretch (GHS), interactive.
   - **Star clusters:** plain autostretch is fine.
2. **GIMP** — star recomposition (using the script's `starmask_*.fit`), saturation +
   levels touch-up, add legend text.
3. **darktable** — final export with watermark / signature.
4. **Output:** exported images land in `~/Images/Photos/Astro`.

The automated pipeline deliberately exits on linear data (after deconv + denoise)
because everything past that is taste-driven.

### Pre-processing pipeline — `~/.config/siril/scripts/astro_hibou*.py`

Custom Siril python stack (sirilpy + PyQt6) with idempotent stage caching. Split into
a shared library plus three launcher scripts, all in `~/.config/siril/scripts/`:

| File                     | Role                                                                                                                                                                                                                 |
| ------------------------ | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `astro_hibou_core.py`    | Shared **library** — the `Pipeline` (all processing steps), `History` step-cache, SyQon wrappers, metadata sidecar, the generic Qt `PipelineWorker`, and `StatsDialog`. No window of its own; not launched directly. |
| `astro_hibou.py`         | Single-target GUI launcher. Imports the core.                                                                                                                                                                        |
| `astro_hibou_mosaic.py`  | Multi-panel **mosaic** launcher (see Mosaic section). Imports the core.                                                                                                                                              |
| `astro_hibou_veralux.py` | Interactive **VeraLux continuation** launcher (see VeraLux section). Imports the core.                                                                                                                               |

Each launcher makes the sibling core importable with
`sys.path.insert(0, str(Path(__file__).resolve().parent)); import astro_hibou_core`
(Siril sets cwd to the data folder, not the script folder). A fix to the processing
logic lands in one place — the core — and all three launchers pick it up. Only the
launchers appear in Siril's script menu; the core is a library.

The single-target launcher discovers day folders (`YYYY-MM-DD` regex) in the current
Siril working directory, or treats the cwd itself as a single day if it contains
`LIGHTS/` + `FLATS/`.

**Light file naming convention** (parsed by RE*LIGHTS):
`<target>*<filter>_<exposure>s_<index>_<temp>C_S<starcount>\_H<HFR>\_R<rms>_<datetime>.fits`

**Calibration store:** master darks at
`/run/media/vincent/Corrbolg/Astro/Raws/Calibration/master_darks_<exposure>.fit`
(env: `ASTRO_HIBOU_DARK_PATH`). One master dark per exposure length; flats and lights
get the matching dark by exposure.

**Frame quarantine — `<night>/DISPOSED/`.** A sub whose framing is grossly
inconsistent with the rest of its sequence (rotator or imaging train moved
mid-session, a slew that never recentred) makes `seqapplyreg -framing=min`
abort with _"the intersection of all images is null or negative"_, killing the
whole channel. `register_lights` therefore inspects the homographies that
`register -2pass` just wrote into `pp_<filter>_.seq`, **before** running
`seqapplyreg`, and moves the offenders out of `LIGHTS/` into a sibling
`DISPOSED/` folder (with an appended `README.txt` naming each frame and its
reason). **Frames are moved, never deleted** — this drive is the only copy.
`create_master_channel` then rebuilds that filter once, without them.

- Outliers are judged against the **majority** framing, not the reference: the
  2-pass reference is picked on image quality, so it can itself be the rogue
  (it was, for M 101's Ha).
- Tolerances: rotation > **1°** or centre offset > **20 %** of the short side,
  vs the sequence medoid. Real field rotation is « 0.1°/night and dither is
  ~10 px, so only mechanical events trip it.
- **Minority guard:** if the disagreeing frames are more than **40 %** of the
  sequence, nothing is disposed of — two nights shot at genuinely different
  rotator angles look identical to one rogue sub, and the script must not
  silently discard half a target. It logs loudly and lets registration fail.
- Sequences under 3 frames are never judged (1-vs-1 has no majority).

Regression test for the detector (real + synthetic `.seq` cases, including the
M 101 Ha matrices that first triggered it):
`~/.local/share/siril/venv/bin/python3 ~/.config/siril/scripts/test_quarantine.py`

**Siril's star-list cache is keyed by sequence _index_, not by frame.**
`process/cache/pp_<filter>_00002.lst` belongs to whatever image is currently
number 2. Drop a frame and the indices shift underneath the cache, so
`findstar` silently reuses another image's stars ("Trouvé N étoiles avec les
mêmes paramètres … en sautant la détection"). Observed live on M 101: the
`.seq` recorded nbstars 74/43/50 while `cache/` held 43/50/50. Any code that
rebuilds a sequence with a different frame count **must** clear
`cache/*<seq>_*.lst` — `Pipeline._reset_filter_artifacts` does.

**Per-day pipeline:**

1. **Master flats** per filter — convert → calibrate (with dark) → stack (`rej sigma 2.0 3.0`, `-nonorm`).
2. **Master channels** per filter — convert → calibrate lights (`-dark=`, `-cc=dark` for bad-pixel interpolation, `-flat=`) → register (homography, 2-pass, min 10 pairs) → stack:
   - ≥15 frames: `rej winsorized 2.0 3.5`, `-norm=mul`, `-weight=wfwhm`, quality filters at 2k σ on roundness/wfwhm/nbstars.
   - <15 frames: `rej sigma 2.0 3.5` with 80 % percentile quality filters (avoids over-rejecting on small sets).
   - Then `unclipstars`, `platesolve`, save.
3. **Background extraction** per channel via GraXpert AI (`-bge -correction subtraction -smoothing 0.5`). **Single-day only** — in the multi-day path BGE is deferred to the combined master (see below).

**Per-sub background extraction (`subtract_sky_gradient`, GraXpert AI).** Runs on
every calibrated sub, in place, between `calibrate_lights` and `register_lights`.
**Nights are not comparable images.** Measured on M 101's luminance:

| night      | sky level | per-sub σ | gradient (p-p, absolute) |
| ---------- | --------- | --------- | ------------------------ |
| 2026-07-07 | 1.79e-02  | 1.26e-03  | 1.08e-03                 |
| 2026-07-08 | 4.75e-03  | 4.73e-04  | 5.64e-05                 |

A 3.8× sky pedestal, a **2.66×** per-sub noise ratio, a **19×** gradient. One
background extraction on the pooled master can only remove the _average_
gradient; each night's deviation stays baked in and nothing downstream can
separate them again.

**Use GraXpert, not a polynomial.** A polynomial does not remove it. Residual
background structure (64-px block MAD) left after the fit, on three real subs per
night, in units of that sub's own noise floor:

| model         | night 07-07 | night 07-08 | across-night corr |
| ------------- | ----------- | ----------- | ----------------- |
| `subsky 1`    | **5.53×**   | 1.50×       | +0.030            |
| `subsky 2`    | 4.05×       | 1.44×       | +0.072            |
| `subsky 4`    | 1.98×       | 1.53×       | +0.149            |
| `subsky -rbf` | 1.87×       | 1.50×       | +0.147            |

What a plane leaves on the bad night is large **and uncorrelated between nights**
(+0.030), so it is precisely the per-night component that the master-level BGE can
never touch. Only a real background model reaches the noise floor. GraXpert costs
**2.11 s/frame** (measured from the previous run's history timestamps) — 112 subs
≈ 4 min. There was never a cost argument against it.

The worry that a flexible model absorbs real extended sky signal does not survive
arithmetic: the IFN measures ~0.09 % of sky, i.e. ~`4.2e-06` in one luminance sub,
against a 64-px block noise floor of `9.2e-06` — **SNR 0.45**. A per-sub model
cannot reliably see it, so it cannot systematically remove it. (And the objection
would have applied equally to the master pass, where GraXpert has always run.)
GraXpert still runs once more on the combined master; it now has little left to do.
Both call sites share `_run_graxpert_bge()`, with the same write-back verification
as the SyQon tools.

**Select on sky level, not on the night folder.** Sky brightness is a pure
function of Moon altitude: on M 101, `corr(L sky, moon alt) = +0.994` across both
sessions (moon down: 304–312 ADU, flat; moon at +14°: 804; moon at +28°: 1236).
Sun altitude was irrelevant — every sub sat below −17.7°, i.e. astronomical night.
So a "bad night" is rarely a night; it is the moonlit part of a continuum that
usually runs straight through the folder boundary. Siril's `-filter-bkg` /
`-filter-background` cuts on that physical quantity. With `-weight=noise` the
weighting is already ∝ 1/σ² ∝ 1/sky for a sky-limited sub, so an explicit cut is
only needed when a sub's _gradient_ residual, not its noise, is the problem.

**Rejection: `rej p 0.2 0.2` (percentile clipping) at every stack size** — was
`rej sigma 2.0 3.5` under 15 frames, `rej winsorized 2.0 3.5` above. Sigma
clipping rejected **0.000 % of pixels on the high side** of an 8-frame stack: with
so few samples one hot pixel inflates the sample σ enough to hide inside 3.5 of
them. Every hot pixel then survived at every dither position — the constellations
of coloured dots across a stretched master's background (positions differ per
filter, hence the colour). Measured on this target's own registered sequences,
identical frames, only the algorithm changed, counting isolated hot pixels left in
the master's background:

| rejection                | 8 red frames | bg σ                    | 23 lum frames |
| ------------------------ | ------------ | ----------------------- | ------------- |
| `rej sigma 2.0 3.5`      | 1041         | 1.767e-04               | 394           |
| `rej winsorized 2.0 3.0` | 226          | 1.813e-04               | 380           |
| **`rej p 0.2 0.2`**      | **63**       | **1.718e-04**           | **16**        |
| `rej GESDT 0.3 0.05`     | 2            | 2.492e-04 (+45 % noise) | 7             |

Percentile clipping is not a trade: it removes 16× more hot pixels **and** gives
the lowest noise of anything tried, at both stack sizes.

**Frame selection: `-filter-round=3k` only** — the `wfwhm`/`nbstars`/`roundness`
cuts were deleting signal for nothing. Same sequences, percentile rejection held
fixed:

| stack             | frames kept | hot | bg σ                  |
| ----------------- | ----------- | --- | --------------------- |
| RED, 80 % filters | 5 of 8      | 687 | 1.726e-04             |
| RED, no filter    | 8 of 8      | 258 | **1.377e-04 (−20 %)** |
| LUM, 2k filters   | 13 of 23    | 41  | 2.023e-04             |
| LUM, no filter    | 23 of 23    | 32  | **1.090e-04 (−46 %)** |

Filtering discarded **43 % of the luminance** and made the master **46 % noisier**,
with _more_ hot pixels (fewer frames to reject against). `-weight=noise` already
down-weights poor frames by their variance; cutting them as well is
double-counting. `-filter-round=3k` stays as a cheap guard against a genuinely
trailed frame — on this data it rejects nothing and costs nothing. Tiny sets
(< `QUALITY_FILTER_MIN_FRAMES`) still get no whole-frame filter at all, or Siril
aborts with "the filtering options do not allow processing at least two images".

**Cosmetic correction: leave `-cc=dark` at its defaults.** Cold-pixel detection is
degenerate on these darks — it flags **600 067 pixels regardless of sigma** (identical
at 1, 3 and 5), because the master dark has a large population clipped at zero.
Siril disables cold by default, correctly. Tightening the hot sigma is also futile:
`-cc=dark 0 0.5` corrects **62 693** pixels (0.7 % of the sensor) and takes the
residual hot spikes in a calibrated sub only from 236 to 228 — they are cosmic rays
and drift, not the dark's hot-pixel map (the darks are the stale 2025 offset-30 set;
see the reshoot TODO). Hot pixels are a _rejection_ problem, not a calibration one.

**Stacking flags: `-norm=add -weight=noise`** (were `-norm=mul -weight=wfwhm`;
`addscale` was an intermediate mistake, see below).

**Never use a normalisation with a _scale_ term on moonlit data.** Light pollution
and moonlight are **additive**; only transparency is multiplicative. Siril
estimates the scale factor from the frame's MAD, which for a sky-limited sub tracks
the Moon, not the transparency — so it divides the moonlit frame's real **signal**
by ~2.2 along with its noise. `mul` does this grossly (night 07-07 scaled by ~0.26,
making a bright night look quiet, `σ 3.3e-04` vs the good night's `4.7e-04`);
`addscale` does it subtly and is just as wrong. Measured on M 101's luminance, with
SNR = signal / noise over a fixed source mask:

| configuration              | N   | noise     | SNR            | vs baseline |
| -------------------------- | --- | --------- | -------------- | ----------- |
| 18 frames `addscale`+noise | 18  | 1.303e-04 | 1.0522e+07     | baseline    |
| 18 frames **`add`**+noise  | 18  | 1.029e-04 | 1.1433e+07     | **+8.7 %**  |
| 23 frames `addscale`+noise | 23  | 1.163e-04 | 1.0055e+07     | −4.4 %      |
| 23 frames **`add`**+noise  | 23  | 1.008e-04 | **1.1532e+07** | **+9.6 %**  |
| 23 frames `add`, no weight | 23  | 1.131e-04 | 1.0143e+07     | −3.6 %      |

Under `addscale` the moonlit night made the master **worse** (signal −14.7 %, noise
−10.7 %, SNR −4.4 %) — the noise drop was an illusion created by shrinking the
signal. Under `add` it is a small gain. _Caveat:_ `add` does not correct genuine
transparency variation; on a thin-cloud night a scale term would help. Here the
dominant variation is the Moon (sky level vs moon altitude, r = **+0.994**), which
is additive, and the measurement is unambiguous.

`-weight=noise` is doing real work: dropping it costs **13 %** SNR (`add`+noise
`1.1532e+07` → `add`, no weight `1.0143e+07`). `wfwhm` weights on star sharpness
and is blind to sky noise entirely.

Both flags verified accepted headless (`siril-cli`); `-weight=bogus` errors, so the
parser really validates.

**Verdict on the moonlit night (5 of 23 L subs):** under the correct flags it is a
**wash** — SNR `1.1433e+07` → `1.1532e+07` (+0.9 %) for +2.9 % background structure.
Keep or drop; it no longer matters. Under the old flags it was actively harmful.

This supersedes the old "one BGE on the combined master is enough" reasoning and
explains the luminance anomaly noted above: L pools the most subs from the worst
night.

**Multi-day (pooled-sub "gold standard"):** each night is calibrated and gets a
per-night master built _as a diagnostic only_ (no per-night BGE). The combined
master is then built by **pooling every night's calibrated subs**
(`pp_<filter>_*.fit`, symlinked via `link` to avoid duplicating them on disk),
registering them all to **one common reference** (2-pass homography,
`-framing=min`), and running a **single stack** with the full quality filters and
per-sub `-weight=wfwhm`. Background extraction runs **once**, on the combined
master. This gives optimal per-sub noise weighting and lets pixel rejection act
across nights — a master-of-masters stack would instead weight a thin night
equally with a deep one and could make the result worse than the deep night
alone.

- _Resolved 2026-07-09:_ the old trade-off ("one BGE pass models a single blended
  gradient across nights") is gone. `subtract_sky_gradient` now flattens **every
  sub** before registration, so the pooled stack sees a common background and the
  single AI BGE on the combined master only mops up. The mooted fallback
  (per-night BGE + `nbstack`-weighted master-of-masters) is no longer needed and
  would have thrown away cross-night pixel rejection for nothing.
- _Re-running on data processed under the old master-of-masters layout:_ hit
  **Reset history** so the new combine path runs from scratch (it needs each
  night's calibrated `pp_` subs present on disk).

**Recombination options** (in `process/`):

- **LRGB / RGB:** `linear_match` R,B to G → `rgbcomp` → color calibrate. **The
  L is NOT folded into the linear master** (no `rgbcomp -lum=`): combining the
  deep luminance into linear colour data **greys the result** — the L pushes the
  nebula to the bright end where a subsequent stretch compresses the channels
  together and colour washes out (confirmed by reproduction: `rgbcomp -lum` →
  gray, same channels without `-lum` → vivid pink; Siril's GUI "Composition TSL"
  avoids it but has no CLI equivalent, and an exact numpy `rgb·L/mean(rgb)`
  transfer greys the same way). So compose stops at a colour-calibrated **RGB**
  master; the luminance (`master_luminance.fit` / `blended_luminance.fit`) is
  combined **after stretching**, where LRGB belongs. _Consequence:_ deconvolution
  now runs on the RGB's own luminance, not the deep L — driving deconv from the L
  would need a separate luminance path (TODO).
- **HaLRGB-R / HaLRGB-L:** blend Ha with weight `w` (default 0.5):
  `channel = (1-w)*base + w*Ha`, linear-matched first. **-R** blends Ha into the
  red _colour_ channel (survives — it's colour, not luminance). **-L** computes
  the Ha-enhanced luminance and saves it as `blended_luminance.fit` for the
  post-stretch combination, but (like LRGB) does **not** fold it into the linear
  master. Both output an RGB colour master.
- **SHO / HOO / OHS / HSO:** linear_match SII,OIII to Ha → rgbcomp in chosen order.
- **Foraxx:** dynamic mask palette using stretched Ha/OIII templates ($TH, $TO) via pixel math.

> **PixelMath expressions must be quoted — always go through
> `Pipeline.pixel_math()`.** Siril splits a command line on spaces and `pm` then
> evaluates only the **first token**, silently discarding the rest: no error, no
> warning, no log line. Every expression here has spaces around its `+`, so the
> unquoted `cmd("pm", "0.5*$aligned_red$ + 0.5*$aligned_ha$")` evaluated as
> `0.5*$aligned_red$` and threw the Ha away. Verified on M 101:
> `blended_red.fit` was bit-identical to `0.5 × aligned_red.fit`
> (`maxdiff = 0.0`), likewise `blended_luminance.fit` vs `aligned_luminance`.
> **HaLRGB-R, HaLRGB-L and both Foraxx channels produced no Ha contribution at
> all, from the first run until 2026-07-09.** `pixel_math()` wraps the
> expression in double quotes; never hand-build a `pm` call.

> **`ha_weight` is a noise knob as much as a colour knob — default 0.30, not
> 0.50.** Ha is a 3 nm band; `linear_match` scales it ~3× to sit at R's level and
> its noise rides along. Measured on M 101: scaled Ha carries σ `1.71e-04`, **2.6×**
> `aligned_red`'s `6.55e-05`. At w=0.5 the blended red lands at `9.17e-05`, 1.40×
> noisier than red _or_ green — red becomes the noisiest channel, so `P(R greatest)`
> in the sky rises to 37–39 % against the 33.3 % of equal-variance channels, and the
> sky **reads brown even though its median is exactly neutral** (rendered crop: RGB
> `36,36,36`). It is chroma noise, not a cast: `_neutralize_background()` does
> nothing for it, and the giveaway is that `std(R−G)/std(B−G) = 1.543` in the render
> matches `σ_blended_red/σ_blue = 1.571` in the FITS. It is _not_ a gain error — on
> stars far from the galaxy the R/G slope is `0.920` vs LRGB's `0.908`, +1.3 %.
> w=0.30 gives `6.89e-05` (1.05× red) and keeps most of the Ha signal. Note the
> brown largely vanishes after Prism anyway; it is loudest on the `_deconvolved`
> intermediate.

> **Background extraction and stacking are NOT the source of the mottle** — but the
> background is not flat either, and that is correct. At 128 px the `lrgb` background
> carries real structure of MAD `1.38e-06`, **2.4× the noise floor**. It is real sky,
> not BGE residue: `extract_bg` runs per channel independently, so residue would be
> uncorrelated between filters, yet the R/G/B background maps correlate
> `0.374 / 0.411 / 0.337` — against a theoretical ceiling of ~`0.41` given their
> noise, i.e. **essentially fully shared** — while narrowband Ha does not follow it
> at all (`0.036 / −0.071 / −0.077`). Grey dust / IFN, which M 101's field is known
> for. Deconvolution preserves it (corr `0.997`). Prism does not: fitting the
> denoised background against the real one gives `denoised_bg = 0.646 × real_bg +
residual`, with the real field explaining only **46.5 %** of the variance and an
> invented residual of MAD `8.87e-07`. So roughly half of what you see in a
> hard-stretched denoised background is real sky the pipeline correctly left alone,
> and half is the denoiser's own invention.
>
> _Explained 2026-07-09:_ `master_luminance` carried `2.28×` the noise floor with
> autocorrelation `0.615` at 32 px, yet correlated only `0.138–0.305` with the RGB
> masters against a ceiling of ~`0.58` — structure that is **not** shared sky. Cause:
> L pools the most subs from the worst night. 2026-07-07's luminance gradient is
> `1.08e-03` peak-to-peak, **19×** night 07-08's and 67 % of that night's entire sky
> level; a single BGE on the pooled master could only remove the average. Fixed by
> `subtract_sky_gradient` + `-norm=add -weight=noise` (see the pre-processing
> section). Re-check this metric after the next full rebuild.

> **HaLRGB-L's colour master is pixel-identical to LRGB's, by design.** Neither
> folds L into the linear master (that greys the colour), so both reduce to
> `rgbcomp(r,g,b)` + SPCC. The Ha lives only in `blended_luminance.fit`, applied
> post-stretch. Do not read "halrgb_l.fit == lrgb.fit" as a bug — it is the
> intended output. HaLRGB-**R** is the one that must differ in the linear master.

**Color calibration: SPCC active.**

- **Sensor:** `SPCC_SENSOR = "Sony IMX411/455/461/533/571"` (the catalog's combined
  IMX entry — covers IMX533).
- **Filters:** `Scorpio R / G / B` — built locally from a visually-digitized
  manufacturer chart, installed at
  `~/.local/share/siril-spcc-database/mono_filters/Scorpio_Astro_ScorPlat_LRGB.json`.
- **Quality:** dataQualityMarker = 3. Acceptable for color-accuracy in
  pretty-picture work; not for photometric science. Replace with measured numeric
  data if Scorpio Astro ever publishes it.
- **Upstream contribution path:** the local JSON is structured to be PR-ready to
  <https://gitlab.com/free-astro/siril-spcc-database/> if/when somebody wants to
  upstream it (would need cleanup of the data-quality assertions to reflect that
  it's a visual digitization).

**Post-processing (still linear data) — SyQon suite, one order.** Deconv,
denoise, and star removal are the **SyQon** tools, run via `pyscript` (same
mechanism as GraXpert BGE) through `Pipeline._run_syqon` → `cmd("pyscript",
…)`. They only run under the **interactive GUI** — Siril initialises its Python
there; every non-GUI mode (`siril-cli`, `siril -s`, `siril -p`) reports "python
not ready" and cannot run a pyscript at all.

Two hard-won gotchas on large (mosaic) masters:

- **GUI load segfault (Siril bug).** Freeing/replacing a large master that is
  already loaded SIGSEGVs the GUI — the _first_ load always works, but the next
  `load` or `close` dies (Siril's own handler prints "report this bug", so there
  is no coredump; the visible symptom is a downstream `_send_command`
  broken-pipe dialog once Siril dies). A `close`-before-load helper did **not**
  fix it (it just moved the crash to the `close`). The real workaround:
  `do_process` loads the master **exactly once** and chains Parallax → Prism →
  Starless _in place_ (the SyQon tools all modify the loaded image, so the
  per-step reloads were unnecessary). On resume it `open_image`s the cached
  deconvolved master once, then denoise+starless run with no further load.
  Headless `siril-cli` loads the same file fine — it's GUI-only. Reliable manual
  fallback: fresh Siril → open the deconvolved master → run SyQon Prism then
  Starless from the Scripts menu (both apply in place, no reload).
- **Parallax stdout deadlock.** SyQon's CLI prints one `end="\r"` progress line
  per tile with `PYTHONUNBUFFERED=1`, and Siril's `pyscript` only drains the
  child's stdout pipe **after** it exits. On the biggest mosaics Parallax's
  output overflows the 64 KiB pipe → deadlock (tool blocks on `write`, Siril in
  `waitpid`). Rescue by draining from outside: `dd if=/proc/<siril>/fd/<n>
of=/dev/null`. Prism/Starless print little and don't hit this.
  **`syqon_logged.py` is live, not reverted** — `Pipeline._run_syqon` invokes
  every SyQon tool as `cmd("pyscript", "syqon_logged.py", "<Tool>.py", *args)`
  (`astro_hibou_core.py`). An earlier note here said the wrapper had been tried
  and abandoned; that was wrong, corrected 2026-07-09 after finding it in the
  live process tree mid-run.

(GraXpert BGE still runs as a plain `pyscript` on smaller per-channel masters.)
GraXpert/StarNet++ are no longer used here
(GraXpert is still the background-extraction engine upstream). The order is the
standard AI-tool sequence — **deconvolve → denoise → remove stars**, all on
linear data with stars present through the first two stages. Denoise no longer
runs after star removal, and there is **no full-vs-starless deconv toggle** (a
single path):

1. **SyQon Parallax** (`Parallax.py --edition pro --star-level 0 --sharpen <deconv_strength>`) —
   deconvolve/sharpen the full linear master, stars present. Aberration
   correction stays **on** (config); star reduction off. `deconv_strength`
   default **1.0** → sharpen alpha. Output: `<image>_deconvolved.fit`.
2. **SyQon Prism** (`Prism.py --model deep --modulation <denoise_strength>`) —
   denoise the deconvolved full frame on linear data. `denoise_strength`
   default **0.85** → modulation blend (see the grain/residual table below).
   Output: `<image>_denoised.fit`.
3. **SyQon Starless** (`Starless.py --axiom3`, Axiom V3) — remove stars →
   `starless_<image>_denoised.fit` + `starmask_<image>_denoised.fit`. No
   upscale (StarNet's `-upscale` 2× is dropped; output stays native res).
4. **STOP.** Files left on disk: `starless_<image>_denoised.fit`,
   `starmask_<image>_denoised.fit`. Stretch / star recomb / final cosmetic = manual.

**Both strength knobs are blend fractions against the _unprocessed_ input, not
intensity dials.** Parallax: `out = in + α·(sharpened − in)`. Prism:
`out = m·denoised + (1−m)·original`. So 0.5 does not mean "denoise moderately",
it means **keep half the noise**. Measured on M 101's LRGB master: at `m=0.5`
high-frequency noise fell 2× (4.98e-05 → 2.51e-05); the same frame at `m=1.0`
fell **173×** (→ 2.88e-07), and the `m=0.5` output was reproducible to float32
round-off as `0.5·deconvolved + 0.5·fully_denoised` (best-fit α = 0.50000).
SyQon's own defaults are 1.0 for both, but those are _GUI_ defaults — the
operator previews and dials back. Before 2026-07-09 the pipeline passed 0.5 for
both without knowing that is what it meant.

**Prism's modulation scales the grain, not the residual — and the grain is what
hides the residual.** `denoise_strength` is **0.85**, not 1.0. Prism leaves a
_smooth_ low-frequency error (coloured continents, a dark halo hugging bright
objects) that barely shrinks as modulation drops; what drops is the random grain
covering it. Measured on M 101 (grain = pixel-to-pixel MAD, residual = 32-px
block structure vs the deconvolved frame, both on masked background):

| m    | grain    | smooth residual | grain/residual | bg chroma spread |
| ---- | -------- | --------------- | -------------- | ---------------- |
| 0.50 | 2.52e-05 | 1.24e-06        | 20.2×          | 0.672 %          |
| 0.85 | 7.80e-06 | 2.14e-06        | **3.7×**       | 0.742 %          |
| 0.95 | 2.78e-06 | 2.37e-06        | 1.2×           | 0.771 %          |
| 1.00 | 2.93e-07 | 2.52e-06        | **0.12×**      | 0.804 %          |

Random grain is invisible — the un-denoised master's own 32-px block noise is
`4.9e-06`, _twice_ the residual, and nobody ever sees it. Smooth structure is
not. At `m=1.0` the residual is 8.6× the grain and becomes the dominant feature
of the image; the star field and the grain were the only things hiding it, which
is why the **starless** frame looks worst of all. `m=0.85` removes 84 % of the
noise and keeps a 3.7× margin.

**Star removal is not the problem.** Measured: Starless changes the 32-px
background by MAD `4.9e-08` (30× less than the denoise residual) and the diffuse
pedestal it removes is `-0.00σ` at every radius from 150 to 1600 px with star
pixels masked. It only removes stars. It just also removes the last thing that
was masking Prism's residual.

**Background neutralisation runs after Prism** (`_neutralize_background`, wired
into both `do_process` paths and `denoise()`). Parallax and Prism each normalise
per channel before inference and hand back a per-channel DC offset; the spread
between the R/G/B sky medians grows `0.12 % → 0.58 % → 0.80 %` across `lrgb →
deconvolved → denoised`, green always highest. Every stretch anchors just under
the sky and divides by what remains, so that offset becomes a flat olive cast.
Subtracting a constant per channel is the honest correction — the sky is neutral,
a DC offset carries no signal, object colour is untouched — and it takes the
spread to exactly `0.000 %`.

**NEVER autostretch a denoised frame. Derive the stretch from the pre-denoise
frame.** This is the single most important rule in the post-processing chain, and
it looks exactly like a denoise bug until you measure it. (It still bites at
`m=0.85`: the midtone comes out `0.000088` against the deconvolved frame's
`0.000498`, 5.7× harsher.)

Siril's `autostretch` puts its black point at `median − 2.8σ` and solves a
midtone that maps the background to 0.25. Both depend on σ. Prism at
`modulation = 1.0` takes M 101's background MAD from `5.9e-05` to `3.7e-06`, so
autostretch answers with a midtone of `0.00003` instead of `0.00049` — **16×
harsher**. What that reveals is Prism's own low-frequency residual bias:
`2.2e-06`, which is a perfectly ordinary **3.7 %** of the noise the model was
shown, but **59 %** of the noise that survives it. Amplified 16×, it becomes
green and magenta continents hundreds of pixels across, a pink halo round the
galaxy, a blown white core and a sky lifted out of black.

Proven, not inferred:

- The linear master's background is **clean**: 32-px block-median MAD `4.9e-06`,
  ≈2× the pure-noise floor, uncorrelated block to block. No mottle upstream.
- The continents are **absent from the input and present in the output**: the
  32-px lowpass of `lrgb` vs `lrgb_denoised` correlates only `0.877`; the
  difference has MAD `2.2e-06`. Deconvolution changes the same lowpass by
  `3.2e-07`, 7× less — Parallax is not the culprit.
- Everything is 32-bit float (`BITPIX -32`, quantisation step `1.2e-10`), so it
  is not posterisation.
- **Stretching the identical denoised pixels with the deconvolved frame's black
  point and midtone yields a clean image**: pixels above 0.9 go `1.39 % → 0.066 %`,
  matching the un-denoised `lrgb`'s `0.073 %`. No blobs, no cast, no blown core.

So `denoise_strength` stays at **1.0**. `do_process_cluster` captures
`_autostretch_params()` from the deconvolved frame _before_ Prism runs and
applies them with `_apply_stretch()` afterwards (numpy + `set_image_pixeldata`,
never Siril's `autostretch`, which would recompute them). For the deep-sky path
the stretch is manual, so `_STRETCH_ME/README.txt` now carries the measured
per-channel black point and midtone — **use them; do not autostretch the
STARLESS.**

**What is and is not affected.** The rule is narrower than "denoised frames are
cursed": a stretch is unsafe only if it derives its black point from the denoised
frame's **σ or a low percentile**.

| Stretch                                          | Black point from                    | Safe on a denoised frame? |
| ------------------------------------------------ | ----------------------------------- | ------------------------- |
| Siril `autostretch`                              | `median − 2.8σ`                     | **No** — σ collapsed 16×  |
| VeraLux HMS, _Adaptive Anchor_ (default, **ON**) | smoothed-histogram morphology       | **Yes**                   |
| VeraLux HMS, _Statistical_ anchor (unticked)     | 0.5th percentile                    | **No**                    |
| GHS by hand                                      | whatever you pick off the histogram | **No** if eyeballed       |

Measured on M 101's `starless_lrgb_denoised.fit`: the adaptive anchor gives
`0.001175`, versus `0.001129` on the pre-denoise deconvolved frame — a 3-bin
difference, because it is set by a 50-bin boxcar over a 65536-bin histogram
(bin width `1.53e-05`), not by σ (`3.3e-06`, a quarter of one bin). The
statistical anchor instead lands at `0.001566`, `1.0e-05` **under** the sky.
That matters because HMS reconstructs colour as `channel / (L − anchor)`: with
the adaptive anchor the background divisor is `4.0e-04`, with the statistical
one it is `9.4e-06`, so Prism's residual chroma bias is divided by ~zero and
`log D` jumps from 20 744 to 3 194 438 (154×). Rendering both confirms it — the
statistical anchor reproduces the green/magenta continents and dark blobs
exactly; the adaptive one gives a clean grey sky.

So: **leave "Adaptive Anchor" ticked in HyperMetric** (it is on by default, and
`reset()` re-ticks it) and no manual numbers are needed there. The
`_STRETCH_ME/README.txt` figures are for MTF-style stretches — Siril's
autostretch, or a hand-set GHS symmetry point. Never eyeball a black point off
the denoised frame's histogram: its visible spread is 16× too narrow.

Parallax at **1.0** looks right, but it clips star cores: `pixels ≥ 1.0` goes
3 → **1138** (at α=0.5 it was 889). Worth running `unclipstars` after
deconvolution, not only after stacking.

**Mosaic star-mask color patchwork — the root cause is per-panel color
mismatch (fixed upstream, see mosaic step 3).** The green/magenta/yellow
patchwork in the M8-M20 star mask (and its recombined image) is **not** a
star-mask problem and **not** a stretch problem — it is per-panel color
mismatch baked into the linear data upstream (panels carry R/G differing 2.4×;
fixed by per-panel SPCC — see `_spcc_calibrate_panels`). Chasing it downstream
wasted a lot of effort and is recorded here so it isn't repeated:

- It is **not** a BGE/gradient artifact — the starless _sky background_ measures
  flat + neutral to ~1% (R/G 0.994±0.011). The mismatch is in the _star flux_,
  which BGE excludes by design, so an extra BGE does nothing.
- It is **not** fixable on the star mask alone. Tried and reverted an automated
  `_desaturate_starmask` step (knee-based luminance desaturation): it turned the
  recomposed stars **monochrome**, because in a hard stretch the faint layer
  dominates the visible flux and desaturating it grays the whole field. Also
  tried (in analysis) chroma-blur → garish RGB fringing, and black-clip →
  deletes the star field. Within a single mask the faint magenta floor and the
  faint star field are the same pixels, so no linear op separates them.
- It is **not** fixable at the stretch stage either — with Log D already at its
  0.00 floor the patchwork persists, because the per-panel casts are in the
  data, not the curve.

The fix belongs where the color goes wrong: **SPCC-calibrate each panel before
assembling the mosaic** (mosaic step 3, `_spcc_calibrate_panels`). Re-run the
mosaic launcher; the per-panel SPCC fires and rewrites the panel masters, whose
mtime bump cascades a rebuild through combine → compose → deconv/denoise/star-
removal.

**Models are the paid/premium editions**, pinned per tool and installed under
`~/.local/share/siril/syqon_{parallax,prism,starless}/`: Parallax **pro**
(`parallax_sharpen.pth`), Prism **deep** (`prism_deep.pt`), Starless **Axiom V3**
(`axiom3.pt`). GUI knobs: "Deconv blend (1.0 = full)" (Parallax sharpen α) and
"Denoise blend (1.0 = full)" (Prism modulation). Parallax defaults to **1.0**,
Prism to **0.85**. See the
blend-fraction warning above before lowering either.

**Every SyQon / GraXpert pyscript write-back is verified.** The tools push their
result with `set_image_pixeldata()` inside a `try/except Exception` that merely
_prints_ on failure and exits 0 — so a tool can burn its full inference time,
fail to update Siril's image, and leave the pipeline saving the untouched input
buffer under the output name, then caching the step as done. `_run_syqon(...,
expect_change=True)` and `extract_bg` now hash Siril's pixel data before and
after (`Pipeline._image_signature`) and raise if nothing changed; the
`undo_save_state` HISTORY label is only stamped once the change is proven, so a
FITS `HISTORY` card can no longer attest to work that never happened. Observed
2026-07-09 on M 101: `halrgb_r_denoised.fit` came out **bit-identical** to
`halrgb_r_deconvolved.fit` after an 8-minute Prism run, with a
`SyQon Prism denoise` HISTORY card on it.

**`do_process` must load its own input.** The SyQon chain is deliberately
single-load (see the GUI segfault note), and its only loader used to be
`_manual_crop_pause()`, which returned early without loading whenever
`manual_crop` was off. Parallax then ran on whatever Siril happened to hold: for
the first recombination the last-composed master, and for every one after it the
_previous_ image's Starless output. On M 101 that made `halrgb_r_deconvolved.fit`
a re-deconvolved **star-free LRGB** (its FITS `HISTORY` read Parallax → Prism →
Starless → Parallax). `_manual_crop_pause` now always leaves `<image>.fit`
loaded, crop or no crop.

**Zenith setup is now skipped entirely under `--axiom3`.** Previously
`Starless.py`'s `main()` always ran `setup_model_torch` (Zenith update check +
download) regardless of the selected model. Against the unreachable
`siril.syqon.it`, the update check's `download_file` call had **no timeout** and
blocked on the OS TCP timeout (~2m14s) before printing "Could not check for
updates to zenith.pt" — dead wall-clock on every run. Fixed 2026-07-05 by two
local edits to `~/.local/share/siril-scripts/SyQon/Starless.py`:

1. `main()` computes `selected_model` first and only calls `setup_model_torch`
   when `selected_model == "zenith"`. Under `--axiom3` the Zenith weights are
   never loaded, so the whole network round-trip is skipped.
2. `download_file`'s `urlopen` gained `timeout=30` as a network circuit-breaker
   (only fetches the tiny `.date`/`.sha256` files; the 377 MB model uses
   `download_with_progress`, untouched), so the Zenith path can't hang forever
   either.

These are in-place edits to the upstream community script — an in-app repo pull
will overwrite them; re-apply after updating SyQon. The placeholder
`~/.local/share/siril/syqon_starless/zenith.pt` is no longer needed under
`--axiom3` (setup is skipped before it's ever consulted) but is harmless to
leave. `do_process` verifies the starless/starmask outputs exist before marking
the step done, so a failed Starless is no longer falsely cached as complete.

**Pre-stretch checkpoint (`_STRETCH_ME/`) — always written.** After `do_process`,
the pipeline copies the pre-stretch pair into `process/_STRETCH_ME/` with loud,
paired names so the hand-off point is unmistakable:

- `<target>_<MODE>_STARLESS.fit` — the denoised, **linear** starless; stretch this
  by hand (GHS / VeraLux).
- `<target>_<MODE>_STARS.fit` — the **linear** star mask; feed to star
  recomposition (it expects linear stars over the stretched starless).
- `README.txt` — one-liner stating which is which.

`<target>` = target folder name, `<MODE>` = LRGB/SHO/etc. This is the default stop;
everything past it is taste-driven. (Toggle: `Pipeline.write_stretch_me`, default on.)

**VeraLux interactive continuation — its own launcher (`astro_hibou_veralux.py`).**
Formerly an opt-in checkbox inside the main script; now a **separate launcher** so the
core pipeline stays lean. Run the main or mosaic pipeline in _full_ mode first (stops
at `_STRETCH_ME/`), then launch `astro_hibou_veralux.py` from the same target/mosaic
directory: it scans the `process/` dir(s) for the recombined images left behind
(`starless_*_denoised.fit` / `*_deconvolved.fit`, or the `*_cluster_*` checkpoints for
cluster targets) and offers to continue any of them. It does **not** replicate VeraLux
math — it launches the real VeraLux GUI scripts via `cmd("pyscript", …)` (same
mechanism as the GraXpert calls) and **blocks on each until you close its window**,
then saves and moves on. Chain order, each stage individually skippable and
History-cached:

Silentium (denoise) → HyperMetric Stretch → Revela (structure) → Curves → Vectra
(color) → StarComposer (recombine stars). StarComposer's output is renamed to
`<target>_<MODE>_REFERENCE.fit`. Per-stage intermediates: `veralux_<image>_<stage>.fit`.

**Denoise ownership — no double-denoise.** When **Silentium is enabled**, Silentium
is the sole denoiser for the reference branch, so it must start from a starless that
has **not** been Prism-denoised. In the new order denoise runs before star removal, so
no such starless exists in the main flow — `veraluxify()` builds one with a dedicated
extra `remove_stars()` pass on the deconv-only frame (`<image>_deconvolved.fit` →
`starless_<image>_deconvolved.fit`). The always-on Prism-denoised `_STRETCH_ME`
STARLESS checkpoint is left untouched as a parallel result. When **Silentium is off**,
the chain starts from the Prism-denoised starless (`starless_<image>_denoised.fit`).
Cluster mode branches from `<image>_cluster_deconvolved.fit` (deconv-only, pre-Prism)
when Silentium is on, else from `<image>_cluster_prestretch.fit` (deconv+denoise); its
autostretch `<image>_cluster.fit` baseline and the VeraLux reference stay
single-denoised.

**In cluster mode** the continuation still applies, minus the stages that don't fit
point-source fields. **Silentium → HyperMetric Stretch → Curves → Vectra** run,
branching from the linear `<image>_cluster_prestretch.fit` checkpoint (Silentium needs
linear input; HyperMetric _is_ the stretch), and write a VeraLux reference alongside
the normal autostretch `<image>_cluster.fit` baseline. **Revela** (luminance
structure) and **StarComposer** (needs the starless/starmask decomposition) are
**skipped automatically** for cluster images (their checkboxes stay, but the cluster
path ignores them). Cluster intermediates: `veralux_<image>_cluster_<stage>.fit`.

No fork / no version guard — the scripts stay as upstream ships them and update with
the in-app repo pull. Historical implementation notes:
`~/.config/siril/scripts/VERALUX_INTEGRATION_PLAN.md` (describes the earlier in-script
integration, before the launcher split). Pre-change backups of the old monolithic
script: `astro_hibou.py.bak-veralux` (VeraLux integration) and `astro_hibou.py.bak-syqon`
(SyQon engine swap + reorder) — both predate the core-library split.

**Cluster mode:** alternative path for star-field targets (no faint extended
structure). No star removal. Parallax deconv → **save deconv-only linear
checkpoint** (`<image>_cluster_deconvolved.fit`) → Prism denoise → **save linear
pre-stretch checkpoint** (`<image>_cluster_prestretch.fit`) → autostretch →
unclipstars. Final output: `<image>_cluster.fit`. Both linear checkpoints are
kept and never overwritten (the final save targets a different file): the
deconv-only one feeds the Silentium branch, the deconv+denoise one lets the
stretch be redone by hand without re-running deconv/denoise.

**Caching:** `.history` file at root tracks completed stages with timestamps. A step
is valid only if its outputs still exist AND no input mtime is newer than the
completion time — touching a calibration file invalidates everything downstream
automatically. GUI "Reset history" button forces full re-run.

The mosaic **manual crop** (the hand-crop pause before deconvolution) is itself a
cached step (`manual_crop`, keyed on the recombined master with the master as both
input and output). This matters because that pause re-saves the master in place: if
it re-ran on every resume, the fresh mtime would invalidate the cached deconvolution
and force a needless ~40-min re-deconvolve. Caching it means a resume whose
`do_process` didn't finish (e.g. crashed at denoise) skips the re-crop, keeps the
master's mtime frozen, and picks up at denoise. It still re-crops correctly if
recombination rewrites the master (mtime then exceeds the crop's completion).

### GIMP

Used for: final non-linear adjustments, star recomposition with the starmask,
selective contrast/saturation, dust/satellite-trail cleanup, framing/crop. Reads
the script's `starless_*_denoised.fit` outputs.

The **`astro-legend.py`** GIMP plugin (legend auto-fill) resolves metadata two
ways: from an export-named file (`YYYY-MM-DD_<target>-<mode>.<ext>`), or — for a
file straight out of the pipeline (`veralux_*`, `starless_*`, `*_cluster`,
`*_REFERENCE`) — by taking the **target from the folder** under `Raws/` and the
**mode from the filename token**, then reading the common name + date from the
matching `process/*.meta.yaml` sidecar. So any pipeline FITS in a target folder
auto-fills without needing a date in its name.

## End-to-end workflow

1. **Capture** — N.I.N.A on Gaius writes FITS to
   `C:\Users\RBFocus\Documents\N.I.N.A\Images\`.
2. **Transfer** — `scp` from Gaius to this drive at
   `/run/media/vincent/Corrbolg/Astro/Raws/<TargetName>/[YYYY-MM-DD/]{LIGHTS,FLATS}/`.
3. **Process** — Siril `astro_hibou.py` pipeline (calibrate, register, stack,
   recombine, deconv → denoise → star removal, SyQon) → manual GHS stretch (or autostretch for clusters)
   → GIMP (star recomp via starmask, saturation/levels, legend).
4. **Export** — darktable → `~/Images/Photos/Astro/`. Two outputs per image:
   full-resolution master and `-web` resized variant.

### Folder layout under `Raws/`

```
Raws/
├── Calibration/              # master darks per exposure: master_darks_<exp>.fit
├── PHD2/                     # guiding logs
├── Snapshot/                 # ad-hoc captures
├── <TargetName>/             # single-night layout
│   ├── LIGHTS/
│   └── FLATS/
├── <TargetName>/             # multi-night layout
│   ├── YYYY-MM-DD/
│   │   ├── LIGHTS/
│   │   └── FLATS/
│   └── YYYY-MM-DD/...
├── Mosaique <Target>/        # mosaic project root
└── <Target> Panel N/         # individual mosaic panel dirs
```

The Siril script auto-detects which layout it's in (looks for LIGHTS+FLATS first,
falls back to `YYYY-MM-DD` subdirs).

### Output naming convention

`~/Images/Photos/Astro/YYYY-MM-DD_<target>-<mode>[-web].jpg`

`<mode>` is one of: `LRGB`, `SHO`, `HOO`, `HSO`, `OHS`, `Forax`, or other
custom-named variants (`-Custom`, `-CustomAqua`, etc.). `-web` suffix marks the
resized publish-ready version; without it is the full-resolution master.

### darktable export presets

Two presets, both writing JPEG 8-bit at quality 95, 4:4:4 chroma, "Image
parameters" color profile + rendering, applying the **`[Astro] Cadre + Filigrane`**
style (custom darktable style that draws the frame and watermark/signature):

| Variant | Filename pattern           | Size              | Notes                                        |
| ------- | -------------------------- | ----------------- | -------------------------------------------- |
| Master  | `…/Astro/$(FILE_NAME)`     | 0 × 0 (no resize) | Full-resolution output                       |
| Web     | `…/Astro/$(FILE_NAME)-web` | 1920 × 1080 max   | Bounding box; no upscaling, no HQ resampling |

Both: on-conflict overwrite, mode "Add to history". Watermark + frame live in the
style file, not the export preset — edit the style to change either.

### Branding — Astro Hibou

Shared name across the processing script (`astro_hibou.py`) and the watermark
graphic: **"Astro Hibou"** (astro owl). Asset locations:

- **darktable style** (frame + watermark composite):
  `~/.config/darktable/styles/[Astro] Cadre + Filigrane`. Exported `.dtstyle`
  filename has `[`/`]` replaced with `_`.
- **Watermark graphic:** `~/.config/darktable/watermarks/astro_hibou_filigrane.svg`
  (source vector) + `.png` (rendered). Square 2981.81 × 2981.81 px, no text — pure
  graphic. The darktable style references the PNG; swapping the PNG re-skins all
  subsequent exports without touching the style.

**Backup scope reminder:** none of these assets are backed up either. When the
planned NAS / M-Disc setup happens, include `~/.config/darktable/` and
`~/.config/siril/scripts/` in scope alongside Raws/.

### Mosaic processing — `astro_hibou_mosaic.py`

Multi-panel projects process in one run. Lay the panels out as subfolders of a
single project root, each named `… Panel N` (each panel is itself an ordinary
single- or multi-night target with `LIGHTS/` + `FLATS/`, or `YYYY-MM-DD/` night
subdirs):

```
Raws/M8 - M20/            <- launch Siril from here (working directory)
├── Panel 1/              <- LIGHTS+FLATS, or YYYY-MM-DD/ night subdirs
├── Panel 2/
├── …
└── process/             <- mosaic masters + recombined output land here
```

Launch `astro_hibou_mosaic.py` from the project root. It:

1. Discovers `Panel N` subfolders (regex `panel\s*\d+`, case-insensitive), one
   checkbox each; offered recombinations = the filters **every selected panel**
   has (intersection), so the mosaic can't come out with holes.
2. Builds each panel's per-filter masters via the shared
   `Pipeline.build_masters_for_target` (identical calibrate → register → stack →
   per-panel background extraction, all History-cached — re-runs skip finished
   panels).
3. **Color-calibrates each panel with SPCC** (`_spcc_calibrate_panels`,
   broadband R+G+B only) **before** assembling. Panels shot on different nights
   leave `build_masters` with different per-channel scaling — each panel's
   per-filter stack is `-norm=mul` normalized to _its own_ reference frame, so
   the absolute R:G:B ratio (the color) is arbitrary per panel, and that
   intrinsic color **survives the mosaic stack** (measured on M8-M20: R/G varied
   **2.4×**, B/G 2.3× across the 9 panels — panel 4 green, panel 8 red — and the
   visible patchwork matched those panel colors; `overlap_norm` matches panel
   _levels_ per channel at the seams, not cross-channel color). A single global
   SPCC on the assembled patchwork can't fix it. So each panel is calibrated
   independently (`_spcc_one_panel`): the three channel masters are stacked
   independently and differ in size (rgbcomp rejects that), so first
   **co-register** them — `convert` → `seqplatesolve` → `seqapplyreg
-framing=min -interp=area` in a scratch `_spcc_reg/` subdir (WCS-based; masters
   are already solved; **`area` not `lanczos4`** — lanczos overshoots at the
   crop boundary and leaves a bright magenta ringing sliver that shows as a
   colored seam line) — then `rgbcomp` → `color_calibrate` (platesolve → SPCC
   with the Scorpio filters + IMX533 sensor, same as the single-target path) →
   `split` into **new `master_<f>_spcc.fit` files, NEVER over the raw masters**
   (they are the only copy on a no-backup drive and the pristine input a re-run
   needs; `_combine_panels_filter` prefers `_spcc` and falls back to the raw
   master for L and any skipped/failed panel). Validated on M8-M20: panels 4 and
   8 went from R/G 0.77 vs 1.87 (2.4×) to 1.09 vs 1.11 (1.02×). **Caveat:** a
   panel whose blue channel is degenerately small (panel 9's blue stacked to
   2223×2330 vs ~2600 for R/G — a data problem in that panel's blue, worth
   investigating) gets `-framing=min`-cropped to the blue extent, which is
   correct (no valid color where blue is absent) but visibly shrinks that panel.
   **History note:** an earlier version split _over_ the raw masters and
   destroyed them (regenerable from the cached per-night stacks by clearing
   `create_master_channel`/`extract_bg`/`combine_filter_across_days` + downstream
   — done once on 2026-07-05). Every panel then
   sits on the **same absolute color reference** — they match by construction
   _and_ carry physically-correct color (not a relative median). L is left
   untouched (luminance ≠ color). Cached per panel (`spcc_panel`, masters as
   input+output like `manual_crop`); a re-stacked panel re-SPCCs (fresh stack is
   uncalibrated → never double-calibrates). A panel too sparse to solve is
   logged and left uncalibrated rather than sinking the mosaic. **Narrowband
   mosaics are skipped** (false-color palettes). The global SPCC in step 5 still
   runs as a final unifying pass.
4. Assembles the panels of each filter onto one union canvas by **astrometric
   registration**: link the (now color-matched) panel masters → `convert` →
   `seqplatesolve` (reuses each panel's existing WCS) → `seqapplyreg
-framing=max` → mosaic `stack` (`rej none -norm=addscale -output_norm
-overlap_norm -maximize -32b`, plus a `-feather` across the seams;
   `MOSAIC_FEATHER_PX` constant, default 30). `overlap_norm` matches panel
   _levels_ per channel at the seams but **not** cross-channel color — that's
   why step 3 is needed upstream. No further background extraction — each panel
   was already flattened.
5. Recombines (LRGB+SPCC / SHO / …) and — in full mode — continues into
   deconv/denoise/star-removal to the `_STRETCH_ME` checkpoint, exactly like a
   single target. The finished mosaic can then be taken further with
   `astro_hibou_veralux.py`.

The mosaic stack's flag combination (`-overlap_norm`, `-feather`, `-maximize`)
and the plate-solve registration are the parts to eyeball on the first real run;
if a panel lacks a WCS, re-solve with `-force -nocache` in `_combine_panels_filter`.
This supersedes the old workflow (build each panel's masters, then hand-link them
into a `Mosaique …/` folder).

## Gaius helper scripts (`gaius:C:\Users\RBFocus\*.ps1`)

`ssh gaius` lands in **cmd.exe**, not a POSIX shell — there is no `bash`, and
`find` resolves to Windows `FIND.EXE`. Remote helpers are therefore PowerShell
(5.1; no `pwsh`), invoked from fish through `astro_ps <script>`:

| Script                                          | Purpose                                                 | Exit codes                                            |
| ----------------------------------------------- | ------------------------------------------------------- | ----------------------------------------------------- |
| `mount_is_parked.ps1`                           | Read-only park check (never slews)                      | 0 parked · 10 not parked · 2 no driver · 3 no connect |
| `mount_park.ps1`                                | Park + wait on the real `AtPark` signal; idempotent     | 0 ok · 4 park refused · 5 timeout/park-failed         |
| `prune_empty_dirs.ps1`                          | Remove empty dirs left by `rsync --remove-source-files` | 0                                                     |
| `set_guiderate_half.ps1` / `read_guiderate.ps1` | Guide-rate 0.5× set / read                              |                                                       |

All talk to the mount over the **ASCOM `ASCOM.OnStep.Telescope`** COM object
(driver "On-Step" 3.15, firmware OnStep **4.24s**), and only disconnect if they
were the ones who connected — so they are safe to run while N.I.N.A holds the
driver.

**Why park matters: OnStep auto-starts tracking on power-up.** The Gaius powers
the mount, so booting the Gaius to fetch subs starts the RA axis turning. The OTA
still points at the pole (Dec ≈ 89.9°, so Alt/Az barely move) but **the RA axis
walks away from home**. Power the Gaius off in that state and OnStep cold-starts
assuming home — hence the re-sync. Parking stops tracking and writes the position
to NV, so the mount wakes up parked.

Fish wrappers (`~/.config/fish/conf.d/alias.fish`): `astro_mount_parked`,
`astro_mount_park`, `astro_ps`. **`astro_copy` parks before copying** (and warns
but still copies if the park fails); **`astro_sd` parks before shutting down.**

OnStep status word (`:GU#`), the ground truth both scripts assert on:
`n` not tracking · `N` no goto · `p` not parked · `P` parked · `I` parking ·
`F` park failed · `H` at home · `E` GEM · `T`/`W` pier east/west · trailing digits
= pulse-guide rate index, guide rate index, general error. Parked looks like
`nNPR/ET160#`; tracking-from-boot looks like `NpR/ET160#`.

## Operational state

- **Polar alignment:** set-and-forget. Mount stays aligned between sessions; TPPA
  not run per-night.
- **Mount parking:** never power the Gaius off with the mount unparked. `astro_copy`
  and `astro_sd` both park automatically; `astro_mount_parked` checks by hand.
- **Mount site coordinates:** **Valdeblore — 44°04′24″ N, 7°10′03″ E (OnStep
  W-positive: −7°10′), 1060 m.** OnStep stores its own site independently of
  N.I.N.A's profile, and was found on 2026-07-08 still holding the old **Nice**
  values (43°40′/56 m) — which N.I.N.A stamps into every FITS/CSV and uses for
  meridian-flip timing and the online weather feed. Corrected in the OnStep ASCOM
  driver (COM7). **Verified 2026-07-09: the fix survived a power-cycle** — ASCOM
  read back 44.0728 / 7.1669 / 1060 m straight off the mount. N.I.N.A's own
  Astrometry profile is correct. No further action.
- **Master darks:** shot once, currently held over from 2025. Camera settings
  (gain 125, offset 25, −10 °C, 1×1, 120 s / 300 s sub lengths) are stable, so the
  dark library is valid as long as none of those change. Re-shoot triggers: any
  gain/offset/temp/binning change, any sub-length change for which no master exists,
  or sensor noise drift over time.
- **Backup:** **none currently.** The Corrbolg drive is the only copy of Raws/.
  Planned future setup: Blu-ray M-Disc archive for long-term, plus a NAS for
  working storage. Until that's in place, treat single-drive failure as a
  catastrophic loss risk — relevant for any "should I delete X?" decision.

## Audience for written output

Anything for publication (blog posts, captions, presentations) targets the **general
public** — gloss specialized terms on first use. Internal conversation with me can
use full jargon.

## House rules

- **Deletions on this drive: use `gio trash`, not `trash put`.** `trash`
  (trashy) misresolves the mount point of `/run/media/vincent/Corrbolg/…` as
  `/run` and dies trying to create a root-owned `/run/.Trash-1000`
  (`Permission denied (os error 13)`) — it cannot delete anything on Corrbolg.
  `gio trash` handles the topdir correctly and files land in
  `/run/media/vincent/Corrbolg/.Trash-1000/` (created 2026-07-09; restore by
  moving back out of `files/`). Elsewhere `trash put` is still fine. Never
  `rm`.
- **Bad frames are disposed of, never trashed:** move them to the target's
  `<night>/DISPOSED/` folder (see Frame quarantine above). They stay on disk.
- No `cd <dir> &&` prefixes; use absolute paths.
- No compound commands.
- Never dismiss a finding as "pre-existing" — if it's broken, fix it.

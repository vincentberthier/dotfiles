#!/usr/bin/env python3

import re
import shutil
import sys

import sirilpy

sirilpy.ensure_installed("PyQt6", "numpy", "astropy")

from astropy.io import fits
from enum import Enum
from pathlib import Path
from sirilpy import SirilError, CommandError
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QApplication,
    QButtonGroup,
    QCheckBox,
    QGroupBox,
    QHBoxLayout,
    QMessageBox,
    QPushButton,
    QRadioButton,
    QVBoxLayout,
    QWidget,
)

DARK_PATH = "/run/media/vincent/Corrbolg/Astro/Raws/Calibration"
RE_DATE = r"\d{4}-\d{2}-\d{2}"
RE_LIGHTS = r"^([\w -]+)_([\w]+)_([\d\.]+)s_(\d{4})_([\d\.-]+)C_S(\d+)_H([\d\.]+)_R([\d\.]+)_([\d_-]+)\.fits$"
RE_FLATS = r"(FLAT)_([\w]+)_([\d\.]+s)"


class ShootingMode(Enum):
    SHO = (1,)
    RGB = (2,)
    LRGB = 3


FILTER_NAMES = {"S": "sii", "H": "ha", "O": "oiii", "L": "luminance", "R": "red", "G": "green", "B": "blue"}
FILTER_DISPLAY_ORDER = {"L": 0, "R": 1, "G": 2, "B": 3, "S": 4, "H": 5, "O": 6}


def order_filters(filters):
    return "".join(sorted(filters, key=lambda f: FILTER_DISPLAY_ORDER.get(f, 99)))


class Step:
    def __init__(self, data="", cwd="", algo="", step=""):
        self.cwd = cwd
        self.algo = algo
        self.step = step
        if data != "":
            data = data.split(":")
            self.cwd = data[0]
            self.algo = data[1]
            self.step = data[2]

    def __repr__(self):
        return f"{self.cwd}:{self.algo}:{self.step}"

    def __eq__(self, o):
        return self.__hash__() == o.__hash__()

    def __ne__(self, o):
        return not self.__eq__(o)

    def __hash__(self):
        return hash((self.cwd, self.algo, self.step))


class History:
    def __init__(self, path):
        self.file = path / ".history"
        self.steps = set()

        if self.file.exists():
            with open(self.file) as f:
                for line in f:
                    self.steps.add(Step(data=line.replace("\n", "")))

    def check_step(self, cwd, algo, step=""):
        step = Step(cwd=cwd, algo=algo, step=step)
        return step in self.steps

    def complete_step(self, cwd, algo, step=""):
        step = Step(cwd=cwd, algo=algo, step=step)
        self.__add_step(step)

    def __add_step(self, step):
        if step in self.steps:
            return
        self.steps.add(step)
        with open(self.file, "a") as f:
            f.write(f"{step}\n")


class Interface(QWidget):
    def __init__(self, siril, days_list, root_dir):
        super().__init__()
        self.setWindowTitle("Astro-Hibou processing")
        self.setWindowFlags(self.windowFlags() | Qt.WindowType.WindowStaysOnTopHint)

        self.siril = siril

        self.days_list = days_list
        self.history = History(self.cwd())
        self.root_dir = root_dir

        # Widgets that hold user selections
        self.day_checks = {}
        self.option_checks = {}
        self.mode_full = None
        self.mode_partial = None
        self.options_layout = None
        self.options_group = None

        self.setup_ui()
        self.update_option_section()

        self.adjustSize()
        self.setFixedSize(self.size())

    def setup_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(10, 10, 10, 10)

        # Day selection section (only show if more than one day)
        if len(self.days_list) > 1:
            day_group = QGroupBox("Select Days")
            day_layout = QVBoxLayout()
            for day in sorted(self.days_list):
                cb = QCheckBox(day)
                cb.toggled.connect(self.on_day_selection_changed)
                self.day_checks[day] = cb
                day_layout.addWidget(cb)
            day_group.setLayout(day_layout)
            main_layout.addWidget(day_group)
        else:
            # If only one day, auto-select it (the checkbox is not displayed)
            if self.days_list:
                cb = QCheckBox(self.days_list[0])
                cb.setChecked(True)
                self.day_checks[self.days_list[0]] = cb

        # Mode selection section
        mode_group = QGroupBox("Mode Selection")
        mode_layout = QVBoxLayout()
        self.mode_full = QRadioButton("Full")
        self.mode_partial = QRadioButton("Partial")
        self.mode_full.setChecked(True)
        mode_button_group = QButtonGroup(self)
        mode_button_group.addButton(self.mode_full)
        mode_button_group.addButton(self.mode_partial)
        mode_layout.addWidget(self.mode_full)
        mode_layout.addWidget(self.mode_partial)
        mode_group.setLayout(mode_layout)
        main_layout.addWidget(mode_group)

        # Options section
        self.options_group = QGroupBox("Options")
        self.options_layout = QVBoxLayout()
        self.options_group.setLayout(self.options_layout)
        main_layout.addWidget(self.options_group)

        # Buttons section
        button_row = QHBoxLayout()
        button_row.addStretch(1)
        proceed_btn = QPushButton("Proceed")
        cancel_btn = QPushButton("Cancel")
        proceed_btn.clicked.connect(self.on_proceed)
        cancel_btn.clicked.connect(self.on_cancel)
        button_row.addWidget(proceed_btn)
        button_row.addWidget(cancel_btn)
        main_layout.addLayout(button_row)

    def determine_full_spectrum(self, selected_days):
        """Determine if full spectrum based on selected days - placeholder logic"""
        # TODO: Implement your actual logic here
        # Example logic: full spectrum if weekends are selected
        res = []
        filters = set()
        day_filters = [day.split()[1] for day in selected_days]
        for day_filters in selected_days:
            matches = re.findall(r'\[([A-Z]+)\]', day_filters)
            for match in matches:
                filters.update(match)
        if len(filters.intersection(set(["S", "H", "O"]))) == 3:
            res.append(ShootingMode.SHO)
        if len(filters.intersection(set(["L", "R", "G", "B"]))) == 4:
            res.append(ShootingMode.LRGB)
        if len(filters.intersection(set(["R", "G", "B"]))) == 3:
            res.append(ShootingMode.RGB)
        return res

    def update_option_section(self):
        # Clear existing options
        while self.options_layout.count():
            item = self.options_layout.takeAt(0)
            w = item.widget()
            if w is not None:
                w.setParent(None)
                w.deleteLater()
        self.option_checks.clear()

        # Get selected days and determine full spectrum
        selected_days = self.get_selected_days()
        shooting_mode = self.determine_full_spectrum(selected_days)
        self.siril.log(f"available shooting modes are {shooting_mode}")

        # Determine number of options based on full_spectrum condition
        options = []
        if ShootingMode.SHO in shooting_mode:
            self.siril.log("four options")
            options.extend(["SHO", "HOO", "OHS", "HSO", "Forax"])
        if ShootingMode.LRGB in shooting_mode:
            options.append("LRGB")
        if ShootingMode.RGB in shooting_mode:
            options.append("RGB")

        # Create checkboxes for options
        for option in options:
            cb = QCheckBox(option)
            cb.toggled.connect(self.validate_option_selection)
            self.option_checks[option] = cb
            self.options_layout.addWidget(cb)

        self.adjustSize()
        self.setFixedSize(self.size())

    def on_day_selection_changed(self, _checked=False):
        """Called when day selection changes"""
        self.validate_day_selection()
        self.update_option_section()  # Update options based on new day selection

    def validate_day_selection(self):
        """Ensure at least one day is selected"""
        if len(self.days_list) > 1:
            selected = any(cb.isChecked() for cb in self.day_checks.values())
            if not selected:
                # Re-enable the last clicked checkbox if none selected
                # This is a simple approach - you might want to handle this differently
                pass

    def validate_option_selection(self, _checked=False):
        """Ensure at least one option is selected"""
        # if no options, no need to check anything
        if len(self.option_checks) == 0:
            pass
        selected = any(cb.isChecked() for cb in self.option_checks.values())
        if not selected:
            QMessageBox.warning(
                self,
                "Invalid Selection",
                "At least one of SHO, HOO, HSO, OHS must be selected",
            )
            pass

    def get_selected_days(self):
        """Get list of selected days"""
        return [day for day, cb in self.day_checks.items() if cb.isChecked()]

    def get_selected_mode(self):
        """Get selected mode"""
        return "full" if self.mode_full.isChecked() else "partial"

    def get_selected_options(self):
        """Get list of selected options"""
        return [option for option, cb in self.option_checks.items() if cb.isChecked()]

    def is_valid_selection(self):
        """Check if current selection is valid"""
        # At least one day selected
        if not any(cb.isChecked() for cb in self.day_checks.values()):
            return False, "At least one day must be selected"

        # At least one option selected
        if len(self.option_checks) > 0 and not any(
            cb.isChecked() for cb in self.option_checks.values()
        ):
            return False, "At least one option must be selected"

        return True, ""

    def on_cancel(self):
        """Cancel button callback - placeholder"""
        # TODO: Implement cancel logic
        self.close()

    #############################################
    #               Processing                  #
    #############################################

    def on_proceed(self):
        valid, message = self.is_valid_selection()
        if not valid:
            QMessageBox.warning(self, "Invalid Selection", message)
            return

        # Get selections
        selected_days = [day.split()[0] for day in self.get_selected_days()]
        selected_mode = self.get_selected_mode()
        selected_options = self.get_selected_options()
        if len(selected_options) == 0:
            selected_options = ["LRGB"]

        # Placeholder for actual processing
        print(f"Selected days: {selected_days}")
        print(f"Selected mode: {selected_mode}")
        print(f"Selected options: {selected_options}")

        failure = None
        try:
            if len(selected_days) == 1:
                self.process_single_day(selected_days[0], selected_mode, selected_options)
            else:
                self.process_multiple_days(selected_days, selected_mode, selected_options)
        except CommandError as e:
            failure = f"Error running command: {e}"
            print(failure)
        except SirilError as e:
            failure = f"Error initializing script: {e}"
            print(failure, file=sys.stderr)
        except Exception as e:
            failure = f"unknown exception: {e}"
            print(failure)
        finally:
            self.siril.cmd("cd", f'"{self.root_dir}"')

        if failure is None:
            QMessageBox.information(self, "Success", "Processing finished successfully")
        else:
            QMessageBox.critical(self, "Failed to execute", failure)

    def process_single_day(self, day, selected_mode, selected_options):
        start_dir = self.cwd()
        self.siril.log(f"current: {start_dir}, stem: {start_dir.stem}, day = {day}")
        if start_dir.stem != day:
            self.cd(day)

        target_filters = set()
        for option in selected_options:
            filters = option if option != "Forax" else "SHO"
            for filter in filters:
                target_filters.add(FILTER_NAMES[filter])

        self.prepare_flats(target_filters)
        self.prepare_channels(target_filters)

        if selected_mode == "full":
            self.compose(selected_options)
            self.process(selected_options)

        if self.cwd() != start_dir:
            self.cd(start_dir)

    def process_multiple_days(self, selected_days, selected_mode, selected_options):
        start_dir = self.cwd()

        (start_dir / "process") .mkdir(exist_ok=True)

        target_filters = set()
        for option in selected_options:
            filters = option if option != "Forax" else "SHO"
            for filter in filters:
                target_filters.add(FILTER_NAMES[filter])

        filters = set()
        # Prepare the masters for each filters for each day
        for day in selected_days:
            self.cd(day)
            self.prepare_flats(target_filters)
            day_filters = self.prepare_channels(target_filters)
            for filter in day_filters:
                master = start_dir / day / "process" / f"master_{filter}.fit"
                (start_dir / "process" / filter).mkdir(exist_ok=True)
                new_master = start_dir / "process" / filter / f"{day}.fit"
                shutil.copy2(master, new_master)
            filters = filters.union(set(day_filters))
            self.cd("..")

        # Create the overall masters
        for filter in filters:
            filter_dir = start_dir / "process" / filter
            files = [f for f in filter_dir.iterdir() if f.is_file()]
            if len(files) == 1:
                shutil.copy2(files[0], start_dir / "process" / f"master_{filter}.fit")
            else:
                self.cd(filter_dir)
                seq_name = f"{filter}"
                self.siril.cmd("convert", f"pp_{seq_name}", "-out=../")
                self.cd("..")
                self.register_lights(seq_name)
                self.stack_lights(f"r_pp_{seq_name}", 100)
                self.cd("..")

        if selected_mode == "full":
            self.compose(selected_options)
            self.process(selected_options)

        self.cd(start_dir)

    #############################################
    #                 Flats                     #
    #############################################

    def prepare_flats(self, filters):
        self.siril.log("Preparing flats")
        if self.history.check_step(self.cwd(), "prepare_flats"):
            self.siril.log("Step already done, skipping")
            return
        self.cd("./FLATS")
        (filter_files, filter_exposure) = self.get_filter_files_exposure(RE_FLATS)

        for filter_type, files in filter_files.items():
            if filter_type not in filters:
                continue
            self.create_master_flat(filter_type, files, filter_exposure[filter_type])
        self.cd("..")
        self.history.complete_step(self.cwd(), "prepare_flats")

    def create_master_flat(self, filter_type, files, filter_exposure):
        self.siril.log(f"Creating master flat for {filter_type}")
        if self.history.check_step(self.cwd(), "create_master_flat", step=filter_type):
            self.siril.log("Step already done, skipping")
            return
        source_dir = self.cwd()
        dest_dir = source_dir / ".." / "process" / f"flats_{filter_type}"
        if dest_dir.exists():
            shutil.rmtree(dest_dir)
        dest_dir.mkdir(parents=True, exist_ok=True)
        for file in files:
            Path(f"{dest_dir}/{file}").symlink_to(Path(f"{source_dir}/{file}"))
        self.cd(dest_dir)
        self.siril.log("Converting files")
        seq_name = f"flats_{filter_type}"
        self.siril.cmd("convert", seq_name, "-out=../")
        self.cd("..")  # back to process
        self.calibrate_flats(seq_name, filter_exposure)
        self.stack_flats(f"pp_{seq_name}")
        shutil.copy2(
            Path(f"{self.cwd()}/master_pp_flats_{filter_type}.fit"),
            Path(f"{self.cwd()}/master_flats_{filter_type}.fit"),
        )
        self.cd("../FLATS")  # back to FLATS
        self.history.complete_step(self.cwd(), "create_master_flat", step=filter_type)

    def calibrate_flats(self, seq_name, exposure):
        self.siril.log(f"Calibrating {seq_name}")
        if self.history.check_step(self.cwd(), "calibrate_flats", step=seq_name):
            self.siril.log("Step already done, skipping")
            return
        dark = get_dark(exposure)
        self.siril.cmd("calibrate", seq_name, f"-dark={dark}")
        self.history.complete_step(self.cwd(), "calibrate_flats", step=seq_name)

    def stack_flats(self, seq_name):
        self.siril.log(f"Stacking {seq_name}")
        if self.history.check_step(self.cwd(), "stack_flats", step=seq_name):
            self.siril.log("Step already done, skipping")
            return
        self.siril.cmd(
            "stack", seq_name, "rej sigma 2.0 3.0", "-nonorm", f"-out=master_{seq_name}"
        )
        master_name = f"master_{seq_name}.fit"
        self.open_image(master_name)
        self.history.complete_step(self.cwd(), "stack_flats", step=seq_name)

    #############################################
    #                 Lights                    #
    #############################################

    def prepare_channels(self, filters):
        self.siril.log("Preparing lights")
        self.cd("./LIGHTS")
        (filter_files, filter_exposure) = self.get_filter_files_exposure(RE_LIGHTS)
        if self.history.check_step(self.cwd() / "..", "prepare_channels"):
            self.siril.log("Step already done, skipping")
            return filter_files

        for filter_type, files in filter_files.items():
            if filter_type not in filters:
                continue
            self.create_master_channel(filter_type, files, filter_exposure[filter_type])
            self.extract_bg(filter_type)
            self.cd("../LIGHTS")  # back to LIGHTS
        self.cd("..")
        self.history.complete_step(self.cwd(), "prepare_channels")
        return filter_files.keys()

    def create_master_channel(self, filter_type, files, filter_exposure):
        self.siril.log(f"Creating master channel for {filter_type}")
        if self.history.check_step(self.cwd(), "create_master_channel", step=filter_type):
            self.siril.log("Step already done, skipping")
            return
        source_dir = self.cwd()
        dest_dir = source_dir / ".." / "process" / f"{filter_type}"
        if dest_dir.exists():
            shutil.rmtree(dest_dir)
        dest_dir.mkdir(parents=True, exist_ok=True)
        for file in files:
            Path(f"{dest_dir}/{file}").symlink_to(Path(f"{source_dir}/{file}"))
        self.cd(dest_dir)
        self.siril.log("Converting files")
        seq_name = f"{filter_type}"
        self.siril.cmd("convert", seq_name, "-out=../")
        self.cd("..")  # back to process
        self.calibrate_lights(seq_name, filter_type, filter_exposure)
        self.register_lights(seq_name)
        self.stack_lights(f"r_pp_{seq_name}", len(files))
        self.history.complete_step(self.cwd(), "create_master_channel", step=filter_type)

    def calibrate_lights(self, seq_name, filter_type, exposure):
        self.siril.log(f"Calibrating {seq_name} (filter = {filter_type}, exposure = {exposure})")
        if self.history.check_step(self.cwd(), "calibrate_lights", step=filter_type):
            self.siril.log("Step already done, skipping")
            return
        dark = get_dark(exposure)
        if dark:
            self.siril.cmd("calibrate", seq_name, f"-dark={dark}", f"-flat=master_flats_{filter_type}.fit")
        else:
            self.siril.cmd("calibrate", seq_name, f"-flat=master_flats_{filter_type}.fit")
        self.history.complete_step(self.cwd(), "calibrate_lights", step=filter_type)

    def register_lights(self, seq_name):
        if self.history.check_step(self.cwd(), "register_lights", step=seq_name):
            self.siril.log("Step already done, skipping")
            return
        self.siril.cmd(
            "register",
            f"pp_{seq_name}",
            "-transf=homography",
            "-interp=lanczos4",
            "-2pass",
            "-minpairs=10",
        )
        self.siril.cmd("load_seq", f"pp_{seq_name}_")
        self.siril.cmd("seqapplyreg", f"pp_{seq_name}", "-framing=min")
        self.history.complete_step(self.cwd(), "register_lights", step=seq_name)

    def stack_lights(self, seq_name, num_files):
        if self.history.check_step(self.cwd(), "stack_lights", step=seq_name):
            self.siril.log("Step already done, skipping")
            return
        self.siril.log(f"Stacking {seq_name}")
        seq_filter = "-filter-round=2k -filter-wfwhm=2k -filter-nbstars=2k"
        master_name = f"master_{seq_name.replace('r_pp_', '')}"
        if num_files < 15:
            self.siril.cmd(
                "stack",
                seq_name,
                "rej sigma 2.0 3.5",
                "-norm=mul",
                "-weight=wfwhm",
                seq_filter,
                f"-out={master_name}",
            )
        else:
            self.siril.cmd(
                "stack",
                seq_name,
                "rej winsorized 2.0 3.5",
                "-norm=mul",
                "-weight=wfwhm",
                seq_filter,
                f"-out={master_name}",
            )
        self.open_image(f"{master_name}.fit")
        self.siril.cmd("unclipstars")
        self.siril.cmd("platesolve")
        self.siril.cmd("save", master_name)
        self.history.complete_step(self.cwd(), "stack_lights", step=seq_name)

    def extract_bg(self, filter_type):
        if self.history.check_step(self.cwd(), "extract_bg", step=filter_type):
            self.siril.log("Step already done, skipping")
            return
        # bg = self.siril.get_image_pixeldata(shape=[0, 0, 50, 50])
        self.siril.cmd(
            "pyscript",
            "GraXpert-AI.py",
            "-bge",
            "-correction subtraction",
            "-smoothing 0.5",
        )
        # while np.array_equal(self.siril.get_image_pixeldata(shape=[0, 0, 50, 50]), bg):
        #     time.sleep(1)
        self.siril.undo_save_state("GraXpert Background Extraction")
        self.siril.cmd("save", f"master_{filter_type}")
        self.history.complete_step(self.cwd(), "extract_bg", step=filter_type)

    #############################################
    #             Recombination                 #
    #############################################

    def compose(self, options):
        if self.history.check_step(self.cwd(), "compose"):
            self.siril.log("Step already done, skipping")
            return
        self.cd("process")
        self.prepare_compose_sequence(options)
        if "LRGB" in options:
            self.compose_lrgb()
        if "RGB" in options:
            self.compose_rgb()
        if len(set(options).intersection(["SHO", "HOO", "OHS", "HSO", "Forax"])) > 0:
            self.compose_sho(options)
        self.cd("..")
        self.history.complete_step(self.cwd(), "compose")

    def prepare_compose_sequence(self, options):
        if self.history.check_step(self.cwd(), "prepare_compose_sequence"):
            self.siril.log("Step already done, skipping")
            return
        source_dir = self.cwd()
        dest_dir = source_dir / "compose"
        if dest_dir.exists():
            shutil.rmtree(dest_dir)
        dest_dir.mkdir(parents=True, exist_ok=True)

        filter_codes = set()
        for opt in options:
            for code in (opt if opt != "Forax" else "SHO"):
                filter_codes.add(code)

        # Siril's `convert` numbers frames alphabetically by file name, so
        # sorting the symlinked names here gives us the same i+1 ordering
        # that r_compose_seq_NNNNN.fit will be produced in.
        filter_names_sorted = sorted(FILTER_NAMES[c] for c in filter_codes)
        for filter_name in filter_names_sorted:
            (dest_dir / f"{filter_name}.fit").symlink_to(
                source_dir / f"master_{filter_name}.fit"
            )

        self.cd("compose")
        self.siril.cmd("convert", "compose_seq")
        # Astrometric: stack_lights plate-solved every master, so align by WCS
        # rather than star matching across very different histograms (broadband
        # vs narrowband often shares too few detectable stars).
        self.siril.cmd(
            "register",
            "compose_seq",
            "-transf=astrometric",
            "-interp=lanczos4",
        )
        self.siril.cmd("seqapplyreg", "compose_seq", "-framing=min")

        for i, filter_name in enumerate(filter_names_sorted):
            shutil.copy2(
                dest_dir / f"r_compose_seq_{i + 1:05d}.fit",
                source_dir / f"aligned_{filter_name}.fit",
            )
        self.cd("..")
        self.history.complete_step(self.cwd(), "prepare_compose_sequence")

    def compose_lrgb(self):
        if self.history.check_step(self.cwd(), "compose_lrgb"):
            self.siril.log("Step already done, skipping")
            return
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
        self.history.complete_step(self.cwd(), "compose_lrgb")

    def compose_rgb(self):
        if self.history.check_step(self.cwd(), "compose_rgb"):
            self.siril.log("Step already done, skipping")
            return
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
        self.history.complete_step(self.cwd(), "compose_rgb")

    def compose_sho(self, options):
        if self.history.check_step(self.cwd(), "compose_sho"):
            self.siril.log("Step already done, skipping")
            return
        self.open_image("aligned_sii.fit")
        median_s = self.siril.get_image_stats(0).median
        self.open_image("aligned_ha.fit")
        median_h = self.siril.get_image_stats(0).median
        self.open_image("aligned_oiii.fit")
        median_o = self.siril.get_image_stats(0).median

        scale_h = median_s / median_h
        scale_o = median_s / median_o
        self.scale_image("aligned_sii.fit", "scaled_sii.fit", 1.0)
        self.scale_image("aligned_ha.fit", "scaled_ha.fit", scale_h)
        self.scale_image("aligned_oiii.fit", "scaled_oiii.fit", scale_o)

        self.linear_match("scaled_oiii.fit", "scaled_ha.fit")
        self.linear_match("scaled_sii.fit", "scaled_ha.fit")

        target_image = None
        if "SHO" in options:
            self.recomb_sho(["sii", "ha", "oiii"])
            target_image = "sho.fit"
        if "HOO" in options:
            self.recomb_sho(["ha", "oiii", "oiii"])
            target_image = "hoo.fit" if target_image is None else target_image
        if "OHS" in options:
            self.recomb_sho(["oiii", "ha", "sii"])
            target_image = "ohs.fit" if target_image is None else target_image
        if "HSO" in options:
            self.recomb_sho(["ha", "sii", "oiii"])
            target_image = "hso.fit" if target_image is None else target_image
        if "Forax" in options:
            self.recomb_forax()
            target_image = "forax.fit" if target_image is None else target_image

        self.open_image(target_image)
        self.history.complete_step(self.cwd(), "compose_sho")

    def linear_match(self, image, ref):
        self.siril.log(f"image: {image}, ref: {ref}")
        self.open_image(image)
        self.siril.cmd("linear_match", ref, "0 0.92")
        self.siril.cmd("save", Path(image).stem)

    def scale_image(self, source, dest, scale):
        path_source = Path(f"{self.cwd()}/{source}")
        path_dest = Path(f"{self.cwd()}/{dest}")
        self.siril.log(f"--------- path_dest: {path_dest}")
        with fits.open(path_source) as hdul:
            hdul[0].data *= scale
            hdul.writeto(path_dest, overwrite=True)

    def recomb_sho(self, filters):
        if self.history.check_step(self.cwd(), "recompose_sho", step="".join(filters)):
            self.siril.log("Step already done, skipping")
            return
        red = f"scaled_{filters[0]}"
        green = f"scaled_{filters[1]}"
        blue = f"scaled_{filters[2]}"
        output = f"{filters[0][0]}{filters[1][0]}{filters[2][0]}"

        self.siril.cmd("rgbcomp", red, green, blue, f"-out={output}")
        self.history.complete_step(self.cwd(), "recompose_sho", step="".join(filters))

    def recomb_forax(self):
        if self.history.check_step(self.cwd(), "recompose_forax"):
            self.siril.log("Step already done, skipping")
            return
        # Prepare templates
        self.open_image("scaled_ha.fit")
        self.siril.cmd("autostretch")
        self.siril.cmd("save", "TH")
        self.open_image("scaled_oiii.fit")
        self.siril.cmd("autostretch")
        self.siril.cmd("save", "TO")
        self.siril.cmd("close")

        # Pixel math red channel
        self.siril.cmd("pm", "($TO$^~$TO$)*$scaled_sii$ + ~($TO$^~$TO$)*$scaled_ha$")
        self.siril.cmd("save", "forax_red")
        self.siril.cmd("close")

        # Pixel math green channel
        self.siril.cmd("pm", "(($TO$*$TH$)^~($TO$*$TH$))*$scaled_ha$~(($TO$*$TH$)^~($TO$*$TH$))*$scaled_oiii$")
        self.siril.cmd("save", "forax_green")
        self.siril.cmd("close")

        self.linear_match("forax_red", "scaled_oiii")
        self.linear_match("forax_green", "scaled_oiii")

        self.siril.cmd("rgbcomp", "forax_red", "forax_green", "scaled_oiii", "-out=forax")
        self.history.complete_step(self.cwd(), "recompose_forax")

    #############################################
    #               Processing                  #
    #############################################

    def process(self, recombinations):
        self.cd("process")
        current_dir = self.cwd()
        done = []
        for image in recombinations:
            image = image.lower()
            if Path(f"{current_dir}/{image}.fit").exists():
                self.siril.log(f"Processing {image.upper()}")
                self.do_process(image)
                done.append(image)
        for image in done:
            self.siril.log(f"{image.upper()} has been processed, starless and starmask are ready")

    def do_process(self, image):
        if self.history.check_step(self.cwd(), "do_process", step=image):
            self.siril.log("Step already done, skipping")
            return
        self.siril.cmd("load", f"{image}.fit")
        self.siril.cmd("unclipstars")
        self.siril.undo_save_state("Unclipped stars")
        self.siril.cmd("save", f"processing_{image}")
        self.siril.cmd("load", f"processing_{image}.fit")
        self.siril.cmd("starnet", "-stretch", "-upscale")
        self.siril.cmd("load", f"starless_processing_{image}.fit")
        self.deconvolve(image)
        self.denoise(image)
        self.history.complete_step(self.cwd(), "do_process", step=image)

    def deconvolve(self, image):
        self.siril.log("Launching GraXpert Deconvolve")
        if self.history.check_step(self.cwd(), "deconvolve", step=image):
            self.siril.log("Step already done, skipping")
            self.open_image(f"starless_{image}_deconvolved")
            return
        # bg = self.siril.get_image_pixeldata(shape=[0, 0, 50, 50])
        self.siril.cmd(
            "pyscript",
            "GraXpert-AI.py",
            "-deconv_obj",
            "-strength 0.8",
        )
        # while np.array_equal(self.siril.get_image_pixeldata(shape=[0, 0, 50, 50]), bg):
        #     time.sleep(1)
        self.siril.undo_save_state("GraXpert Deconvolve Object")
        self.siril.cmd("save", f"starless_{image}_deconvolved")
        self.open_image(f"starless_{image}_deconvolved")
        self.history.complete_step(self.cwd(), "deconvolve", step=image)

    def denoise(self, image):
        self.siril.log("Launching GraXpert Denoise")
        if self.history.check_step(self.cwd(), "denoise", step=image):
            self.siril.log("Step already done, skipping")
            self.open_image(f"starless_{image}_denoised")
            return
        # bg = self.siril.get_image_pixeldata(shape=[0, 0, 50, 50])
        self.siril.cmd(
            "pyscript",
            "GraXpert-AI.py",
            "-denoise",
            "-strength 0.5",
        )
        # while np.array_equal(self.siril.get_image_pixeldata(shape=[0, 0, 50, 50]), bg):
        #     time.sleep(1)
        self.siril.undo_save_state("GraXpert Denoise")
        self.siril.cmd("save", f"starless_{image}_denoised")
        self.open_image(f"starless_{image}_denoised")
        self.history.complete_step(self.cwd(), "denoise", step=image)

    #############################################
    #                    Utils                  #
    #############################################

    def cwd(self):
        return Path(self.siril.get_siril_wd())

    def cd(self, path):
        self.siril.cmd("cd", f"\"{path}\"")

    def open_image(self, image_name):
        self.siril.cmd("load", f'"{image_name}"')

    def get_filter_files_exposure(self, regex):
        source_dir = self.cwd()
        files = [f.name for f in source_dir.iterdir() if f.is_file()]
        filter_files = {}
        filter_exposure = {}
        for file in files:
            re_match = re.search(regex, file)
            if not re_match:
                continue
            filter_type = re_match.group(2).lower()
            exposure = re_match.group(3)
            filter_files.setdefault(filter_type, []).append(file)
            filter_exposure[filter_type] = exposure
        return (filter_files, filter_exposure)


#############################################
#                  Main                     #
#############################################


def get_dark(exposure):
    res = Path(f"{DARK_PATH}/master_darks_{exposure}.fit")
    if res.exists():
        return res
    return None


def get_available_days(siril):
    current_dir = Path(siril.get_siril_wd())
    siril.log(f"looking for data in {current_dir}")
    folders = [f.name for f in current_dir.iterdir() if f.is_dir()]
    siril.log(f"folders found: {folders}")
    if "LIGHTS" in folders and "FLATS" in folders:
        return [current_dir.stem]

    res = []
    for folder in folders:
        re_match = re.search(RE_DATE, folder)
        if not re_match:
            continue
        res.append(folder)

    return res


def get_shooting_mode(siril, day):
    day_dir = Path(siril.get_siril_wd()) / day / "LIGHTS"
    files = [f.name for f in day_dir.iterdir() if f.is_file()]
    filters = set()
    for file in files:
        match = re.search(RE_LIGHTS, file)
        if not match:
            continue
        filters.add(match.group(2)[0].upper())

    return filters


def main():

    siril = sirilpy.SirilInterface()
    try:
        siril.connect()
        print("Siril connected successfully")
    except sirilpy.SirilConnectionError as e:
        print(f"Failed to connect to Siril: {e}")
        return

    root_dir = Path(siril.get_siril_wd())

    available_days = get_available_days(siril)
    siril.log(f"Found days: {available_days}")

    days = []
    if len(available_days) > 1:
        for day in available_days:
            filters = get_shooting_mode(siril, day)
            days.append(f"{day} [{order_filters(filters)}]")
    else:
        try:
            filters = get_shooting_mode(siril, "")
        except FileNotFoundError:
            filters = get_shooting_mode(siril, available_days[0])
        days.append(f"{available_days[0]} [{''.join(filters)}]")

    try:
        qapp = QApplication.instance() or QApplication(sys.argv)
        qapp.setApplicationName("Astro-Hibou")
        qapp.setStyle("Fusion")
        window = Interface(siril, days, root_dir)
        window.show()
        qapp.exec()
    except CommandError as e:
        print(f"Error running command: {e}")
    except SirilError as e:
        print(f"Error initializing script: {str(e)}", file=sys.stderr)
    except Exception as e:
        print(f"unknown exception: {e}")
    finally:
        siril.cmd("cd", f'"{root_dir}"')


if __name__ == "__main__":
    main()

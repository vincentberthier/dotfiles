#!/usr/bin/env python3
"""Regression: adding widgets must grow the window's size hint, never crush the
last group. Asserts on sizeHint, not pixel geometry — the offscreen Qt platform
does not lay out real geometry ("does not support propagateSizeHints()").
"""
import importlib.util
import os
import sys
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, str(Path(__file__).resolve().parent))

spec = importlib.util.spec_from_file_location(
    "astro_hibou_core", str(Path(__file__).resolve().parent / "astro_hibou_core.py"))
core = importlib.util.module_from_spec(spec)
spec.loader.exec_module(core)

from PyQt6.QtWidgets import (  # noqa: E402
    QApplication, QCheckBox, QGroupBox, QLabel, QPushButton, QVBoxLayout, QWidget,
)

app = QApplication.instance() or QApplication(sys.argv)


def build():
    """Shaped like the real dialog: a group that grows, a tall 'Processing'
    group after it, and pinned buttons outside the scroll area."""
    w = QWidget()
    outer = QVBoxLayout(w)
    content = QWidget()
    inner = QVBoxLayout(content)

    opts = QGroupBox("Options")
    opts_l = QVBoxLayout()
    opts.setLayout(opts_l)
    inner.addWidget(opts)

    proc = QGroupBox("Processing")
    proc_l = QVBoxLayout()
    for i in range(6):
        proc_l.addWidget(QLabel(f"row {i}"))
    proc.setLayout(proc_l)
    inner.addWidget(proc)
    inner.addStretch(1)

    area = core.scrollable(content)
    outer.addWidget(area, 1)
    outer.addWidget(QPushButton("Proceed"))   # pinned outside the scroll area
    core.fit_to_content(w)
    return w, opts_l, proc, content, area


# --- 1. the old bug: setFixedSize locks the window; adjustSize cannot grow ---
w, opts_l, proc, content, area = build()
w.adjustSize()
w.setFixedSize(w.size())
locked = w.height()
for i in range(4):
    opts_l.addWidget(QCheckBox(f"option {i}"))
w.adjustSize()                                  # exactly what the old code did
assert w.height() == locked, "old code should be unable to grow"
assert w.maximumHeight() == locked
print(f"old: locked at {locked} px, adjustSize() cannot grow it  (reproduced)")

# --- 2. fit_to_content releases the lock AND refreshes the stale hints -------
w, opts_l, proc, content, area = build()
before_content = content.sizeHint().height()
before_win = w.sizeHint().height()
proc_hint = proc.sizeHint().height()

for i in range(4):
    opts_l.addWidget(QCheckBox(f"option {i}"))
core.fit_to_content(w)

after_content = content.sizeHint().height()
after_win = w.sizeHint().height()
print(f"new: content hint {before_content} -> {after_content}, "
      f"window hint {before_win} -> {after_win}")
assert after_content > before_content, "nested layout hint went stale"
assert after_win > before_win, "window hint did not follow its content"
assert w.maximumHeight() == core._QWIDGETSIZE_MAX, "window left fixed-size"
assert proc.sizeHint().height() == proc_hint, "Processing group hint shrank"

# the scroll area must track its content, or the window can never grow
assert area.minimumHeight() >= after_content or area.minimumHeight() == int(w.screen().availableGeometry().height()*0.85), (
    f"scroll area min {area.minimumHeight()} < content {after_content}")
print(f"     scroll area minimum {area.minimumHeight()} tracks content")

# --- 3. content taller than the screen is capped, and scrolls ---------------
for i in range(400):
    opts_l.addWidget(QCheckBox(f"filler {i}"))
core.fit_to_content(w)
avail = w.screen().availableGeometry().height()
cap = int(avail * 0.85)
print(f"     400 extra rows: window {w.height()} px, screen cap {cap} px")
assert w.height() <= cap + 1, f"window {w.height()} exceeded cap {cap}"
assert content.sizeHint().height() > cap, "test did not actually overflow"
assert proc.sizeHint().height() == proc_hint, "Processing group crushed on overflow"

print("\nALL ASSERTIONS PASSED")

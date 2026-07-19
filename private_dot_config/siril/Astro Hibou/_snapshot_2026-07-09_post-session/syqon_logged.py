# -*- coding: utf-8 -*-
"""Run a SyQon tool (Parallax / Prism / Starless) as a Siril pyscript while
streaming its stdout/stderr into Siril's *log console* instead of the
pyscript-captured stdout pipe.

Why this exists
---------------
Siril's ``pyscript`` command runs the tool as a child process and captures its
stdout/stderr into a 64 KiB kernel pipe that Siril only drains *after* the
child exits (it sits in ``waitpid``). SyQon's CLI progress prints one
``print(f"…", end="\r")`` per tile with ``PYTHONUNBUFFERED=1``, so on a large
image (e.g. a stitched mosaic) that output overflows the 64 KiB buffer: the
tool blocks writing to a full pipe, Siril blocks waiting for the tool to exit,
and the run deadlocks permanently.

This wrapper removes the stdout pipe from the critical path. It runs the real
tool *in-process* (``runpy``) with fds 1 & 2 redirected onto a private pipe it
drains itself, forwarding every line to ``SirilInterface.log`` — a command sent
over the sirilpy socket, which Siril services live. Result: no pipe can fill,
and the tool's progress shows up in Siril's log as feedback.

Invocation (from astro_hibou_core.py)::

    cmd("pyscript", "syqon_logged.py", "<Tool>.py", *tool_args)

Single connection
-----------------
Siril hands each pyscript child its own single-client socket (``MY_SOCKET``),
so the tool cannot open a *second* connection. This wrapper owns the one
connection and monkeypatches ``sirilpy.SirilInterface`` so the tool's
``main()`` (which does ``s.SirilInterface(); .connect()``) transparently reuses
it. sirilpy serialises commands with an internal lock, so the log-forwarding
thread and the tool's own image I/O share the connection safely.
"""
from __future__ import annotations

import os
import re
import runpy
import sys
import threading
import time
from pathlib import Path

import sirilpy as s

# --- locate the requested SyQon tool -------------------------------------
if len(sys.argv) < 2:
    raise SystemExit("syqon_logged: expected '<Tool>.py [args...]'")

tool_name = sys.argv[1]
tool_args = sys.argv[2:]

_SEARCH_ROOTS = (
    Path.home() / ".local" / "share" / "siril-scripts",
    Path.home() / ".config" / "siril" / "scripts",
)
tool_path = None
for _root in _SEARCH_ROOTS:
    if not _root.is_dir():
        continue
    for _cand in _root.rglob(tool_name):
        if _cand.is_file():
            tool_path = _cand
            break
    if tool_path is not None:
        break
if tool_path is None:
    raise SystemExit(
        f"syqon_logged: could not find {tool_name!r} under "
        + ", ".join(str(r) for r in _SEARCH_ROOTS)
    )

# --- one shared Siril connection -----------------------------------------
# This wrapper is the pyscript child, so it owns the single-client socket.
# Establish the connection, then force the tool to reuse it.
_siril = s.SirilInterface()
_siril.connect()


def _reuse_interface(*_args, **_kwargs):
    return _siril


s.SirilInterface = _reuse_interface          # tool's SirilInterface() -> ours
_siril.connect = lambda *_a, **_k: True       # tool's .connect() -> no-op

# --- redirect the tool's stdout/stderr into Siril's log ------------------
# dup2 fds 1 & 2 (Siril's captured pipe) onto a private pipe drained by a
# reader thread that forwards to _siril.log(). Progress lines that only differ
# by a repeated percentage are throttled so the log isn't flooded.
_saved_out = os.dup(1)
_saved_err = os.dup(2)
_pipe_r, _pipe_w = os.pipe()
os.dup2(_pipe_w, 1)
os.dup2(_pipe_w, 2)
os.close(_pipe_w)

_prefix = f"[{tool_name}] "
_PCT = re.compile(rb"(\d{1,3})\s*%")
_last_line = None
_last_pct = None
_eta_t0 = None      # wall time at the first observed 0 < pct < 100
_eta_p0 = None      # that percentage


def _emit(raw: bytes) -> None:
    global _last_line, _last_pct, _eta_t0, _eta_p0
    if not raw:
        return
    m = _PCT.search(raw)
    suffix = ""
    if m is not None:
        pct = m.group(1)
        if pct == _last_pct:        # same percentage as last -> skip spam
            return
        _last_pct = pct
        # SyQon reports no ETA, so extrapolate one from the average rate
        # since the first percentage seen (resets if progress goes backwards).
        try:
            v = int(pct)
        except ValueError:
            v = -1
        if 0 < v < 100:
            now = time.time()
            if _eta_t0 is None or _eta_p0 is None or v <= _eta_p0:
                _eta_t0, _eta_p0 = now, v
            else:
                rate = (v - _eta_p0) / max(now - _eta_t0, 1e-6)  # %/s
                if rate > 0:
                    rem = int((100 - v) / rate)
                    suffix = f" · ~{rem // 60}m{rem % 60:02d}s left"
    elif raw == _last_line:         # exact duplicate (non-% line) -> skip
        return
    _last_line = raw
    text = raw.decode("utf-8", "replace").strip()
    if not text:
        return
    try:
        _siril.log(f"{_prefix}{time.strftime('%H:%M:%S')}  {text}{suffix}")
    except Exception:
        pass


def _forward() -> None:
    buf = b""
    with os.fdopen(_pipe_r, "rb", buffering=0) as rf:
        while True:
            chunk = rf.read(4096)
            if not chunk:
                break
            # SyQon progress uses '\r'; normal output uses '\n'. Treat both
            # as line breaks so carriage-return progress is forwarded too.
            buf = (buf + chunk).replace(b"\r", b"\n")
            while b"\n" in buf:
                line, buf = buf.split(b"\n", 1)
                _emit(line.strip())
    _emit(buf.strip())              # trailing partial line


_reader = threading.Thread(target=_forward, name="syqon-log-forward", daemon=True)
_reader.start()

# --- run the tool as if it were the pyscript -----------------------------
sys.argv = [str(tool_path), *tool_args]
try:
    runpy.run_path(str(tool_path), run_name="__main__")
finally:
    # Restore fds 1/2 so the private pipe reaches EOF, then let the forwarder
    # flush and finish. join() is bounded because a lingering child (e.g. a
    # multiprocessing resource tracker) may keep the write end open; process
    # exit closes it regardless.
    try:
        sys.stdout.flush()
        sys.stderr.flush()
    except Exception:
        pass
    os.dup2(_saved_out, 1)
    os.dup2(_saved_err, 2)
    os.close(_saved_out)
    os.close(_saved_err)
    _reader.join(timeout=5.0)

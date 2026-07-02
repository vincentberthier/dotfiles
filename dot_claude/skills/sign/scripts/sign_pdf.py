#!/usr/bin/env python3
"""Stamp a signature image (and, by default, the date) onto a page of a PDF.

Builds a transparent single-page overlay PDF — the signature placed at an exact
position with its alpha channel preserved as a PDF soft mask, plus an optional
date drawn in Helvetica — and merges it onto the target page with
`qpdf --overlay`.

Dependencies: Pillow (import PIL) and the `qpdf` and `pdfinfo` binaries. No
network, no other Python packages.
"""

from __future__ import annotations

import argparse
import datetime
import re
import subprocess
import sys
import tempfile
import zlib
from pathlib import Path

from PIL import Image


def die(msg: str) -> None:
    print(f"sign: {msg}", file=sys.stderr)
    sys.exit(1)


def pdf_page_info(pdf: Path) -> tuple[int, float, float]:
    """Return (page_count, width_pts, height_pts) from pdfinfo."""
    try:
        out = subprocess.run(
            ["pdfinfo", str(pdf)],
            check=True,
            capture_output=True,
            text=True,
        ).stdout
    except FileNotFoundError:
        die("`pdfinfo` not found (install poppler-utils)")
    except subprocess.CalledProcessError as e:
        die(f"pdfinfo failed: {e.stderr.strip()}")

    pages = None
    w = h = None
    for line in out.splitlines():
        if line.startswith("Pages:"):
            pages = int(line.split(":", 1)[1].strip())
        elif line.startswith("Page size:"):
            m = re.search(r"([\d.]+)\s*x\s*([\d.]+)", line)
            if m:
                w, h = float(m.group(1)), float(m.group(2))
    if pages is None or w is None or h is None:
        die("could not parse page size from pdfinfo")
    return pages, w, h


def _pdf_string(s: str) -> bytes:
    """Encode a string as a PDF literal string (WinAnsi/latin-1, escaped)."""
    b = s.encode("cp1252", "replace")
    b = b.replace(b"\\", b"\\\\").replace(b"(", b"\\(").replace(b")", b"\\)")
    return b"(" + b + b")"


def build_overlay(sig: Path, page_w: float, page_h: float,
                  x: float, y: float, draw_w: float, draw_h: float,
                  date: str | None, date_x: float, date_y: float,
                  date_size: float) -> bytes:
    """Return bytes of a one-page PDF (size page_w x page_h) with the signature
    drawn at (x, y) sized draw_w x draw_h, and optionally `date` drawn with its
    baseline at (date_x, date_y). Coordinates are PDF points from lower-left."""
    img = Image.open(sig).convert("RGBA")
    iw, ih = img.size
    rgb = img.convert("RGB").tobytes()          # row-major, top-to-bottom
    alpha = img.getchannel("A").tobytes()

    rgb_z = zlib.compress(rgb, 9)
    alpha_z = zlib.compress(alpha, 9)

    parts = [f"q\n{draw_w:.4f} 0 0 {draw_h:.4f} {x:.4f} {y:.4f} cm\n/Im0 Do\nQ\n"
             .encode("ascii")]
    if date:
        parts.append(
            b"BT\n/F1 " + f"{date_size:.4f}".encode("ascii")
            + b" Tf\n0 0 0.35 rg\n"
            + f"{date_x:.4f} {date_y:.4f} Td\n".encode("ascii")
            + _pdf_string(date) + b" Tj\nET\n"
        )
    content_z = zlib.compress(b"".join(parts), 9)

    objs: list[bytes] = []
    objs.append(b"<< /Type /Catalog /Pages 2 0 R >>")
    objs.append(b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>")
    objs.append(
        f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 {page_w:.4f} {page_h:.4f}] "
        f"/Resources << /XObject << /Im0 5 0 R >> /Font << /F1 7 0 R >> >> "
        f"/Contents 4 0 R >>".encode("ascii")
    )
    objs.append(
        b"<< /Length %d /Filter /FlateDecode >>\nstream\n" % len(content_z)
        + content_z + b"\nendstream"
    )
    objs.append(
        (f"<< /Type /XObject /Subtype /Image /Width {iw} /Height {ih} "
         f"/ColorSpace /DeviceRGB /BitsPerComponent 8 /SMask 6 0 R "
         f"/Filter /FlateDecode /Length {len(rgb_z)} >>\nstream\n").encode("ascii")
        + rgb_z + b"\nendstream"
    )
    objs.append(
        (f"<< /Type /XObject /Subtype /Image /Width {iw} /Height {ih} "
         f"/ColorSpace /DeviceGray /BitsPerComponent 8 "
         f"/Filter /FlateDecode /Length {len(alpha_z)} >>\nstream\n").encode("ascii")
        + alpha_z + b"\nendstream"
    )
    objs.append(
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica "
        b"/Encoding /WinAnsiEncoding >>"
    )

    out = bytearray(b"%PDF-1.5\n%\xe2\xe3\xcf\xd3\n")
    offsets = [0]
    for i, body in enumerate(objs, start=1):
        offsets.append(len(out))
        out += f"{i} 0 obj\n".encode("ascii") + body + b"\nendobj\n"

    xref_pos = len(out)
    n = len(objs) + 1
    out += f"xref\n0 {n}\n".encode("ascii")
    out += b"0000000000 65535 f \n"
    for off in offsets[1:]:
        out += f"{off:010d} 00000 n \n".encode("ascii")
    out += (f"trailer\n<< /Size {n} /Root 1 0 R >>\nstartxref\n{xref_pos}\n"
            "%%EOF\n").encode("ascii")
    return bytes(out)


def main() -> None:
    p = argparse.ArgumentParser(description="Add a signature (and date) to a PDF page.")
    p.add_argument("pdf", type=Path, help="input PDF")
    p.add_argument("-s", "--signature", type=Path,
                   default=Path.home() / "Images" / "signature.png",
                   help="signature PNG (default: ~/Images/signature.png)")
    p.add_argument("-o", "--output", type=Path,
                   help="output PDF (default: <input>-signed.pdf)")
    p.add_argument("--page", default="last",
                   help="1-based page number, or 'last' (default: last)")
    p.add_argument("--width", type=float, default=150.0,
                   help="signature width in points (default: 150)")
    p.add_argument("--position", default="bottom-right",
                   choices=["bottom-right", "bottom-left", "bottom-center"],
                   help="anchor for the default placement (default: bottom-right)")
    p.add_argument("--margin", type=float, default=54.0,
                   help="margin from page edges in points (default: 54 = 0.75in)")
    p.add_argument("--x", type=float, default=None,
                   help="explicit X of signature lower-left (points from left); "
                        "overrides --position")
    p.add_argument("--y", type=float, default=None,
                   help="explicit Y of signature lower-left (points from bottom); "
                        "overrides --position")
    # Date options
    p.add_argument("--date", default=None,
                   help="date text to stamp (default: today as DD/MM/YYYY). "
                        "Pass any string to override the format/value.")
    p.add_argument("--no-date", action="store_true",
                   help="do not stamp a date")
    p.add_argument("--date-x", type=float, default=None,
                   help="X of the date baseline (points from left). "
                        "Default: left-aligned with the signature.")
    p.add_argument("--date-y", type=float, default=None,
                   help="Y of the date baseline (points from bottom). "
                        "Default: just above the signature.")
    p.add_argument("--date-size", type=float, default=11.0,
                   help="date font size in points (default: 11)")
    args = p.parse_args()

    if not args.pdf.is_file():
        die(f"input PDF not found: {args.pdf}")
    if not args.signature.is_file():
        die(f"signature image not found: {args.signature}")

    pages, page_w, page_h = pdf_page_info(args.pdf)

    if args.page == "last":
        page_num = pages
    else:
        try:
            page_num = int(args.page)
        except ValueError:
            die(f"invalid --page: {args.page!r}")
        if not 1 <= page_num <= pages:
            die(f"--page {page_num} out of range (document has {pages} pages)")

    with Image.open(args.signature) as im:
        iw, ih = im.size
    draw_w = args.width
    draw_h = draw_w * ih / iw

    if draw_w > page_w or draw_h > page_h:
        die(f"signature ({draw_w:.0f}x{draw_h:.0f}pt) larger than page "
            f"({page_w:.0f}x{page_h:.0f}pt); reduce --width")

    if args.x is not None or args.y is not None:
        x = args.x if args.x is not None else args.margin
        y = args.y if args.y is not None else args.margin
    else:
        y = args.margin
        if args.position == "bottom-left":
            x = args.margin
        elif args.position == "bottom-center":
            x = (page_w - draw_w) / 2
        else:  # bottom-right
            x = page_w - draw_w - args.margin

    if args.no_date:
        date = None
    else:
        date = args.date or datetime.date.today().strftime("%d/%m/%Y")

    # Default date placement: left-aligned with the signature, just above it.
    date_x = args.date_x if args.date_x is not None else x
    date_y = args.date_y if args.date_y is not None else y + draw_h + 6

    output = args.output or args.pdf.with_name(args.pdf.stem + "-signed.pdf")

    overlay = build_overlay(args.signature, page_w, page_h, x, y, draw_w, draw_h,
                            date, date_x, date_y, args.date_size)

    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tf:
        tf.write(overlay)
        overlay_path = Path(tf.name)

    try:
        subprocess.run(
            ["qpdf", str(args.pdf),
             "--overlay", str(overlay_path), f"--to={page_num}", "--",
             str(output)],
            check=True, capture_output=True, text=True,
        )
    except FileNotFoundError:
        die("`qpdf` not found (install qpdf)")
    except subprocess.CalledProcessError as e:
        # qpdf returns 3 for warnings but still writes output; treat as success.
        if e.returncode != 3 or not output.is_file():
            die(f"qpdf failed: {e.stderr.strip() or e.stdout.strip()}")
    finally:
        overlay_path.unlink(missing_ok=True)

    stamped = "signature" + (f" + date ({date})" if date else "")
    print(f"Stamped {stamped} on page {page_num} -> {output}")


if __name__ == "__main__":
    main()

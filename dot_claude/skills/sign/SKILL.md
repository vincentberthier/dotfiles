---
name: sign
description: Add Vincent's handwritten signature (and, by default, today's date) to a PDF. Use whenever the user asks to sign a PDF, add a signature to a document, or runs /sign with a PDF path. Stamps the signature image (default ~/Images/signature.png) plus the date onto a page and writes a new <name>-signed.pdf.
---

# sign

Stamp a handwritten signature image — and, by default, the date — onto a PDF page.

## Usage

The only required argument is the PDF path. The signature defaults to
`~/Images/signature.png`, the date defaults to today (`DD/MM/YYYY`), and the
output defaults to `<input>-signed.pdf` alongside the input.

```
python3 ~/.claude/skills/sign/scripts/sign_pdf.py <input.pdf>
```

Run it, then report the output path to the user.

## Always place it deliberately — and always verify

Do NOT just accept the default corner placement. Real documents (devis,
contracts, forms) have a designated signing area, usually a block like
**"Bon pour accord, le : \_\_\_"** above **"LE CLIENT"** (or "Signature", "Le
gérant", "Fait à … le …"). The signature belongs on that line and the **date
belongs on the "…, le : \_\_\_" blank** — not in the page footer, where the
default lands and overlaps legal text.

Standard workflow:

1. `pdfinfo <pdf>` — page count and page size in points (origin bottom-left).
2. Render the target page to find the signing area and the date blank:
   `magick -density 100 '<pdf>[N-1]' page.png` (N-1 is 0-based). Read it and
   estimate coordinates in points (points = pixels \* 72 / 100 at density 100).
3. Run the script with explicit placement for BOTH the signature and the date
   (see options). Put the date baseline on the "…, le :" line; put the
   signature in the signature block.
4. Render the signed page and read it back to confirm both the signature and
   the date sit correctly, with no overlap and a clean transparent background.
   If anything is off, adjust and re-run — never hand back a bad placement.

## Options

Signature:

- `-o, --output PATH` — output file (default `<input>-signed.pdf`).
- `-s, --signature PATH` — a different signature image.
- `--page N` — 1-based page to sign, or `last` (default `last`).
- `--position bottom-right|bottom-left|bottom-center` — default anchor when no
  `--x/--y` is given (default `bottom-right`).
- `--width PTS` — signature width in points (default 150; height keeps aspect).
- `--margin PTS` — distance from the page edges (default 54 = 0.75in).
- `--x PTS --y PTS` — explicit lower-left of the signature, in points from the
  page's bottom-left corner; overrides `--position`.

Date (on by default):

- `--date STR` — override the text/format (e.g. `--date "2 juillet 2026"` or
  `--date 02/07/2026`). Default is today as `DD/MM/YYYY`. Accented French month
  names render fine.
- `--no-date` — do not stamp any date.
- `--date-x PTS --date-y PTS` — baseline (bottom-left) of the date text. Default
  is left-aligned with the signature, just above it — usually you WANT to set
  these explicitly to land on the "…, le :" blank.
- `--date-size PTS` — date font size (default 11).

The date and signature go on the same page (the `--page` you sign) in one pass.

## How it works

`scripts/sign_pdf.py` builds a transparent one-page overlay PDF sized to the
target page: the signature PNG embedded with its alpha channel preserved as a
PDF soft mask, plus the date drawn in the base-14 Helvetica font (dark blue,
WinAnsi-encoded so accents work). It merges the overlay onto the chosen page
with `qpdf --overlay`. It shells out to `pdfinfo` (page size/count) and `qpdf`
(merge); the only Python dependency is Pillow. No network, no other packages.

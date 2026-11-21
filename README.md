# Variable Font Editor

A local, offline workbench for drafting original letterforms: named font drafts, glyphs with stable IDs and advance widths, a Canvas2D preview with baseline, cap-height and advance guides, and numeric or button point editing. Data is stored in a local SQLite file. Python 3.12 standard library only; no build step.

M1 edits single-master glyph drafts. See the baseline verification below. See [docs/PRD.md](docs/PRD.md) for the full spec.

## Launch

Linux:

```
python3 -m font_editor --data-dir ./data --port 8765
```

Windows:

```
python -m font_editor --data-dir .\data --port 8765
```

Then open http://127.0.0.1:8765/. The server binds 127.0.0.1 only. The data directory is created if missing; an empty path or a path that is a file exits with code 2.

## M1 smoke steps

1. Click **New font**, enter **Font name** `Smoke`.
2. Click **Add fixture glyph**. The readout shows `Advance 500`.
3. Set **Selected glyph width** to `640`. The readout shows `Advance 640`.
4. Choose **Selected point** `P3`, set **Point X** to `300`. P3 is (300, 700).
5. Optionally use **Add glyph** with a **Glyph name** and **Advance width** to add a rectangle glyph.
6. Click **Save**. Status shows `Saved Smoke (version 1)`.
7. Stop the server, start it again with the same `--data-dir`, reload the page, click `Smoke` in the saved list. Width 640 and P3 (300, 700) are restored.
8. Optional: focus the canvas and use the arrow keys to move the selected point by **Step**; hold Shift to move by 1.
9. Resize the window to 800×600; the page should not scroll horizontally.

## Limits

Title 1–60 chars; glyph name 1–24 chars, distinct per font; advance 100–1500; cap height 300–1000; 3–64 integer points per glyph in −1000..2000; one closed polygon contour per glyph; one regular master; ≤128 glyphs per font; ≤200 fonts; request bodies ≤256 KiB. Degenerate (zero-area, duplicate-point) contours are rejected. No TTF/OTF export in M1.

## Persistence

All fonts live in `<data-dir>/fonts.sqlite3`, created with ordered migrations. Saves are transactional with a per-font version; a stale save gets a 409 and the UI keeps your edits.

## Tests

```
python -m unittest discover -s tests -t .      # Windows
python3 -m unittest discover -s tests -t .     # Linux
```

Tests use temporary directories and port 0.

## Expected future scope

Reversible contour commands with curve points; character mapping, kerning and sample text; regular and bold masters with weight interpolation; static and variable TrueType export (using a pinned, locally staged, approved library); revision history and draft recovery; shaping and round-trip regression tests. Details in the PRD.

## Baseline verification

- Windows with Python 3.13.14 and Ubuntu 24.04 WSL with Python 3.12.3 each passed 77 unit and API tests. WSL unit tests used temporary storage on tmpfs.
- Chrome 157 verified the main workflow with external requests blocked. The selected glyph's changed advance width and a keyboard-edited contour point both reopened after a server restart.

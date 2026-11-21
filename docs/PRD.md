# Variable Font Editor — Product Requirements and Technical Spec

Status legend: **[Implemented]** = implemented in M1 (see [baseline verification](../README.md#baseline-verification)); **[Planned]** = future work, not built.

## 1. Intended user and workflow

A design-system author working alone, offline, who wants to iterate on original letterforms and check spacing without a remote design tool.

Workflow: start a named font draft → add glyphs (name + advance width) → adjust the contour points and widths while watching a live preview against baseline, cap-height and advance guides → save locally → close everything → reopen later and find the same data. Later milestones add curves, text layout with kerning, a second master, and font export.

## 2. Scope

### M1 [Implemented]
- Local named font drafts, each with a stable integer ID and a title (1–60 chars, unique case-insensitively).
- Glyphs with stable IDs, a distinct name (1–24 chars) and an integer advance width 100–1500. Editable width.
- One regular master, one closed polygon contour per glyph (3–64 points, straight segments).
- Canvas2D preview with baseline (y=0), cap-height guide, origin line, advance mark, contour and point handles.
- Selected-point editing by numeric X/Y fields and Left/Right/Up/Down buttons (step 1–100, default 10), keyboard arrows on the canvas, click-to-select on the canvas.
- Opt-in "Add fixture glyph" (bundled original outline, advance 500).
- SQLite persistence of fonts, glyphs, geometry and widths; exact reopen after restart.
- Validation of degenerate contours and cap-height data.

### Future milestones [Planned]
See section 8. Order: P1 contour editing commands and curves, P2 mapping/kerning/text layout, P3 regular+bold masters and interpolation, P4 TrueType export, P5 revisions and draft recovery, P6 shaping and round-trip regression.

### Out of scope
TTF/OTF export in M1, user accounts, remote sync, paid services, deployment, real user data, external media or models, import of third-party fonts, hinting, OpenType features beyond kerning, multi-user editing.

## 3. System stack

- Python 3.12 standard library only: `http.server.ThreadingHTTPServer`, `sqlite3`, `json`, `argparse`, `unittest`.
- Static HTML/CSS/native JavaScript served from `font_editor/static/`. No build tooling, no external URLs.
- Launch: `python -m font_editor --data-dir <path> --port <port>` (Windows), `python3 -m font_editor --data-dir <path> --port <port>` (Linux). Binds 127.0.0.1 only.
- Data: `<data-dir>/fonts.sqlite3`.

Modules: `cli.py` (argument and directory checks), `server.py` (routing, security checks, static allowlist), `validation.py` (shape and geometry rules), `storage.py` (migrations, transactions).

## 4. Contracts

### 4.1 Domain limits
| Item | Rule |
|---|---|
| Font title | 1–60 chars, trimmed, no control chars, unique (case-insensitive) |
| Cap height | integer 300–1000, default 700 |
| Glyph name | 1–24 chars, trimmed, no control chars, distinct in font (case-insensitive) |
| Advance | integer 100–1500 (booleans, floats, strings rejected) |
| Points | 3–64 per glyph, integer x,y in −1000..2000 |
| Contour | no equal consecutive points (including last vs first), non-zero shoelace area, non-zero vertical extent |
| Counts | ≤128 glyphs per font, ≤200 fonts |
| Request body | ≤256 KiB |

### 4.2 HTTP API
All JSON UTF-8. Errors: `{"error":{"code","message","details":[{"field","message"}]}}`.

| Request | Success | Errors |
|---|---|---|
| `GET /` | HTML page | |
| `GET /static/app.js`, `/static/styles.css` | static asset | other paths 404 |
| `GET /api/v1/health` | 200 `{"status":"ok","app":"font-editor","api_version":1,"schema_version":1}` | |
| `GET /api/v1/fonts` | 200 list of `{id,title,version,glyph_count,updated_at}` | |
| `POST /api/v1/fonts` | 201 full font | 400 invalid_json, 409 duplicate_title/limit_reached, 411, 413, 415, 422 |
| `GET /api/v1/fonts/{id}` | 200 full font | 404 |
| `PUT /api/v1/fonts/{id}` | 200 full font (full replace, body includes `version`) | 404, 409 stale_version (with `current`), plus POST errors |

Glyph input is `{id?, name, advance, points:[{x,y}]}`; omitted glyphs are deleted on PUT; present IDs are kept.

### 4.3 Schema (migration 1, `PRAGMA user_version`)
`fonts(id, title UNIQUE NOCASE, cap_height, version, created_at, updated_at)` and `glyphs(id, font_id → fonts ON DELETE CASCADE, name NOCASE, advance, points_json, position, UNIQUE(font_id,name), UNIQUE(font_id,position))` with CHECK constraints mirroring the limits above. `PRAGMA foreign_keys=ON`, `busy_timeout=5000` and WAL are set per connection.

### 4.4 UI contract
Labels: **New font**, **Font name**, **Cap height**, **Glyph name**, **Advance width**, **Add glyph**, **Add fixture glyph**, **Selected glyph width**, **Selected point**, **Point X**, **Point Y**, **Left/Right/Up/Down**, **Step**, **Save**. Saved fonts appear as buttons whose text is the title. Status in a polite live region, errors in an alert region, dirty marker "Unsaved changes". Preview readout: `Advance 500 · Cap height 700 · Point P3 (285, 700)`.

### 4.5 Algorithms
- Validation collects all problems (up to 50) with field paths.
- Signed area: `A = ½ Σ (xᵢ·yᵢ₊₁ − xᵢ₊₁·yᵢ)` with wraparound; `A = 0` is degenerate.
- Preview scaling: fit x range `[−100, advance+100]` and y range `[−200, max(cap, maxY)+200]` into the canvas keeping aspect ratio; y flipped.
- Save: one `BEGIN IMMEDIATE` transaction checks `version`, applies the full replace (parking changed names/positions to avoid UNIQUE collisions), increments `version`.

## 5. Deterministic fixtures

**Fixture A** (client constant): name `Fixture A`, advance 500, points (x,y): (30,0), (215,700), (285,700), (470,0), (390,0), (345,160), (155,160), (110,0). Selected point P3 = (285,700).

| Step | Expected |
|---|---|
| Add fixture glyph into font "Smoke" | list entry `Fixture A — 500`, readout `Advance 500` |
| Set Selected glyph width to 640 | readout `Advance 640`, canvas `data-advance="640"` |
| Select P3, set Point X 300 | P3 = (300, 700) |
| Save | status `Saved Smoke (version 1)` |
| Restart server, reload, click `Smoke` | width 640, P3 = (300, 700) exactly |
| Rectangle default glyph, advance 500, cap 700 | points (50,0),(450,0),(450,700),(50,700) |
| Contour (0,0),(100,0),(200,0) | rejected: zero area |
| Contour with 2 points, or cap height 299 / 1001 | rejected |

## 6. Responsiveness, accessibility, errors, concurrency

- ≥720 px: two columns; narrower: stacked. At 800×600 there is no body horizontal overflow.
- Every control has an associated label; visible `:focus-visible`; contrast ≥4.5:1; system fonts; 40 px minimum touch targets; the canvas has `role="img"` with an updating `aria-label` and a text readout.
- User text is rendered with `textContent` only; CSP forbids inline script.
- Errors are recoverable: client validation messages keep typed text; network failure leaves **Save** enabled for retry; fonts-list failure offers **Retry loading fonts**.
- Stale save (409): local edits stay; user chooses **Save my edits over version N** or **Load latest**.
- Concurrent writes: SQLite `BEGIN IMMEDIATE` with a busy timeout; of two simultaneous saves on the same version exactly one succeeds and the other receives 409.
- Restart: all state is in SQLite; nothing is held only in memory.

## 7. Security and validation

Loopback bind only; `Host` must be `127.0.0.1:<port>` or `localhost:<port>`; mutations also check `Origin` and require `application/json`; no CORS headers are sent; static files come from an exact allowlist (no path joining from URLs); request bodies are size-capped before reading; per-connection socket timeout; strict shape/type/length validation; SQL via parameters and CHECK constraints; `no-store`, `nosniff` and a restrictive CSP on every response.

## 8. Future epic: "From single-master glyph drafts to exportable variable fonts"

Exactly one epic. Tickets (the issue text in the repository's backlog file carries the same scope with extended numeric acceptance):

Shared future fixture: glyph **A** = Fixture A mapped to U+0041; glyph **V** mapped to U+0056, advance 600, points (10,700), (110,700), (300,120), (490,700), (590,700), (350,0), (250,0). Bold master: A advance 560 with P3 = (325,700) and all other points equal to regular; V identical to regular. Point IDs are the 1-based point index at creation (P1 introduces them, stored in the point record); each ticket that changes stored geometry adds the next numbered migration in merge order. Duplicate-value conflicts inside a single request use 422; conflicts with already-stored data use 409. Interpolated values round half away from zero (decided).

| Key | Story | Depends on | Headline acceptance |
|---|---|---|---|
| P1 | As an author I can edit contours as reversible commands with on/off-curve points | — | move P3 +15 → (300,700); undo → (285,700); 2-point and all-off-curve contours rejected |
| P2 | As an author I can map characters, add kerning and see sample text | P1 | A=500, V=600, kern −60: V at x=440, width 1040 (1100 without kern) |
| P3 | As an author I can keep regular and bold masters and slide weight | P1 | P3 midpoint (305,700) at weight 550; mismatched contours rejected 422 |
| P4 | As an author I can export static and variable TrueType | P2, P3 | advances 500/600, copyright echoed, weight axis 400–700, renders in a browser and a desktop word processor |
| P5 | As an author I can restore revisions and recover unsaved drafts | P1 | restore v2 → new version 4; 50-revision cap; draft recovery text exact |
| P6 | As an author I get shaping parity and regression coverage | P4, P5 | "AV" advances 440 + 600; round-trip exact at 400/700 |

Dependencies: P4 requires a pinned font-building library. It must be plannable offline, approved by the project owner, staged from a local copy and hash-verified before use; nothing is downloaded at runtime. Exported text and geometry come only from user-authored or generated data.

## 9. Versioning

API under `/api/v1`; schema versioned by `PRAGMA user_version` with ordered, idempotent migrations; a database newer than the code is refused at startup. Per-font `version` integer supports optimistic concurrency. Future additive fields keep `/api/v1`; breaking changes go to `/api/v2`.

## 10. Acceptance matrix (M1)

| # | Requirement | Check |
|---|---|---|
| 1 | Health and HTML served | GET /api/v1/health 200; GET / 200 text/html |
| 2 | Glyph name/width limits | name 0/25 chars and width 99/1501 rejected; 1/24 and 100/1500 accepted |
| 3 | Distinct names | duplicate (case-insensitive) → 422/409 and UI message |
| 4 | Width edit persisted | 500 → 640 survives restart |
| 5 | Geometry exact after restart | points JSON equal before/after |
| 6 | Degenerate contour/cap | rejected with field path |
| 7 | Stale save | 409 stale_version with current; edits kept in UI |
| 8 | Concurrent saves | two threads, one 200, one 409 |
| 9 | Foreign Host/Origin | 403 on mutation |
| 10 | Traversal | `/static/../x`, `%2e%2e` → 404 |
| 11 | Body cap | >256 KiB → 413 |
| 12 | Bad data dir | empty/file path → exit 2, no traceback |
| 13 | Layout | 800×600 no horizontal overflow (manual) |
| 14 | Canvas | preview shows guides and advance mark (manual) |

Rows 1–12 are covered by automated tests under `tests/`; rows 13–14 describe browser checks.

## 11. Sample demo

Start the server on a fresh data dir; New font "Smoke"; Add fixture glyph; width 640; P3 X 300; Save; stop and restart the server; open the page; click "Smoke"; confirm 640 and (300, 700).

## 12. Test plan

`python -m unittest discover -s tests` (use `python3` on Linux): validation unit tests; storage migrations and transactions on temp dirs; HTTP tests against a server on port 0; CLI failure cases. Manual browser smoke per section 11 plus resize to 800×600. Future tickets add their own fixtures as listed in the backlog.

## 13. Open choices

- Which font-building library and exact pinned version for P4 (needs approval and offline staging).
- Whether glyph names should later be constrained to a PostScript-safe character set when export arrives.
- Whether kerning (P2) is per-glyph-pair only or also class-based.
- Which text-shaping approach P6 uses for the "AV" check; it must be offline-stageable and approved, or be reduced to reading the kerning table back and comparing with the P2 layout function.

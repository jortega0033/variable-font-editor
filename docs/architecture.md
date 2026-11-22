# Architecture, baseline status and PRD drift

This file records how the baseline is built, what was checked against the source, and where [PRD.md](PRD.md) and the code differ. It was written during backlog preparation on 2026-11-22 against commit `b18964e` (the only commit on `main`). Line numbers refer to that commit. Update this file in the same pull request as any change that makes a row untrue.

How to read the evidence marks:

- **[RUN]**: the command was run during preparation and the result was seen (Windows 11, Python 3.13.14).
- **[READ]**: established by reading the source only.
- **[NOT VERIFIED]**: a claim in the README or the PRD that was not reproduced.

## 1. Pattern

A single-process, layered application on the Python standard library. No framework, no router library, no build step, no third-party package. The whole font is one document: the client reads it with one GET and replaces it with one PUT.

| Layer | File | Responsibility |
|---|---|---|
| Entry point | `font_editor/__main__.py`, `font_editor/cli.py` | Parses `--data-dir` and `--port` (both required), checks that the data directory exists or can be created and is writable, calls `create_server`, prints `Serving on http://127.0.0.1:<port>/`, serves until Ctrl-C (`cli.py:27-63`). Exit code 2 for a bad data directory or a newer schema, 1 when the port cannot be bound. |
| Transport | `font_editor/server.py` | `Handler` on `ThreadingHTTPServer`: Host and Origin checks, hand-written routing, body reading with a size cap, the JSON error envelope, three allowlisted static files. Calls validation first and storage second. |
| Domain validation | `font_editor/validation.py` | Pure functions over the submitted payload: text, integer and count limits, contour geometry, duplicate names and ids. No I/O. Collects up to 50 problems with field paths. |
| Persistence | `font_editor/storage.py` | SQLite file `<data-dir>/fonts.sqlite3`. One connection per operation; every write is one `BEGIN IMMEDIATE` transaction. Owns the ordered migrations and the optimistic version check. |
| UI | `font_editor/static/index.html`, `styles.css`, `app.js` | Native HTML, CSS and JavaScript. `app.js` is one IIFE with a mutable `state` object, Canvas2D drawing and a copy of the validation rules. No modules, no bundler. |

Tests (`tests/`, 77 tests, standard `unittest`): `test_validation.py` (15) calls `validate_font` directly; `test_storage_cli.py` (13) covers migrations, storage errors and CLI exit codes; `test_api.py` (24) and `test_security.py` (25) drive a real server on port 0 with a temporary data directory and stub static files (`tests/__init__.py:29-60`). There is no test for anything in `app.js`.

## 2. Traced workflow: new font, add the fixture glyph, edit, save, restart, reopen

1. **Start.** `python -m font_editor --data-dir D --port P` runs `cli.main` (`cli.py:27-63`). It rejects an empty path or a path that is a file, creates the directory, proves it is writable with a temporary file, then calls `create_server` (`server.py:337-342`). [RUN: started on a scratch directory; a data directory that is a file gave exit code 2 and a one-line message; a second server on a port in use gave exit code 1]
2. **Storage open.** `Storage.__init__` (`storage.py:75-89`) runs `_migrate` (`storage.py:118-128`): inside one `BEGIN IMMEDIATE` transaction it reads `PRAGMA user_version`, refuses a value above `SCHEMA_VERSION`, and executes the SQL statements of each missing migration. A migration is a list of SQL strings (`storage.py:42-61`). [READ; the refusal of a newer schema is covered by `tests/test_storage_cli.py:43`]
3. **Page load.** `GET /`, `/static/app.js` and `/static/styles.css` are served from the `STATIC_ROUTES` dictionary and nothing else (`server.py:21-25`, `_static` at `214-221`). The HTML response carries the Content-Security-Policy (`server.py:27-30`, `77-78`). The script renders an empty draft and loads the saved-font list (`app.js:787-788`). [RUN: headless Chrome 157 loaded the page, the script ran, and the saved-font list showed a font created over the API; no click was performed]
4. **Edit.** `onAddFixture` (`app.js:502-517`) appends the constant from `app.js:4-8`. `onWidthInput` (`app.js:536-549`), `onPointCoord` (`app.js:551-563`) and `movePoint` (`app.js:575-586`) change the in-memory `state` and call `markDirty` (`app.js:437-440`). Nothing is sent until Save. Point labels `P1..Pn` are the array index plus one (`app.js:275`, `311`). [READ]
5. **Save request.** `save()` (`app.js:641-666`) runs `validateDraft` (`app.js:158-175`), then sends `POST /api/v1/fonts` for a new font or `PUT /api/v1/fonts/{id}` with `version`, built by `buildPayload` (`app.js:616-631`). [READ]
6. **Guards.** `_handle` (`server.py:186-207`) checks, in this order: `Host` must be `127.0.0.1:<port>` or `localhost:<port>` (403 `forbidden_host`); for POST, PUT and DELETE an `Origin` header, when present, must be `http://` plus one of those hosts (403 `forbidden_origin`); then the route. `_read_json` (`server.py:253-287`) requires `application/json` (415), refuses `Transfer-Encoding` and a missing `Content-Length` (411), a malformed length (400), a length over 262144 bytes before reading (413), an incomplete body (400) and invalid JSON or non-finite numbers (400 `invalid_json`). [RUN through the suite: `tests/test_security.py`; the order is READ]
7. **Validation.** `validate_font` (`validation.py:136-195`) checks the title, cap height and each glyph (`_validate_glyph`, `validation.py:87-133`), including `validate_contour` (`validation.py:67-84`): no equal consecutive points including last to first, a vertical extent above zero, and a non-zero shoelace area. Duplicate glyph names are compared with `casefold()` (`validation.py:178-185`). Any problem returns 422 `validation_failed` with `details`. Nothing has been written at this point. [RUN: a three-point collinear contour, a two-point contour and cap heights 299 and 1001 each returned 422 with a field path]
8. **Write.** `create_font` (`storage.py:207-240`) or `replace_font` (`storage.py:242-295`) runs in one transaction. `replace_font` compares the stored version with the submitted one (`storage.py:248-249`; a mismatch raises `StaleVersion` carrying the current font), rejects glyph ids that do not belong to the font (`250-260`), deletes glyphs that were omitted (`264-266`), parks surviving rows on temporary names and positions so that swaps cannot collide with the UNIQUE constraints (`267-272`), writes the final rows and adds 1 to `version` (`286-290`). Points are stored as compact JSON text in `glyphs.points_json` (`_points_json`, `storage.py:68-71`). [RUN: create returned 201 with version 1 and a `Location` header; a PUT with width 640 and P3 x=300 returned 200 with version 2; repeating the PUT with version 1 returned 409 `stale_version` with `current.version` 2]
9. **Result in the UI.** On success the UI adopts the response (`adopt`, `app.js:211-229`), shows `Saved <title> (version N)` and reloads the list. On 409 `stale_version` it keeps the edits and offers **Save my edits over version N** and **Load latest** (`app.js:668-709`). On a network failure it keeps the edits and leaves Save enabled (`app.js:662-665`). [READ]
10. **Restart.** The server holds no state in memory. After stopping and starting it on the same data directory, `GET /api/v1/fonts/1` returned a body equal to the one before the restart, with advance 640 and P3 (300, 700). [RUN]

## 3. Data ownership

- The server and SQLite own every saved font. The schema is in `storage.py:42-57`: `fonts` and `glyphs`, with `glyphs.font_id` cascading on delete.
- The browser owns only the unsaved draft in `state` (`app.js:27-36`). A `beforeunload` handler warns when it is dirty (`app.js:783-785`). Nothing is written to `localStorage` today.
- `fonts.version` is the optimistic-concurrency token. It starts at 1 and rises by 1 per successful replace.
- Glyph ids are assigned by SQLite (`AUTOINCREMENT`), are kept across saves when the client sends them back, and are not reused after deletion (`tests/test_api.py:117`, `210`). Glyph order is the array order of the payload, stored in `glyphs.position`.
- Points have no identity of their own today: a point is `{x, y}` and its label is its position in the array.

## 4. Invariants

| Invariant | Enforced by |
|---|---|
| Font title 1 to 60 characters, trimmed, no control characters, unique without regard to case | `validation.py:43-54`; `_title_taken` with `casefold()` (`storage.py:198-204`); `UNIQUE COLLATE NOCASE` and a length CHECK (`storage.py:45`) |
| Cap height is an integer from 300 to 1000 | `validation.py:156-161`; CHECK (`storage.py:46`) |
| Glyph name 1 to 24 characters, distinct in the font without regard to case | `validation.py:99`, `178-185`; `UNIQUE(font_id, name)` with NOCASE and a length CHECK (`storage.py:52`, `56`) |
| Advance is an integer from 100 to 1500; booleans, floats and strings are rejected | `is_int` (`validation.py:32-33`), `validation.py:100-102`; CHECK (`storage.py:53`) |
| 3 to 64 points per glyph, each coordinate an integer from -1000 to 2000, contour not degenerate | `validation.py:103-131`, `67-84`. The database does not check `points_json`. |
| At most 128 glyphs per font and 200 fonts | `validation.py:167-168`; `storage.py:210-212`. The database does not check either count. |
| A write is all or nothing | `_txn` (`storage.py:103-116`); `tests/test_api.py:151` |
| A stale write changes nothing; of several simultaneous saves on one version exactly one wins | Version check inside the write transaction (`storage.py:245-249`); `tests/test_api.py:164` |
| A database newer than the code is refused and left untouched | `storage.py:121-124`; `tests/test_storage_cli.py:43` |
| Only loopback, same-host clients are served; a foreign `Origin` cannot mutate | Bind address (`server.py:16`, `341`); `_handle` (`server.py:187-196`) |
| Nothing outside three static files is read from disk because of a URL | `STATIC_ROUTES` (`server.py:21-25`); `tests/test_security.py:165` |
| Request bodies over 262144 bytes are refused before they are read | `server.py:15`, `270-273` |
| Every response carries `Cache-Control: no-store`, `X-Content-Type-Options: nosniff`, `Referrer-Policy: no-referrer`; no CORS header is ever sent | `server.py:67-70`; `tests/test_security.py:112` |
| The HTML response carries a CSP that forbids inline script and style and any external source | `server.py:27-30`, `77-78` |

## 5. Status against the PRD

| Capability (PRD section) | Status | Evidence |
|---|---|---|
| Named font drafts with stable ids and unique titles (2, 4.1) | Implemented | [RUN] suite and HTTP probe |
| Glyphs with stable ids, distinct names, advance 100 to 1500 (2, 4.1) | Implemented | [RUN] suite |
| One closed polygon contour of 3 to 64 points, degenerate contours rejected (2, 4.1, 5) | Implemented | [RUN] suite and HTTP probe |
| HTTP API v1: health, list, create, read, replace, error envelope (4.2) | Implemented | [RUN] suite and HTTP probe |
| SQLite persistence and exact reopen after restart (2, 10 rows 4 and 5) | Implemented | [RUN] HTTP probe with a real restart; `tests/test_api.py:191` |
| Stale save answered with 409 and the current font (6, 10 row 7) | Implemented | [RUN] server side; the two buttons in the UI are [READ] |
| Security: loopback bind, Host and Origin checks, body cap, static allowlist, headers (7, 10 rows 9 to 11) | Implemented | [RUN] suite |
| CLI failures exit with code 2 and no traceback (10 row 12) | Implemented | [RUN] suite and one manual case |
| Page loads and the script runs under the CSP | Implemented | [RUN] headless Chrome 157, DOM dump only |
| Canvas preview with guides, point editing by fields, buttons, arrow keys and canvas click, fixture glyph button (2, 4.4) | Implemented in source, needs verification | [READ] `app.js`; README reports a Chrome 157 run of the main workflow [NOT VERIFIED] |
| Layout at 800x600 without horizontal overflow, contrast, focus visibility, touch target size (6, 10 rows 13 and 14) | Needs verification | [NOT VERIFIED]; manual browser checks only |
| Linux and Python 3.12 run (README) | Needs verification | [NOT VERIFIED]; README reports WSL Python 3.12.3 |
| P1 on-curve and off-curve points, reversible commands, stable point ids (8) | Planned, issue #2 | No code |
| P2 character mapping, kerning, sample text (8) | Planned, issue #3 | No code |
| P3 regular and bold masters, weight interpolation (8) | Planned, issue #4 | No code |
| P4 static and variable TrueType export (8) | Planned, issue #5 | No code; no font-building library is approved or staged |
| P5 revisions and draft recovery (8) | Planned, issue #6 | Only the `beforeunload` warning exists (`app.js:783-785`) |
| P6 kerning in the export, regression fixtures, round trip (8) | Planned, issue #7 | No code |

## 6. PRD drift and baseline findings

Each row is a place where a document and the code disagree, or a fact that the documents do not state and a later ticket depends on. None of them was changed during preparation.

| # | Finding | Evidence | Consequence |
|---|---|---|---|
| D1 | The test command in PRD section 12, `python -m unittest discover -s tests`, fails with four import errors. The README form, `python -m unittest discover -s tests -t .`, is the working one. | [RUN] both forms; the test modules use `from . import ...` | Use the README form. Correct PRD section 12 in the next pull request that touches it. |
| D2 | PRD section 8 says the issue text is in "the repository's backlog file". No such file is in the repository: `.prep/` is ignored (`.gitignore:11`) and was never committed. | [READ] | The GitHub issues and the PRD are the only durable backlog. |
| D3 | PRD section 4.3 says CHECK constraints mirror the limits of section 4.1. They cover title length, cap height, version, name length and advance. Point count, coordinate range, contour rules, the glyph and font counts and the control-character rule are enforced only in Python. | [READ] `storage.py:42-57` | A ticket that changes point storage cannot rely on the database to reject bad geometry; the validation tests are the guard. |
| D4 | PRD section 4.2 describes `GET /api/v1/fonts` as returning a list. The body is an object, `{"fonts": [...]}`. | [READ] `server.py:232-233`; `app.js:730` | Wording only. Keep the object shape. |
| D5 | PRD section 7 says mutations check `Origin`. A mutation without an `Origin` header is accepted; only a foreign `Origin` is refused. | [READ] `server.py:191-196` | Intended for non-browser clients such as the tests. A new mutating route must reuse `_handle`, not add its own check. |
| D6 | `DELETE` is listed in `MUTATIONS` (`server.py:33`) but no route accepts it: `DELETE /api/v1/fonts/1` answers 405 with `Allow: GET, PUT`. A font cannot be deleted; a glyph is deleted by leaving it out of a PUT. | [RUN] | Not a defect against the PRD, which lists no delete. Stated here because it surprises readers of the code. |
| D7 | Unknown fields in a payload are ignored without an error. A font posted with `codepoint`, `kerning`, and point `type` and `id` was stored with `x` and `y` only. | [RUN] | Additive fields under `/api/v1` (PRD section 9) are silently dropped by an older server, and a client that omits a new collection on PUT replaces it with nothing. Each ticket that adds a field must say what omission means. |
| D8 | The client copy of the validation rules is not identical to the server rules. The client compares names with `toLowerCase()` and the server with `casefold()`; the client's control-character pattern (`app.js:9`) does not include U+2028, U+2029 or surrogates, which the server rejects (`validation.py:36-40`); the client counts UTF-16 units and the server counts code points (a title of 60 characters outside the Basic Multilingual Plane is accepted by the server). | [READ] client; [RUN] server cases | Harmless today because the server decides and its message is shown. There is no automated check that the two stay aligned. |
| D9 | Glyph names that differ only by Unicode normalisation (U+00E9 and `e` followed by U+0301) are accepted as two glyphs. | [RUN] | Matters when glyph names reach an exported file (PRD section 13, second open choice). |
| D10 | A font at the documented maximums (128 glyphs of 64 points) is valid and its request body is about 170 KiB, inside the 256 KiB cap. With an `id` and a `type` on every point the same font is about 333 KiB, and with a second master about 662 KiB. | [RUN] `validate_font` and measured JSON sizes | The body cap in PRD section 4.1 and the limits in the same table cannot both hold after P1. Issue #2 has to decide (raise the cap or shorten the encoding) and test the largest font. |
| D11 | A migration is a list of SQL strings. Points live in a JSON text column, so adding a field to every stored point needs either a Python step or SQLite JSON functions. The runner supports neither a callable step nor a test of data survival across two schema versions. | [READ] `storage.py:118-128`; `tests/test_storage_cli.py:34` checks only that reopening keeps version 1 | The first ticket that changes stored geometry (#2) must extend the runner. |
| D12 | PRD section 3 says Python 3.12. The suite passed on Python 3.13.14 during preparation; the README reports 3.12.3 as well. | [RUN] 3.13.14; 3.12.3 [NOT VERIFIED] | Treat the requirement as "3.12 or newer". |
| D13 | The README reports a Chrome 157 run of the main workflow with external requests blocked. | [NOT VERIFIED] beyond the page load | Tickets that change the UI must record their own browser run. |
| D14 | PRD section 8 fixes point ids as "the 1-based point index at creation, stored in the point record". Today a point is `{x, y}` and the label `P3` is recomputed from the array position on every render. | [READ] `storage.py:68-71`, `app.js:275` | After P1 a label must come from the stored id, or it will change when a point is inserted before it. |

## 7. Notes for the planned work

These are constraints that follow from the baseline. They are planning notes, not decisions already built.

- **Whole-font replace.** Every save sends the whole font and the server replaces it in one transaction. History (P5), a second master (P3) and kerning (P2) either travel inside that document or add their own routes. Routes that add state must take the font `version` and answer 409 `stale_version` the same way.
- **Static allowlist.** A new static file is not served until it is added to `STATIC_ROUTES` in `server.py`, to `STUBS` in `tests/__init__.py`, and to the checks in `tests/test_security.py` (`test_allowlisted_files_and_types`, `test_real_static_files_when_present`).
- **CSP.** No inline script or style, no external source, `connect-src 'self'`. Script can fetch only from the same origin. The simplest download is a same-origin GET response with `Content-Disposition: attachment`.
- **Body cap tests.** `tests/test_security.py:75-103` hard-code 256 KiB. A cap change updates them and PRD section 4.1 together.
- **One connection per operation.** `Storage` opens a connection for each call (`storage.py:91-101`). Work that needs several statements to be atomic belongs inside one `_txn` block.
- **Rounding.** PRD section 8 fixes interpolation as "round half away from zero". Python's `round()` rounds half to even and JavaScript's `Math.round()` rounds half up, so neither can be used as is for negative coordinates.
- **Export library.** PRD sections 8 and 13 require a pinned font-building library that the owner approves, staged from a local copy and verified by hash, with nothing downloaded at run time. Nothing is approved or staged. This is the only planned work that needs an owner decision before its code can be finished.
- **Browser logic has no test runner.** The standard-library rule covers the tests as well. Logic that exists only in `app.js` (undo and redo, sample-text layout, interpolation for the preview, draft recovery) cannot be checked by `unittest`. The batch has to state, per ticket, which numbers are proved by `unittest` and which by a recorded browser run. Pending the owner decision recorded in epic #1, browser logic may be tested with Node's built-in `node:test` under `tests/js/`, with no package manifest and no npm install. The application never needs Node, and the suite skips these tests with a reason when Node is absent. Nothing of this exists at the baseline: there is no `tests/js/` directory yet, and adding one is planned work. On Node 22 the runner must be given the test files, not the directory: `node --test tests/js` exits 1 with `Cannot find module` (observed with Node v22.23.4 in a scratch directory during preparation).
- **The client keeps only the fields it names.** `normalizePoint` (`app.js:207-209`) keeps `x` and `y`, `adopt` (`app.js:211-229`) keeps a glyph's id, name, advance and points, and `buildPayload` (`app.js:616-631`) sends exactly those. Together with the whole-font replace above, a stored field that these functions do not carry is reset by the next save from the UI. Every planned field (point id and type, code point, kerning, bold master, copyright) has to pass through all three.

## 8. How this was checked

All on 2026-11-22, Windows 11, Python 3.13.14, in a separate worktree at `b18964e`. Every server that was started was stopped, and scratch directories were removed.

| Check | Result |
|---|---|
| `python -m unittest discover -s tests -t .` | `Ran 77 tests in 32.914s`, `OK` |
| `python -m unittest discover -s tests` (PRD form) | 4 import errors, `FAILED (errors=4)` |
| `python -m font_editor --data-dir <scratch> --port 8771`, then HTTP requests from a script | Printed `Serving on http://127.0.0.1:8771/`; health 200 with the documented body; `GET /` 200 `text/html` with the CSP; both static files 200; create 201; replace 200; stale replace 409; restart; the font read back equal |
| Edge requests on the same server | Results are in rows D6, D7, D9 and D10 above; a title with a lone surrogate or U+2028 returned 422; `HEAD /` returned 405 with `Allow: GET`; a 16-digit id returned 404 |
| Headless Chrome 157, `--dump-dom` on `/` at 800x600 | The script ran: readout `No glyph selected · Cap height 700`, canvas sized, saved-font list rendered from the API, alert region empty |

Not run: any click or keyboard path in a browser, the 800x600 overflow check, a contrast check, Linux, Python 3.12.

# CLAUDE.md

Variable Font Editor is a local, offline workbench for drafting letterforms: named font drafts, glyphs with advance widths, one polygon contour per glyph, a Canvas2D preview, saved in SQLite and served to one browser on the loopback interface. The baseline (milestone M1) is built. The epic that takes it to exportable variable fonts (issue #1) is not.

## Commands

Both commands were run on 2026-11-22 on Windows 11 with Python 3.13.14, from the repository root.

| Purpose | Command | Observed |
|---|---|---|
| Test | `python -m unittest discover -s tests -t .` | `Ran 77 tests`, `OK`, about 33 seconds |
| Run | `python -m font_editor --data-dir ./data --port 8765` | Observed with a scratch data directory and other ports (`--port 8771`, `--port 8772`): it printed `Serving on http://127.0.0.1:8771/`. The command as shown, with `./data` and port 8765, is the README form and was not run in that exact form. Open the URL it prints. |

- There is no install step. Python 3.12 or newer is the only requirement. On Windows the interpreter is `python`; on Linux use `python3`.
- Keep `-t .` in the test command. The form printed in `docs/PRD.md` section 12 (without `-t .`) fails with import errors, because the test modules use relative imports.
- `--data-dir` and `--port` are both required. The port must be 1 to 65535; port 0 is available only to tests through `create_server`.
- There is no lint, format, type-check or build command. Do not claim that any of these passed. CI runs only the test suite and the role-gate self-test (see Delivery workflow).
- The Linux and Python 3.12 runs reported in the README were not repeated during preparation.
- Stop every server you start. `data/` and `*.sqlite*` are ignored by Git; use a scratch `--data-dir` for experiments.

## Hard constraints

These come from [docs/PRD.md](docs/PRD.md) sections 2, 3, 7 and 8. Several are enforced by tests.

- Python standard library only for the application and its tests. No pip or npm dependency, no package manifest, no build step.
- One test-only exception, not built yet. Pending the owner decision recorded in epic #1, browser logic may be tested with Node's built-in `node:test` under `tests/js/`, with no package manifest and no npm install. The application never needs Node, and the suite skips these tests with a reason when Node is absent. If the owner decides against Node, the fallback in the first ticket of the epic (issue #8) applies and this bullet is removed.
- The one planned exception is the font-building library for TrueType export (PRD sections 8 and 13). It must be approved by the owner, pinned, staged from a local copy and verified by hash before use. Do not install, download or import one until the owner has approved it. A copy that happens to be installed in your Python environment does not count.
- No external request of any kind at run time: no CDN, web font, remote URL or telemetry.
- The server binds `127.0.0.1` only. Keep the Host and Origin checks, the body cap and the response headers on every new route by routing through `Handler._handle` in `font_editor/server.py`.
- The Content-Security-Policy forbids inline script and style. UI code stays in `font_editor/static/`. A new static file must be added to `STATIC_ROUTES` in `font_editor/server.py`, or it is not served.
- Render user text with `textContent`. Do not build HTML from strings.
- Fonts, glyph outlines and sample data must be original or generated. Do not import third-party fonts or copy outlines from them.

## Sources of truth

| Question | Where to look |
|---|---|
| What the product is, limits, the HTTP API, fixtures, the acceptance matrix, the future milestones P1 to P6 and the open choices | [docs/PRD.md](docs/PRD.md) |
| How the code is layered, the traced save workflow, invariants, what is implemented, planned or unverified, and where the PRD and the code differ | [docs/architecture.md](docs/architecture.md) |
| What to build next and in which order | Epic issue #1 on GitHub and its sub-issues, in the dependency order given in the epic body: #8, #2, #3, #4, #9, #5, #6, #7 |
| What was observed to work at baseline, and on which platforms | [README.md](README.md), "Baseline verification" |

Code and tests show what the product does. The PRD says what it should do. When they disagree, do not pick one silently: add a row to the drift table in `docs/architecture.md` and raise it in the ticket.

## Architecture boundaries

Details and source citations are in [docs/architecture.md](docs/architecture.md). The rules that a change must keep:

- `font_editor/validation.py` is pure: no I/O, no SQLite, no HTTP. Payload and geometry rules live here. New pure logic (text layout, interpolation, export preflight) belongs in pure modules next to it, each testable without a server.
- `font_editor/storage.py` owns SQLite. Each write is one `BEGIN IMMEDIATE` transaction that checks the font `version` first. It trusts that validation already ran. Schema changes are appended to `MIGRATIONS`; never edit a migration that has shipped.
- `font_editor/server.py` owns HTTP: guards, routing, the error envelope and static files. It calls validation first and storage second.
- `font_editor/cli.py` owns arguments, the data-directory checks and the exit codes (2 for a bad data directory or a newer schema, 1 when the port cannot be bound).
- `font_editor/static/` is the whole UI. The server owns all saved state; the browser owns only the unsaved draft.
- The whole font is one document: one GET reads it and one PUT replaces it. A field that the client leaves out of a PUT is gone afterwards, and unknown fields are ignored without an error. A change that adds a field must say what leaving it out means and must test it.
- The client carries a second copy of the validation rules in `app.js`. A rule change is made in both places in the same pull request.

## Git workflow

Observed state at preparation time: `main` is the default branch with one commit, it is not protected, there is no CI and there are no contribution rules in the repository. The rules below are the working defaults until the owner replaces them. CI and branch protection are now in place; see Delivery workflow.

- Never commit to `main` directly. Branch from the tip of `origin/main`, one branch per ticket, named `<type>/<issue-number>-<short-slug>` (for example `feat/2-curve-points`).
- Keep commits small and use the existing subject style (`feat: ...`, `fix: ...`, `docs: ...`, `test: ...`, `chore: ...`).
- Open a draft pull request that names the issue (`Part of epic #1`, `Closes #N`). The owner reviews and merges. Do not merge, force-push or rewrite published history.
- Migrations are numbered in merge order. If another schema change was merged first, rebase and renumber yours before review.
- Do not commit a data directory, a SQLite file, `__pycache__`, an exported font file, a staged library file or a browser report folder.
- A change to behaviour updates the matching PRD section, the acceptance matrix in PRD section 10 and `docs/architecture.md` in the same pull request.

## Evidence before claiming a ticket done

Report only what you ran and saw. For each ticket, capture:

1. The full-suite command and its last lines: `python -m unittest discover -s tests -t .`, with the test count, `OK` and the number of skipped tests with their reasons. The count must not go down.
2. The names of the new tests and the acceptance criteria of the issue that each one covers.
3. For API changes: one request and response for the main case and one for a rejected case, taken from a real server on a scratch data directory, including the status code.
4. For UI changes: the browser and its version, the steps performed, and what the page showed (the status text, the preview readout, the `data-*` attributes on the canvas). Say plainly if no browser run was done. Labels, keyboard operation and the status and alert regions are part of the acceptance criteria (PRD sections 4.4 and 6), not polish.
5. For schema changes: a test or a run that opens a database created by the previous schema version with data in it and shows the data intact.
6. For export changes: the name, version and SHA-256 of the staged library that was used, and the values read back from the exported file.
7. `git status --short` showing no stray files, and confirmation that every server started for the check was stopped.
8. Local evidence comes first: items 1 to 7, then both gates, then the draft pull request. After that, green CI on the pull request (`gh pr checks`), with each job name. Do not mark the pull request ready before CI is green. Reality Checker does not judge CI: it checks items 1 to 7 and that CI is configured to run the documented checks.

State what was not verified. A README or PRD claim that you did not reproduce is a claim, not evidence.

## Project agents and ticket workflow

`.claude/agents/` holds project-local roles copied from Agency Agents at a pinned revision, plus `loop-verifier`, which belongs to the Loop below and takes no part in ticket work. Source paths, licence, local changes, the name collision with a user-level install, and how to check that the roles load are in [.claude/agency-agents/README.md](.claude/agency-agents/README.md).

Each role file starts with a section "In this repository", written for this project: the constraints that bind the role, the files it owns or reviews, its commands, its checklist, the parts of the generic role text that do not apply here, and what it must hand back. That section and this file override the generic upstream text that follows the section in each role file, which was written for larger stacks (frameworks, cloud services, scanners, new dependencies).

When asked to implement, continue or finish a GitHub issue, follow the playbook in [`.claude/skills/implement-ticket/SKILL.md`](.claude/skills/implement-ticket/SKILL.md). Claude Code loads it on its own for ticket work; `/implement-ticket <issue number>` starts it by hand. Delegate to the roles without waiting to be asked: each role's `description` ends with a "Use proactively ..." sentence, which is what makes Claude Code delegate. The playbook has the exact trigger of each role.

- **Before coding:** Codebase Onboarding Engineer (an unfamiliar area) and Software Architect (a change to a module boundary, the data model, the schema, the API or a dependency).
- **While coding:** Backend Architect for `font_editor/*.py`, Frontend Developer for `font_editor/static/`.
- **After coding, when the trigger matches the change:** API Tester (HTTP-level tests in `tests/`), Application Security Engineer and Accessibility Auditor.
- **Gates on every ticket, whatever its size:** Code Reviewer on the full diff, then Reality Checker on the acceptance criteria and the evidence listed above. A ticket is not done until both pass and CI is green on the draft pull request. Run the gates on local evidence before the draft pull request is opened, never skip one to open or ready a pull request.
- Backend Architect, Frontend Developer and API Tester can edit files. The other six are read-only (`tools: Read, Grep, Glob`) and cannot run commands: give them the diff, the acceptance criteria and the recorded command output.
- The session or role that wrote a change does not count as its reviewer.
- List the roles that ran, what each was asked and its verdict in the pull request description under "Agent roles run".

## Delivery workflow

How a ticket gets from the queue to a ready pull request. Each piece has its own file; this part only links them.

- **Start:** the owner types `/next-ticket` ([`.claude/skills/next-ticket/SKILL.md`](.claude/skills/next-ticket/SKILL.md)); that is the go signal, nothing runs on a schedule. It runs one ticket through the [`implement-ticket`](.claude/skills/implement-ticket/SKILL.md) playbook and stops at a ready pull request. The order is fixed: local checks, Code Reviewer, Reality Checker, draft pull request, CI, then ready only on green CI.
- **Labels:** `status:ready`, `status:blocked`, `status:in-progress`, `needs-decision`. Epic issue #1 holds the order.
- **Review gate:** [`.claude/hooks/role_gate.py`](.claude/hooks/role_gate.py) blocks `gh pr create` (draft included) and `gh pr ready` until Code Reviewer and Reality Checker ran after the last code edit. `ROLE_GATE=off` in the environment Claude Code is started from switches it off for that session; only the owner does that.
- **Permissions:** [`.claude/settings.json`](.claude/settings.json). Documented commands are allowed; force pushes, pushes to `main`, `gh pr merge` and releases are denied; edits to CI, agent configuration and Loop files ask first.
- **CI:** [`.github/workflows/ci.yml`](.github/workflows/ci.yml) runs the test command and the gate self-test on Linux and Windows. It runs on the draft pull request and must be green before the pull request is marked ready; a failure means fix, re-run local checks and both gates, push.
- **Pull request:** [`.github/pull_request_template.md`](.github/pull_request_template.md). Add one line under `Unreleased` in [`CHANGELOG.md`](CHANGELOG.md) for every ticket.
- **UI and copy:** [`docs/ui-quality.md`](docs/ui-quality.md) holds the ten UI rules; the `ui-ux-pro-max` and `unslop` skills are used as it describes.
- **Decisions:** [`docs/owner-decisions.md`](docs/owner-decisions.md) records what the owner decided and where it is implemented.
- **Merge and release:** only the owner merges and releases ([`docs/RELEASING.md`](docs/RELEASING.md)). Security reports: [`SECURITY.md`](SECURITY.md).

## Loop

Loop Engineering is set up with the `issue-triage` pattern at L1: report-only and started by hand. It has no scheduler and makes no GitHub writes. See [LOOP.md](LOOP.md) and [loop-constraints.md](loop-constraints.md).

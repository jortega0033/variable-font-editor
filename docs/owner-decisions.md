# Owner decisions

A dated record of the decisions the owner made for this repository, so the rules do not depend on anyone's memory of a conversation. Changing any entry needs the owner. An agent that finds a decision blocking a ticket stops and says so.

Entry 11 of the owner's list (Rust verified in CI only) does not apply here: this repository has no Rust. Numbering below follows the owner's list.

| # | Date | Decision | Implemented in |
|---|---|---|---|
| 1 | 2026-11-22 | The instructions, tooling and playbook live on the default branch (`main`), not on a prep branch. | This commit set, merged to `main`: `CLAUDE.md`, `.claude/`, `.github/`, `docs/` |
| 2 | 2026-11-22 | Persona agents run automatically during ticket work and carry instructions tailored to this project. | `.claude/agents/` ("In this repository" sections and "Use proactively" descriptions), `.claude/skills/implement-ticket/SKILL.md`, `.claude/agency-agents/README.md` |
| 3 | 2026-11-22 | Every open ticket is about app implementation; tooling is installed, not ticketed. | `.github/ISSUE_TEMPLATE/implementation-ticket.md`, `CLAUDE.md` "Delivery workflow" |
| 4 | 2026-11-22 | Agents may take a ticket up to a ready pull request. Only the owner merges and releases. | `.claude/skills/next-ticket/SKILL.md`, `.claude/settings.json` (deny `gh pr merge`, releases), `docs/RELEASING.md`, `.github/CODEOWNERS` |
| 5 | 2026-11-22 | No scheduler. Ticket work starts only on the owner's go signal (`/next-ticket`), because the repository is used to train AI models. | `.claude/skills/next-ticket/SKILL.md` (`disable-model-invocation: true`), `LOOP.md` |
| 6 | 2026-11-22 | A review gate hook blocks opening or readying a pull request until the gate roles have run after the last code edit. | `.claude/hooks/role_gate.py`, `.claude/settings.json` (`hooks`), `.gitignore` (`.claude/state/`) |
| 7 | 2026-11-22 | Loop Engineering stays at L1, report-only and unscheduled. | `LOOP.md`, `loop-constraints.md`, `loop-budget.md` |
| 8 | 2026-11-22 | Continuous integration runs on Linux and Windows; the default branch requires a pull request and green checks. | `.github/workflows/ci.yml`; branch protection is set by the owner's orchestrator on GitHub, not in the repository |
| 9 | 2026-11-22 | Permission rules: documented commands are allowed; force pushes, pushes to the default branch, merges, releases and reads of secrets are denied; edits to CI, agent configuration and Loop files ask first. | `.claude/settings.json` (`permissions`) |
| 10 | 2026-11-22 | Open decisions on tickets are settled with the ticket's stated default; where a ticket states none, the conservative option is taken and flagged in the issue. See the list below. | Issues #1, #2, #8 and #9 on GitHub; this file |
| 12 | 2026-11-22 | The ten UI rules in `docs/ui-quality.md` are binding, and the `ui-ux-pro-max` and `unslop` skills are installed in the repository and used for UI work and for copy. | `docs/ui-quality.md`, `.claude/skills/ui-ux-pro-max/`, `.claude/skills/unslop/`, `.claude/skills/implement-ticket/SKILL.md` |

## Entry 10: decisions settled by default

| Issue | Decision | Settled by | Note |
|---|---|---|---|
| #8 (epic #1) | Node as an optional, test-only tool for browser logic tests (`node:test` under `tests/js/`, no npm, skipped when Node is absent). | Stated default: yes. | The application never needs Node. |
| #9 (epic #1) | Which font-building library and exact version to approve for export. | The ticket names fontTools (MIT) as a candidate but states no approval. Conservative option: approve nothing, keep the pin empty (`unpinned`). | Flag in issue. Only item 6 of #9 waits; #5 and #7 wait for the real pin. Agents do not install, download or import a library. |
| #2 (epic #1) | Undo and redo cover only the contour and advance commands (move, insert, delete, retype a point, change the advance). | Stated default for the batch: the narrower scope. | The owner can widen it, which adds work to #2, #3 and #4. |

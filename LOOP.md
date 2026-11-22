# Loop Configuration: Issue Triage

Scaffolded with `npx --yes @cobusgreyling/loop@0.2.0 init . --pattern issue-triage --tool claude` ([Loop Engineering](https://github.com/cobusgreyling/loop-engineering), MIT). The generated `.grok/` and `.codex/` variants were removed; this repository uses the Claude Code files only. The scaffold generated no workflow file, and none was added.

## Active Loops

| Pattern | Cadence | Status | Command |
|---------|---------|--------|---------|
| Issue Triage | Manual, on request | L1 report-only | `/issue-triage` in a Claude Code session at the repository root |

## Operating level: L1 report-only

- The loop reads open issues with `gh issue list` and `gh issue view` and rewrites `issue-triage-state.md`. That file and `loop-run-log.md` are the only files it may change.
- It never applies labels, comments, closes or edits issues, edits source or tests, commits, pushes, opens pull requests or merges.
- No scheduler is configured. Do not wrap the skill in `/loop`, a cron entry, a scheduled task or a GitHub workflow. The "2h" cadence in the generated skill text describes the upstream pattern, not this repository.
- `loop doctor` prints its own readiness score. That score describes the scaffold, not the operating level. The operating level here stays L1 until the owner changes this file.

## Ticket work is not a loop run

Implementing backlog tickets is not a run of this loop. The owner starts it with `/next-ticket`, and it is governed by `CLAUDE.md`, the `implement-ticket` playbook, the review gate hook, CI and branch protection. The loop stays report-only and unscheduled at L1.

## Next manual triage run

From the repository root, in a new Claude Code session:

```text
/loop-constraints
/issue-triage
```

Headless equivalent:

```text
claude -p "Run the loop-constraints skill, then the issue-triage skill in L1 report-only mode. Update issue-triage-state.md and append one entry to loop-run-log.md. Make no GitHub writes and change no other file."
```

Review the diff of `issue-triage-state.md` afterwards. Committing it is a human decision.

## Health checks

```text
npx --yes @cobusgreyling/loop@0.2.0 doctor .
npx --yes @cobusgreyling/loop@0.2.0 status .
```

Observed on 2026-11-22 in the preparation worktree with the loop files committed: `doctor` printed `Ready: 100/100 L3` and `Status: HEALTHY (exit 0)`; `status` printed `Pattern: issue-triage`, `State: issue-triage-state.md · not yet run`, and exited 0. The `L3` in that output is the scaffold's readiness score, not the operating level.

Doctor exit codes: 0 healthy, 1 warnings, 2 blocked. These two commands need Node and network access to npm. They are maintenance tools for the loop files, not part of the product, which stays offline and standard-library only.

## Human Gates

- Priority assignment (P0, P1): human only.
- Anything touching the request guards in `font_editor/server.py` (Host, Origin, body cap, static allowlist, security headers), the SQLite schema or its migrations, the public JSON API, or the choice and staging of the font-building library for export: always escalate.
- Duplicate closure: human confirms.
- Stale issue closure: human confirms.
- Any change to this file, `loop-budget.md` or `loop-constraints.md`: human only.

## Verifier

`.claude/agents/loop-verifier.md` is the checker for a later maker/checker level. It is limited to `Read, Grep, Glob`, so it cannot run the tests itself and must answer `ESCALATE_HUMAN` when a verdict depends on a test run. It has no role at L1 because the loop proposes no changes.

## Budget

- Sub-agent spawns per run: 0 at L1.
- See `loop-budget.md`.

## MCP

MCP is not required for this pattern. The triage skill reads issues through the `gh` command line.

## Doctor suggestions that were not adopted

`loop doctor` may also suggest a `docs/safety.md`, issue and pull request templates, and workflows. They were left out on purpose: the denylists and merge policy are in `loop-constraints.md`, and a workflow would be the scheduler that L1 excludes.

## Links

- Pattern: https://github.com/cobusgreyling/loop-engineering/blob/main/patterns/issue-triage.md
- Repository instructions: [CLAUDE.md](CLAUDE.md)
- Backlog source of truth: [docs/PRD.md](docs/PRD.md) and the epic issue (#1)

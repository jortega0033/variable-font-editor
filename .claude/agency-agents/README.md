# Agency Agents roles used in this repository

The Markdown files in `.claude/agents/` whose names start with `engineering-`, `testing-` or `security-` are copies of role definitions from Agency Agents. They are project-local Claude Code subagents. The file `loop-verifier.md` in the same folder is not from Agency Agents; it belongs to the Loop Engineering setup described in [`LOOP.md`](../../LOOP.md).

## Source and licence

- Upstream: https://github.com/msitarzewski/agency-agents
- Pinned revision: `8ae6164602c95ca78828b148b9052460ee426885` (upstream `main`, committed 2026-11-09)
- Licence: MIT, "Copyright (c) 2025 AgentLand Contributors". The upstream licence text at the pinned revision is kept unchanged in [`LICENSE`](LICENSE) next to this file (SHA-256 `9a45258434d5cedf0af73c9ad4771373701225038d246c49219026c33677f66f`). It covers only the copied role files, not the rest of this repository.
- Fetched with `gh api -H "Accept: application/vnd.github.raw" "repos/msitarzewski/agency-agents/contents/<path>?ref=<revision>"`.

## Installed roles

"Upstream SHA-256" is the hash of the file as fetched at the pinned revision (LF line endings, as stored in Git). Reviewer roles have one added frontmatter line, `tools: Read, Grep, Glob`, so they cannot edit files or run commands. Nothing else in any file was changed.

| File in `.claude/agents/` | `name:` | Upstream path | Upstream SHA-256 | Local change |
|---|---|---|---|---|
| `engineering-software-architect.md` | Software Architect | `engineering/engineering-software-architect.md` | `b85121691776147bacde26673e68fbbacd6a7f0816d1ca8e203c264d25ce1d30` | added `tools: Read, Grep, Glob` |
| `engineering-code-reviewer.md` | Code Reviewer | `engineering/engineering-code-reviewer.md` | `7509fcc3ea1dda46511b2801996305bf3d4a125576f9655ff0b63df25602f446` | added `tools: Read, Grep, Glob` |
| `engineering-codebase-onboarding-engineer.md` | Codebase Onboarding Engineer | `engineering/engineering-codebase-onboarding-engineer.md` | `07aa548b45887c3ad768efad5fdbf6e57bea639df4f1b74c7e383142f454e2a1` | added `tools: Read, Grep, Glob` |
| `testing-accessibility-auditor.md` | Accessibility Auditor | `testing/testing-accessibility-auditor.md` | `362935907af23839775b9c6162f38c0c5a740542ab4350cb5c5b5a0d9f9a4268` | added `tools: Read, Grep, Glob` |
| `testing-reality-checker.md` | Reality Checker | `testing/testing-reality-checker.md` | `6d32fcdb114233e13902ec6372d50293b120e85d490b5e81d372c29808f988a1` | added `tools: Read, Grep, Glob` |
| `security-appsec-engineer.md` | Application Security Engineer | `security/security-appsec-engineer.md` | `a19f0bda46f4adca5737365dbc3c7ed93e9d93b71349536d92ff055dcf4e3b83` | added `tools: Read, Grep, Glob` |
| `engineering-backend-architect.md` | Backend Architect | `engineering/engineering-backend-architect.md` | `ac717bde4848d7663fff8a3c7edc711fd119256de6a7ce38c036619372f42c99` | none |
| `engineering-frontend-developer.md` | Frontend Developer | `engineering/engineering-frontend-developer.md` | `1ae4cc10b2e0163bd3ed921ad54080b865cd02e591becd8919b64b73fab06dad` | none |
| `testing-api-tester.md` | API Tester | `testing/testing-api-tester.md` | `ab91de9188d48bd9c417282c33673a37b066215e90e08c0f1b270d036084e3bb` | none |

## Why these roles

| Role | Use in this repository |
|---|---|
| Software Architect (read-only) | Review a ticket's design against the layering in [`docs/architecture.md`](../../docs/architecture.md) before code is written: the point and master data model, the migration runner, where layout, interpolation and export code lives, how a new route fits the whole-font replace model. |
| Code Reviewer (read-only) | Review a diff for correctness, missed edge cases and broken invariants (version check, validation before write, request guards on new routes, rounding rule). |
| Codebase Onboarding Engineer (read-only) | Trace a code path and report facts with file and line citations. |
| Accessibility Auditor (read-only) | Review keyboard operation, focus handling, labels, the text alternative to the canvas, and the status and alert regions. PRD sections 4.4 and 6 make these requirements. |
| Reality Checker (read-only) | Compare claimed evidence with what was actually run before a ticket or the final regression gate is called done. |
| Application Security Engineer (read-only) | Review changes to the request guards, the static allowlist, download responses, and above all the staging and hash verification of the export library (PRD sections 7 and 8). |
| Backend Architect | Implement work in `font_editor/*.py` (HTTP layer, storage and migrations, validation, layout, interpolation, export). |
| Frontend Developer | Implement work in `font_editor/static/`. |
| API Tester | Write the HTTP-level `unittest` cases in `tests/` for new and existing routes. |

The role texts are written for larger stacks (frameworks, cloud services, scanners, Postman, k6, Playwright). In this repository the rules in [`CLAUDE.md`](../../CLAUDE.md) win: Python standard library only, native HTML, CSS and JavaScript, `unittest`, no pip or npm dependencies, no external requests.

Roles that were considered and left out: Test Automation Engineer and Evidence Collector (browser automation needs a dependency this repository does not allow), Tool Evaluator (written for business software selection; the one library decision in the backlog belongs to the owner), Database Optimizer (one small SQLite file, no query tuning in the backlog).

## Name collision with user-level agents

A developer who has installed Agency Agents in `~/.claude/agents/` already has agents with the same `name:` values. Claude Code gives the project-level definition precedence, so inside this repository the copies here are used, including the read-only tool limits. The upstream names were kept on purpose so that the roles stay recognisable and can be compared with upstream.

A Claude Code session that was already running when these files were added keeps the definitions it loaded at start. Start a new session to pick up the project copies.

## Check that the roles load

From the repository root, in a new session:

```text
claude -p "List the project-level subagents defined in .claude/agents with the tools each one may use. Then run the Reality Checker subagent and ask it which tools it has."
```

The six reviewer roles and `loop-verifier` must report exactly `Read, Grep, Glob`.

### What was observed, and what was not

Observed on 2026-11-22 with Claude Code 2.1.323, headless (`claude -p --model haiku`, no MCP servers), from the repository root, on a machine that also has a user-level Agency Agents install:

- All ten names were listed. Software Architect, Code Reviewer, Codebase Onboarding Engineer, Accessibility Auditor, Reality Checker, Application Security Engineer and `loop-verifier` were listed with `Read, Grep, Glob`. Backend Architect, Frontend Developer and API Tester were listed with all tools.
- A launched Reality Checker, a launched Application Security Engineer and a launched `loop-verifier` each reported exactly `Read`, `Grep`, `Glob`. The user-level copies of the reviewer roles have no `tools:` line, so the project copies were the ones loaded.
- **Not shown:** which copy of the three implementing roles was loaded. They are unchanged from the pinned upstream and have no tool limit, and the listing gives names and tools only, not the file a definition comes from. Claude Code's documented precedence says the project copy wins; that was not demonstrated for these three here.
- **Not shown:** behaviour in an interactive session, and behaviour on a machine without a user-level install (there the ten names must simply be listed).

## Updating

Fetch the same paths at a newer revision, re-apply the `tools:` line to the six reviewer roles, and update the revision and hashes in this file in the same commit.

## Local change: automatic delegation (2026-11-22)

One sentence beginning "Use proactively" was appended to the `description:` line of every Agency Agents role in `.claude/agents/` (not to `loop-verifier`). Claude Code uses that field to decide when to delegate, so the roles now run during ticket work without being named. Nothing else in the role files changed.

This supersedes any statement above that a role file is unmodified or that the `tools:` line is the only local change. To compare a role with the pinned upstream file, remove that sentence (and the `tools:` line where one was added) first.

The steps at which each role runs are in `.claude/skills/implement-ticket/SKILL.md`.

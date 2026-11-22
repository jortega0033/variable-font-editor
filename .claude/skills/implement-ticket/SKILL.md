---
name: implement-ticket
description: Playbook for implementing a GitHub issue in this repository from start to pull request, with the project subagents run at fixed steps. Use whenever asked to implement, start, continue or finish a ticket, an issue or an epic child, for example "implement #12" or "work on the next ticket".
argument-hint: "[issue number]"
---

# Implement a ticket

Use this playbook for every implementation ticket in this repository. `CLAUDE.md` holds the commands, the architecture boundaries, the Git workflow and the evidence rules; where this playbook and `CLAUDE.md` differ, `CLAUDE.md` wins.

The project subagents in `.claude/agents/` are part of the work. Delegate to them at the steps below without waiting to be asked. If a step names a role that is not installed, do that step yourself and say so in the pull request.

## Steps

1. **Read the ticket.** `gh issue view <number>` and the epic it belongs to. Check that every prerequisite issue is closed. An open owner decision blocks only what the ticket says it blocks: #8 states a default to build with (recorded in `docs/owner-decisions.md`), and #9 says which of its items wait for the decision. Work only on a leaf ticket: a `tracking` ticket or one with open sub-issues is a container, so take its first ready sub-issue instead. If the ticket, or the part you were asked for, is blocked, stop and say what blocks it.
2. **Read the rules.** `CLAUDE.md`, then the architecture notes it links to.
3. **Orient and check the approach.** Delegate as the table "Before coding" says. For a UI ticket, start with the `ui-ux-pro-max` skill (design-system search for the product type) and read `docs/ui-quality.md`. Settle open design questions before writing code.
4. **Branch** as the Git workflow in `CLAUDE.md` says. Never work on the default branch.
5. **Implement** inside the ticket's stated scope. Delegate the work to the implementing role that matches the files being changed (table "While coding"). Do not widen scope; note anything else you find as a follow-up.
6. **Test.** Add or change tests for every acceptance criterion and material edge case, then run the checks listed in `CLAUDE.md`. Record each command and its result.
7. **Specialist review.** Run every role in the table "After coding" whose trigger matches the change. For a UI ticket, check each changed screen against the ten rules in `docs/ui-quality.md` and note the result for the pull request.
8. **Finalize the diff.** Add one line under `Unreleased` in `CHANGELOG.md`. Run the `unslop` skill over user-facing copy, documentation and the pull request text. The gates must judge the final diff, so nothing that changes it comes after them.
9. **Review gate, always.** Write the diff and the local evidence to `.claude/state/review/` (`git diff --stat origin/main...HEAD`, `git diff origin/main...HEAD`, each check output) because the reviewers have no shell, and name those files in the request. Run Code Reviewer on the full diff. Fix every material finding, re-run the checks, and have the reviewer look again until no material finding is left.
10. **Acceptance gate, always.** Run Reality Checker with the ticket's acceptance criteria and the local evidence you produced (items 1 to 7 of `CLAUDE.md`). It checks that the documented checks were run locally and passed and that CI is configured to run them; do not ask it to confirm a CI result. Do not open a pull request unless it passes. A criterion that needs a person (marked manual in the ticket, such as a hand check in a normal browser) is done as far as an agent can, with the evidence, and the rest is listed under "Owner checks" in the pull request; Reality Checker accepts that only when the ticket marks the step as manual.
11. **Hand off.** Capture the evidence `CLAUDE.md` asks for. Only after both gates passed on the final code, open a draft pull request from `.github/pull_request_template.md` that names the issue. CI runs on the draft; if it fails, fix, re-run the local checks and both gates, and push. Do not poll: after the push, end the turn with "Draft pull request #N is waiting for CI" and read `gh pr checks` once when woken. When CI is green, mark it ready (`gh pr ready`). If this is the last open sub-issue of a parent, the pull request also says `Closes #<parent>`. Never change agent configuration (`.claude/agents`, `skills`, `hooks`, `settings.json`) inside a ticket. Never open or mark ready a pull request with a gate not run. Only the owner merges: do not merge.

## Roles

### Before coding

| Role | Access | Delegate to it |
|---|---|---|
| Codebase Onboarding Engineer | read-only reviewer | At the start of a ticket in an unfamiliar area, to trace the relevant code paths before anything is changed |
| Software Architect | read-only reviewer | Before implementing a ticket that adds or changes a module boundary, data model, storage schema, public API or dependency, to check the approach against the architecture notes |

### While coding

| Role | Access | Delegate to it |
|---|---|---|
| Backend Architect | can edit | When a ticket changes server-side code, HTTP routes, validation, persistence or data migrations |
| Frontend Developer | can edit | When a ticket changes browser-side code such as pages, components, client state, styling or keyboard interaction |

### After coding

| Role | Access | Delegate to it |
|---|---|---|
| Application Security Engineer | read-only reviewer | After a ticket touches input parsing, file upload or import, sanitization, origin and host checks, or any handling of untrusted data |
| Accessibility Auditor | read-only reviewer | After a ticket changes user-facing UI, keyboard handling, focus order or markup |
| API Tester | can edit | After a ticket adds or changes an HTTP endpoint, status code or request and response contract |

### Gates that run on every ticket

| Role | Access | Delegate to it |
|---|---|---|
| Code Reviewer | read-only reviewer | After implementing or changing code for a ticket, before Reality Checker and before any pull request is opened |
| Reality Checker | read-only reviewer | As the acceptance gate of every ticket, after Code Reviewer, to check each acceptance criterion against evidence that was actually produced before the draft pull request is opened. It does not judge CI |

## Rules

- The session or role that wrote a change does not count as its reviewer.
- Read-only reviewers cannot run commands. Give them the diff, the acceptance criteria and the recorded command output.
- Each role file starts with a section "In this repository" written for this project. That section and `CLAUDE.md` override the role's general advice (frameworks, dependencies, cloud services) wherever they differ.
- In the pull request description, add a section "Agent roles run" listing each role that ran, what it was asked and its verdict, and any step you did yourself because a role was missing.

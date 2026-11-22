---
name: next-ticket
description: Take one ticket of epic #1 from the queue to a ready pull request. Starting this skill is the owner's go signal; it never merges.
argument-hint: "[issue number]"
disable-model-invocation: true
---

# Next ticket

The owner starts this with `/next-ticket` or `/next-ticket <issue number>`. That is the go signal: the repository is used to train AI models, so no ticket work starts without it. Do one ticket per run, then stop. Never merge, never start another run.

The epic is issue #1. Its body holds the dependency table; the order is #8, #2, #3, #4, #9, #5, #6, #7, then any later ticket of the epic (for example #12). Labels: `status:ready`, `status:blocked`, `status:in-progress`, `needs-decision`, `tracking`.

Only leaf tickets are work. A ticket labelled `tracking`, or one with open sub-issues (`gh api repos/jortega0033/variable-font-editor/issues/<n>/sub_issues`), is a container and is never picked. The order is the parents in the epic table, then the sub-issues of each parent in their listed order.

## Steps

1. **Refresh the queue.** `gh issue list --state open --label epic`, then read the epic body and each open child with `gh issue view` and its sub-issues with the API call above. A `status:blocked` ticket whose blockers (the "Depends on" column and the ticket text) are all closed is relabelled `status:ready`: `gh issue edit <n> --remove-label status:blocked --add-label status:ready`. A parent whose sub-issues are all closed is closed with a comment (`gh issue close <n> --comment "All sub-issues are closed."`). If a label does not exist yet, say so and continue by the dependency table.
2. **Pick the ticket.** If an issue number was given, use it: check that it is open, not `status:in-progress` and not `needs-decision`; if it is a `tracking` ticket or has open sub-issues, refuse it, list its open sub-issues and stop. If no issue number was given, take the first `status:ready` leaf ticket in the order above that is neither `status:in-progress` nor `needs-decision`. If none qualifies, say why and stop.
3. **Claim it.** `gh issue edit <n> --add-label status:in-progress --remove-label status:ready`.
4. **Branch in a fresh worktree.** `git fetch origin`, then `git worktree add ../variable-font-editor-<n> -b <type>/<n>-<short-slug> origin/main` (branch name as in the Git workflow in `CLAUDE.md`). Work only in that worktree. Never work on `main`.
5. **Run the playbook.** Follow [`.claude/skills/implement-ticket/SKILL.md`](../implement-ticket/SKILL.md) for the whole ticket, including the Code Reviewer and Reality Checker gates and the evidence `CLAUDE.md` requires. Before calling the two reviewers, which have no shell, write the review material to `.claude/state/review/` in the worktree: `git diff --stat origin/main...HEAD`, `git diff origin/main...HEAD` and the output of each local check, and name those files in the request.
6. **Open the draft.** Only after the local checks and both gates have passed, `git push -u origin <branch>`, then `gh pr create --draft` with the template in `.github/pull_request_template.md` (the push comes first: `gh pr create` aborts on an unpushed branch). The pull request says `Closes #<n>`; if this ticket is the last open sub-issue of a parent, it also says `Closes #<parent>`. Acceptance steps that need a person (marked manual in the ticket) are done as far as an agent can and listed under "Owner checks". The review gate hook blocks `gh pr create` and `gh pr ready` until the gate roles have run after the last code edit.
7. **Wait for CI without polling.** Bind the pull request to the session if the app offers it, then end the turn with the line "Draft pull request #N is waiting for CI". Do not loop, sleep or watch. When the session is woken (a CI event from the app, or the owner says "continue"), read `gh pr checks <N>` once. Green: go to step 8. Red: fix, re-run the local checks and both gates, push, and end the turn with the same line. Still running: end the turn with the same line.
8. **Hand off.** On green CI run `gh pr ready <N>`, then comment on the issue with the pull request link, the CI run link and a one-line status.
9. **Stop.** Report the ticket, the pull request, the evidence and anything not verified. Leave the merge to the owner. Do not remove the worktree.

If a decision blocks the ticket and the ticket states no default, stop, label the issue `needs-decision`, say what is needed, and end the run.

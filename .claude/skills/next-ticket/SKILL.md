---
name: next-ticket
description: Take one ticket of epic #1 from the queue to a ready pull request. Starting this skill is the owner's go signal; it never merges.
argument-hint: "[issue number]"
disable-model-invocation: true
---

# Next ticket

The owner starts this with `/next-ticket` or `/next-ticket <issue number>`. That is the go signal: the repository is used to train AI models, so no ticket work starts without it. Do one ticket per run, then stop. Never merge, never start another run.

The epic is issue #1. Its body holds the dependency table; the order is #8, #2, #3, #4, #9, #5, #6, #7. Labels: `status:ready`, `status:blocked`, `status:in-progress`, `needs-decision`.

## Steps

1. **Refresh the queue.** `gh issue list --state open --label epic`, then read the epic body and each open child with `gh issue view`. A `status:blocked` ticket whose blockers (the "Depends on" column and the ticket text) are all closed is relabelled `status:ready`: `gh issue edit <n> --remove-label status:blocked --add-label status:ready`. If a label does not exist yet, say so and continue by the dependency table.
2. **Pick the ticket.** If an issue number was given, use it, and check that it is open, not `status:in-progress` and not `needs-decision`. Otherwise take the first `status:ready` ticket in the epic's dependency order that is neither `status:in-progress` nor `needs-decision`. If none qualifies, say why and stop.
3. **Claim it.** `gh issue edit <n> --add-label status:in-progress --remove-label status:ready`.
4. **Branch in a fresh worktree.** `git fetch origin`, then `git worktree add ../variable-font-editor-<n> -b <type>/<n>-<short-slug> origin/main` (branch name as in the Git workflow in `CLAUDE.md`). Work only in that worktree. Never work on `main`.
5. **Run the playbook.** Follow [`.claude/skills/implement-ticket/SKILL.md`](../implement-ticket/SKILL.md) for the whole ticket, including the Code Reviewer and Reality Checker gates and the evidence `CLAUDE.md` requires.
6. **Hand off.** Open the pull request as a draft with the template in `.github/pull_request_template.md` (it names the issue). When both gates have passed and CI is green on the pull request (`gh pr checks`), run `gh pr ready`, then comment on the issue with the pull request link and a one-line status. The review gate hook blocks `gh pr create` and `gh pr ready` until the gate roles have run after the last code edit.
7. **Stop.** Report the ticket, the pull request, the evidence and anything not verified. Leave the merge to the owner. Do not remove the worktree.

If a decision blocks the ticket and the ticket states no default, stop, label the issue `needs-decision`, say what is needed, and end the run.

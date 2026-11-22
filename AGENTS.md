# AGENTS.md

The full repository instructions are in [CLAUDE.md](CLAUDE.md). This file repeats only what an agent needs before it reads that.

## Test commands

```
python -m unittest discover -s tests -t .
```

Use `python3` on Linux. Python 3.12 or newer, standard library only. There is no lint step, no build step and no package manifest. Do not add pip or npm dependencies.

## Run

```
python -m font_editor --data-dir ./data --port 8765
```

## Ticket work

To implement a GitHub issue, follow [.claude/skills/implement-ticket/SKILL.md](.claude/skills/implement-ticket/SKILL.md) and the section "Project agents and ticket workflow" in [CLAUDE.md](CLAUDE.md). Each role file in `.claude/agents/` starts with a section "In this repository" that holds this project's checklist for that role.

## Loop conventions

- The loop runs at L1: report-only, started by hand. It proposes; it does not label, comment, close, edit source, push or merge.
- No scheduler and no loop workflow is installed (the CI workflow `.github/workflows/ci.yml` runs the tests and the gate self-test on pull requests). Do not add one without the owner's approval.
- See [LOOP.md](LOOP.md) for the manual command and the human gates.

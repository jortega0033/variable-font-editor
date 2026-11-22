#!/usr/bin/env python3
"""Review gate for pull requests opened from Claude Code.

Two modes, both called by the hooks in .claude/settings.json:

  record  when a subagent finishes (SubagentStop): note which role ran, and when.
  check   before a shell command: if the command opens a pull request or marks
          one ready, refuse unless every gate role ran after the last code edit.

A change that touches only documentation or agent configuration passes without
a review. The owner can switch the gate off for a session by starting Claude
Code with ROLE_GATE=off in the environment.

Standard library only. Exit code 2 blocks the tool call; the text on stderr is
shown to Claude as the reason.
"""
import json
import os
import re
import subprocess
import sys
import time

GATE_ROLES = ["Code Reviewer", "Reality Checker"]  # GATE_ROLES_MARKER
LEDGER = os.path.join(".claude", "state", "role-runs.jsonl")
PR_COMMAND = re.compile(r"(?:^|[\s;&|(])gh(?:\.exe)?\s+pr\s+(create|ready)\b")
DOC_ONLY = re.compile(
    r"(^|/)(\.claude|\.github|docs)/|\.(md|txt|rst)$|(^|/)(LICENSE|\.gitignore|\.gitattributes)$",
    re.IGNORECASE,
)
SLACK_SECONDS = 2  # file-system timestamp granularity


def git(root, *args):
    try:
        out = subprocess.run(
            ["git", "-C", root] + list(args),
            capture_output=True, text=True, timeout=20,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    # keep leading spaces: `git status --porcelain` lines start with them
    return out.stdout.rstrip() if out.returncode == 0 else None


def repo_root(cwd):
    return git(cwd or ".", "rev-parse", "--show-toplevel")


def base_ref(root):
    head = git(root, "symbolic-ref", "--quiet", "--short", "refs/remotes/origin/HEAD")
    for ref in [head, "origin/main", "origin/master", "main", "master"]:
        if ref and git(root, "rev-parse", "--verify", "--quiet", ref) is not None:
            return ref
    return None


def changed_files(root):
    """Files that differ from the default branch, committed or not. None = unknown."""
    names = set()
    base = base_ref(root)
    if base is None:
        return None
    merge_base = git(root, "merge-base", base, "HEAD")
    if merge_base is None:
        return None
    committed = git(root, "diff", "--name-only", merge_base, "HEAD")
    working = git(root, "status", "--porcelain", "--untracked-files=all")
    if committed is None or working is None:
        return None
    names.update(line for line in committed.splitlines() if line)
    for line in working.splitlines():
        path = line[3:]
        if " -> " in path:
            path = path.split(" -> ", 1)[1]
        names.add(path.strip('"'))
    return sorted(names)


def is_code(path):
    return not DOC_ONLY.search(path.replace("\\", "/"))


def last_code_change(root, files):
    """(timestamp, path) of the most recently modified changed code file."""
    newest, newest_path = 0.0, None
    for rel in files:
        full = os.path.join(root, rel)
        try:
            stamp = os.path.getmtime(full)
        except OSError:
            continue  # deleted file: nothing left to review in it
        if stamp > newest:
            newest, newest_path = stamp, rel
    return newest, newest_path


def read_ledger(root):
    runs = {}
    try:
        with open(os.path.join(root, LEDGER), "r", encoding="utf-8") as handle:
            for line in handle:
                try:
                    entry = json.loads(line)
                except ValueError:
                    continue
                role = str(entry.get("role", "")).strip().lower()
                stamp = float(entry.get("ts", 0))
                if role and stamp > runs.get(role, 0):
                    runs[role] = stamp
    except OSError:
        pass
    return runs


def record(event):
    tool_input = event.get("tool_input") or {}
    # SubagentStop events carry agent_type; a tool event carries tool_input.subagent_type
    role = event.get("agent_type") or tool_input.get("subagent_type") or ""
    role = str(role).strip()
    if not role:
        return 0
    root = repo_root(event.get("cwd"))
    if not root:
        return 0
    path = os.path.join(root, LEDGER)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "a", encoding="utf-8") as handle:
        handle.write(json.dumps({
            "role": role,
            "ts": time.time(),
            "session": event.get("session_id", ""),
        }) + "\n")
    return 0


def check(event):
    command = str((event.get("tool_input") or {}).get("command", ""))
    if not PR_COMMAND.search(command):
        return 0
    if os.environ.get("ROLE_GATE", "").lower() == "off":
        sys.stderr.write("role gate: switched off by ROLE_GATE=off for this session\n")
        return 0
    root = repo_root(event.get("cwd"))
    if not root:
        return 0  # not a git checkout: nothing to gate
    files = changed_files(root)
    if files is None:
        code = None  # cannot tell what changed: require the gate
    else:
        code = [name for name in files if is_code(name)]
        if not code:
            return 0  # documentation or agent configuration only
    stamp, newest = last_code_change(root, code) if code else (time.time(), None)
    if code and not newest:
        # every changed code file was deleted: a review any time after the branch point counts
        branch_point = git(root, "log", "-1", "--format=%ct", git(root, "merge-base", base_ref(root), "HEAD") or "HEAD")
        stamp, newest = float(branch_point or 0), "(deleted files only)"
    runs = read_ledger(root)
    missing = [role for role in GATE_ROLES if runs.get(role.lower(), 0) + SLACK_SECONDS < stamp]
    if not missing:
        return 0
    when = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(stamp))
    seen = ", ".join(
        "%s at %s" % (role, time.strftime("%H:%M:%S", time.localtime(runs[role.lower()])))
        for role in GATE_ROLES if role.lower() in runs
    ) or "none"
    sys.stderr.write(
        "Blocked by .claude/hooks/role_gate.py: this pull request changes code and the review gate has not "
        "run on the current state of it.\n"
        "Run these project subagents on the full diff, fix what they find, then try again: %s.\n"
        "Last code change: %s at %s. Gate runs recorded: %s.\n"
        "A review counts only if it ran after the last code edit. Documentation-only changes pass without one.\n"
        "The steps are in .claude/skills/implement-ticket/SKILL.md.\n"
        % (", ".join(missing), newest or "unknown", when, seen)
    )
    return 2


def self_test():
    import shutil
    import tempfile

    def run(root, mode, event, env=None):
        full_env = dict(os.environ)
        full_env.pop("ROLE_GATE", None)
        full_env.update(env or {})
        event = dict(event, cwd=root)
        proc = subprocess.run(
            [sys.executable, os.path.abspath(__file__), mode],
            input=json.dumps(event), capture_output=True, text=True, env=full_env,
        )
        return proc.returncode

    def sh(root, *args):
        subprocess.run(["git", "-C", root] + list(args), check=True, capture_output=True)

    pr = {"tool_name": "Bash", "tool_input": {"command": "gh pr create --draft --title x --body y"}}
    failures = []

    def expect(label, got, want):
        if got != want:
            failures.append("%s: exit %s, expected %s" % (label, got, want))

    root = tempfile.mkdtemp(prefix="role-gate-")
    try:
        sh(root, "init", "-q", "-b", "main")
        sh(root, "config", "user.email", "test@example.invalid")
        sh(root, "config", "user.name", "test")
        with open(os.path.join(root, "app.py"), "w") as handle:
            handle.write("x = 1\n")
        sh(root, "add", "-A")
        sh(root, "commit", "-q", "-m", "base")
        sh(root, "checkout", "-q", "-b", "feature")

        expect("other command passes", run(root, "check", {"tool_name": "Bash", "tool_input": {"command": "git status"}}), 0)
        expect("no change passes", run(root, "check", pr), 0)

        with open(os.path.join(root, "README.md"), "w") as handle:
            handle.write("docs\n")
        expect("docs-only change passes", run(root, "check", pr), 0)

        with open(os.path.join(root, "app.py"), "w") as handle:
            handle.write("x = 2\n")
        expect("code change without review is blocked", run(root, "check", pr), 2)
        expect("gh pr ready is gated too", run(root, "check", {"tool_name": "Bash", "tool_input": {"command": "cd x && gh pr ready 12"}}), 2)
        expect("owner switch passes", run(root, "check", pr, {"ROLE_GATE": "off"}), 0)

        time.sleep(SLACK_SECONDS + 1)
        for role in GATE_ROLES[:-1]:
            run(root, "record", {"hook_event_name": "SubagentStop", "agent_type": role})
        if len(GATE_ROLES) > 1:
            expect("one gate role missing is blocked", run(root, "check", pr), 2)
        run(root, "record", {"hook_event_name": "SubagentStop", "agent_type": GATE_ROLES[-1].upper()})
        expect("all gate roles after the edit pass", run(root, "check", pr), 0)

        sh(root, "add", "-A")
        sh(root, "commit", "-q", "-m", "change")
        expect("committing does not invalidate the review", run(root, "check", pr), 0)

        time.sleep(SLACK_SECONDS + 1)
        with open(os.path.join(root, "app.py"), "w") as handle:
            handle.write("x = 3\n")
        expect("code edited after the review is blocked again", run(root, "check", pr), 2)
    finally:
        shutil.rmtree(root, ignore_errors=True)

    if failures:
        print("role_gate self-test FAILED:\n  " + "\n  ".join(failures))
        return 1
    print("role_gate self-test passed (gate roles: %s)" % ", ".join(GATE_ROLES))
    return 0


def main():
    mode = sys.argv[1] if len(sys.argv) > 1 else ""
    if mode == "--self-test":
        return self_test()
    try:
        event = json.load(sys.stdin)
    except ValueError:
        return 0  # no readable event: never block on a malformed call
    if mode == "record":
        return record(event)
    if mode == "check":
        return check(event)
    return 0


if __name__ == "__main__":
    sys.exit(main())

"""repopilot.git_utils - Shared git plumbing helpers."""

from __future__ import annotations

import subprocess
import sys


def ensure_git() -> None:
    """Exit with code 1 if git is not on PATH."""
    try:
        subprocess.run(
            ["git", "--version"],
            capture_output=True,
            text=True,
        )
    except FileNotFoundError:
        sys.stderr.write("Error: Git executable not found in PATH.\n")
        sys.exit(1)


def is_inside_work_tree() -> bool:
    """Return True if CWD is inside a git working tree."""
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--is-inside-work-tree"],
            capture_output=True,
            text=True,
        )
        return result.returncode == 0 and result.stdout.strip() == "true"
    except FileNotFoundError:
        return False


def current_branch() -> str | None:
    """Return the name of the current branch, or None on detached HEAD."""
    result = subprocess.run(
        ["git", "branch", "--show-current"],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        return None
    name = result.stdout.strip()
    return name if name else None


def merged_branches() -> list[str]:
    """Return a list of local branch names that are merged into HEAD."""
    result = subprocess.run(
        ["git", "branch", "--merged"],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        return []

    branches: list[str] = []
    for line in result.stdout.splitlines():
        line = line.strip()
        if not line:
            continue
        # Strip the current-branch marker (* ) or worktree marker (+ )
        if line.startswith("* "):
            line = line[2:].strip()
        elif line.startswith("+ "):
            line = line[2:].strip()
        # Ignore detached HEAD entries e.g. '(HEAD detached at ...)'
        if line.startswith("(") and "detached" in line:
            continue
        branches.append(line)
    return branches


def delete_branch(name: str) -> tuple[bool, str]:
    """Delete a local branch with `git branch -d`.

    Returns (success, message).
    """
    result = subprocess.run(
        ["git", "branch", "-d", name],
        capture_output=True,
        text=True,
    )
    if result.returncode == 0:
        msg = result.stdout.strip() or f"Deleted branch {name}."
        return True, msg
    err = result.stderr.strip() or result.stdout.strip()
    return False, err

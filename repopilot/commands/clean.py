"""commands/clean.py - Clean stale, merged git branches."""

from __future__ import annotations

import subprocess
import sys


def print_error(message: str) -> None:
    """Print an error message to STDERR matching the shared repopilot convention."""
    sys.stderr.write(f"Error: {message}. Run 'repopilot clean --help' for usage.\n")


def parse_protected(protect_arg) -> set[str]:
    """Parse protected branches from arguments.
    
    Supports list of strings, comma-separated strings, or single string.
    """
    if protect_arg is None:
        return {"main", "master", "dev"}
    if isinstance(protect_arg, str):
        protect_arg = [protect_arg]
    protected = set()
    for item in protect_arg:
        for part in str(item).split(","):
            val = part.strip()
            if val:
                protected.add(val)
    return protected


def register(subparsers):
    """Register the 'clean' subcommand parser."""
    parser = subparsers.add_parser(
        "clean",
        help="Find and delete local git branches that are already merged.",
        description="Find and delete local git branches that are already merged (stale branch cleanup).",
    )
    parser.add_argument(
        "--protect",
        nargs="*",
        default=["main", "master", "dev"],
        help="Protected branches that should not be deleted (default: main master dev).",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be deleted without deleting.",
    )
    parser.add_argument(
        "--force",
        "-f",
        action="store_true",
        help="Skip the confirmation prompt before deleting.",
    )
    parser.set_defaults(handler=handle)
    return parser


def handle(args) -> int:
    """Handle the 'repopilot clean' command."""
    try:
        # 1. Confirm current directory is inside a git working tree
        try:
            rev_parse = subprocess.run(
                ["git", "rev-parse", "--is-inside-work-tree"],
                capture_output=True,
                text=True,
            )
        except FileNotFoundError:
            print_error("Git executable not found in PATH")
            sys.exit(1)

        if rev_parse.returncode != 0 or rev_parse.stdout.strip() != "true":
            print_error("Not a git repository")
            sys.exit(1)

        # 2. Get current branch (never delete this one)
        curr_res = subprocess.run(
            ["git", "branch", "--show-current"],
            capture_output=True,
            text=True,
        )
        if curr_res.returncode != 0:
            print_error(f"Failed to get current branch: {curr_res.stderr.strip()}")
            sys.exit(2)

        current_branch = curr_res.stdout.strip()

        # 3. Get merged branches
        merged_res = subprocess.run(
            ["git", "branch", "--merged"],
            capture_output=True,
            text=True,
        )
        if merged_res.returncode != 0:
            print_error(f"Failed to list merged branches: {merged_res.stderr.strip()}")
            sys.exit(2)

        raw_merged = []
        for line in merged_res.stdout.splitlines():
            line = line.strip()
            if not line:
                continue
            if line.startswith("* "):
                line = line[2:].strip()
            elif line.startswith("+ "):
                line = line[2:].strip()
            # Ignore detached HEAD entries e.g. '(HEAD detached at ...)'
            if line.startswith("(") and "detached" in line:
                continue
            raw_merged.append(line)

        # 4. Filter out protected branches and current branch
        protected = parse_protected(getattr(args, "protect", None))
        branches_to_delete = [
            b for b in raw_merged
            if b not in protected and b != current_branch
        ]

        # Guard: Ensure current branch is never targeted for deletion
        if current_branch and current_branch in branches_to_delete:
            print_error(f"Cannot delete the currently checked-out branch '{current_branch}'")
            sys.exit(1)

        # 5. Handle --dry-run mode
        if getattr(args, "dry_run", False):
            for branch in branches_to_delete:
                print(branch)
            return 0

        # If no branches eligible for deletion
        if not branches_to_delete:
            print("No merged branches to clean.")
            return 0

        # 6. Confirmation prompt if --force is not specified
        if not getattr(args, "force", False):
            print("Merged branches eligible for deletion:")
            for b in branches_to_delete:
                print(f"  {b}")
            try:
                response = input("Delete these branches? [y/N]: ").strip().lower()
            except (EOFError, KeyboardInterrupt):
                print("\nAborted.")
                return 0

            if response not in ("y", "yes"):
                print("Aborted.")
                return 0

        # 7. Delete each remaining branch with git branch -d
        for branch in branches_to_delete:
            if branch == current_branch:
                print_error(f"Cannot delete the currently checked-out branch '{current_branch}'")
                sys.exit(1)

            del_res = subprocess.run(
                ["git", "branch", "-d", branch],
                capture_output=True,
                text=True,
            )
            if del_res.returncode == 0:
                msg = del_res.stdout.strip() or f"Deleted branch {branch}."
                print(msg)
            else:
                err_msg = del_res.stderr.strip() or del_res.stdout.strip()
                print(f"Failed to delete {branch}: {err_msg}")

        return 0

    except SystemExit:
        raise
    except Exception as exc:
        print_error(f"Unexpected internal error: {exc}")
        sys.exit(2)

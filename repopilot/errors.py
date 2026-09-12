"""repopilot.errors - Shared error reporting."""

from __future__ import annotations

import sys


def print_error(message: str, command: str = "") -> None:
    """Print a formatted error message to STDERR.

    Format: Error: <message>. Run 'repopilot [<command>] --help' for usage.
    """
    suffix = f" {command}" if command else ""
    sys.stderr.write(f"Error: {message}. Run 'repopilot{suffix} --help' for usage.\n")

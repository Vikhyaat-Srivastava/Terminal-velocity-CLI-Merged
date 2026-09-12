"""repopilot.cli - Main entry point for the repopilot CLI."""

from __future__ import annotations

import argparse
import sys

from repopilot import __version__
from repopilot.commands import setup, env, clean, logs


def build_parser() -> argparse.ArgumentParser:
    """Build the top-level argument parser and register all subcommands."""
    parser = argparse.ArgumentParser(
        prog="repopilot",
        description="CLI tools for developer workflows — setup, env, clean, logs.",
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"%(prog)s {__version__}",
    )

    subparsers = parser.add_subparsers(
        dest="command",
        title="commands",
        description="Run 'repopilot <command> --help' for details on a specific command.",
    )

    # Register all subcommands
    setup.register(subparsers)
    env.register(subparsers)
    clean.register(subparsers)
    logs.register(subparsers)

    return parser


def main(argv: list[str] | None = None) -> None:
    """Parse arguments and dispatch to the appropriate subcommand."""
    parser = build_parser()
    args = parser.parse_args(argv)

    if not args.command:
        parser.print_help()
        sys.exit(0)

    if hasattr(args, "handler"):
        code = args.handler(args)
        sys.exit(code or 0)
    else:
        parser.print_help()
        sys.exit(0)

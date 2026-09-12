#!/usr/bin/env python3
"""
repopilot - CLI tool for developer workflows.

Entry point that imports each commands/*.py module and calls
register(subparsers) from each to wire up subcommands.

Shared conventions:
  Exit codes:  0 = success, 1 = user error, 2 = internal error
  Errors:      stderr only, format:
               "Error: <what went wrong>. Run 'repopilot <cmd> --help' for usage."
"""

import argparse
import sys

from repopilot.commands import setup, env, clean, logs

COMMAND_MODULES = [
    setup,
    env,
    clean,
    logs,
]


def main(argv=None):
    parser = argparse.ArgumentParser(
        prog="repopilot",
        description="CLI tool for developer workflows — setup, env, clean, logs.",
    )
    subparsers = parser.add_subparsers(dest="command")

    for module in COMMAND_MODULES:
        module.register(subparsers)

    args = parser.parse_args(argv)

    if not args.command:
        parser.print_help(file=sys.stderr)
        return 1

    # Each module sets a 'handler' default on its subparser
    if hasattr(args, "handler"):
        code = args.handler(args)
        sys.exit(code or 0)

    parser.print_help(file=sys.stderr)
    return 1


if __name__ == "__main__":
    sys.exit(main())

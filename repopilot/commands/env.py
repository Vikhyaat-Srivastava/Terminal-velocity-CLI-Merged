"""
repopilot env - Environment switching and management subcommand.
Complies with Track 4 constraints:
- STDOUT: Shell commands ONLY for `switch` (to be evaluated by parent shell).
- STDERR: All human-facing messages and errors.
- Exit codes: 0 = success, 1 = user error, 2 = internal error.
- Error format: "Error: <what went wrong>. Run 'repopilot <cmd> --help' for usage."
"""

import os
import re
import shlex
import sys
from pathlib import Path


# ----------------------------------------------------------------------
# Helpers: Exit & Error Formatting
# ----------------------------------------------------------------------

def user_error(cmd_name: str, message: str) -> int:
    """Print user error to STDERR and return exit code 1."""
    print(f"Error: {message}. Run 'repopilot {cmd_name} --help' for usage.", file=sys.stderr)
    return 1


def internal_error(cmd_name: str, message: str) -> int:
    """Print internal error to STDERR and return exit code 2."""
    print(f"Error: {message}. Run 'repopilot {cmd_name} --help' for usage.", file=sys.stderr)
    return 2


def find_repo_root() -> Path:
    """Search upward from CWD to find .git directory or root marker."""
    cur = Path.cwd().resolve()
    for d in [cur, *cur.parents]:
        if (d / ".git").exists():
            return d
    return cur


# ----------------------------------------------------------------------
# Parser: Robust .env Parser
# ----------------------------------------------------------------------

def parse_env_file(filepath: Path) -> dict[str, str]:
    """
    Parses a .env file handling:
    - Empty files and empty values (KEY=)
    - Optional leading 'export '
    - Single quotes (preserves exact literal string)
    - Double quotes (supports escaped \\", \\n, \\r, \\t)
    - Multiline values enclosed in quotes
    - Full-line and inline comments (#)
    """
    env_vars: dict[str, str] = {}
    content = filepath.read_text(encoding="utf-8-sig")
    lines = content.splitlines()

    i = 0
    while i < len(lines):
        line = lines[i].strip()
        i += 1

        if not line or line.startswith("#"):
            continue

        if line.startswith("export "):
            line = line[7:].strip()

        if "=" not in line:
            continue

        key, val = line.split("=", 1)
        key = key.strip()
        val = val.strip()

        if not key or not re.match(r"^[A-Za-z_][A-Za-z0-9_]*$", key):
            continue

        if val.startswith('"'):
            val_buf = val[1:]
            while True:
                # Look for unescaped closing double quote
                match = re.search(r'(?<!\\)"', val_buf)
                if match:
                    raw_val = val_buf[:match.start()]
                    val = (
                        raw_val.replace(r'\"', '"')
                        .replace(r"\n", "\n")
                        .replace(r"\r", "\r")
                        .replace(r"\t", "\t")
                        .replace(r"\\", "\\")
                    )
                    break
                if i >= len(lines):
                    val = val_buf  # Unterminated quote fallback
                    break
                val_buf += "\n" + lines[i]
                i += 1

        elif val.startswith("'"):
            val_buf = val[1:]
            while True:
                idx = val_buf.find("'")
                if idx != -1:
                    val = val_buf[:idx]
                    break
                if i >= len(lines):
                    val = val_buf
                    break
                val_buf += "\n" + lines[i]
                i += 1

        else:
            # Unquoted: strip inline comments preceded by whitespace
            comment_match = re.search(r"\s+#.*$", val)
            if comment_match:
                val = val[:comment_match.start()].strip()

        env_vars[key] = val

    return env_vars


# ----------------------------------------------------------------------
# Shell Formatting
# ----------------------------------------------------------------------

def detect_shell(requested_shell: str) -> str:
    """Determine target shell format (bash/zsh vs powershell vs fish)."""
    if requested_shell and requested_shell != "auto":
        return requested_shell.lower()

    env_shell = os.environ.get("REPOPILOT_SHELL", "").lower()
    if env_shell in ("powershell", "pwsh", "bash", "zsh", "fish"):
        return env_shell

    # If $SHELL is set (Linux, macOS, Git Bash, WSL), use bash syntax
    if os.environ.get("SHELL"):
        shell_path = os.environ["SHELL"].lower()
        if "fish" in shell_path:
            return "fish"
        if "zsh" in shell_path:
            return "zsh"
        return "bash"

    # Windows native default (PowerShell)
    if os.name == "nt":
        return "powershell"

    return "bash"


def format_export_command(key: str, val: str, target_shell: str) -> str:
    """Format single variable export for target shell."""
    if target_shell in ("powershell", "pwsh"):
        escaped_val = val.replace("'", "''")
        return f"$env:{key} = '{escaped_val}'"
    elif target_shell == "fish":
        escaped_val = shlex.quote(val)
        return f"set -gx {key} {escaped_val}"
    else:  # bash, zsh, sh
        escaped_val = shlex.quote(val)
        return f"export {key}={escaped_val}"


# ----------------------------------------------------------------------
# Command Implementations
# ----------------------------------------------------------------------

def handle_switch(args) -> int:
    """
    Subcommand: repopilot env switch <name> [--shell {auto,bash,zsh,powershell,fish}]
    Prints shell statements to STDOUT; informational messages to STDERR.
    """
    cmd_name = "env switch"
    env_name = args.name.strip()

    # Prevent directory traversal attacks
    if not re.match(r"^[a-zA-Z0-9_.-]+$", env_name):
        return user_error(cmd_name, f"Invalid environment name '{env_name}'")

    try:
        root = find_repo_root()
        target_file = root / f".env.{env_name}"

        if not target_file.exists():
            return user_error(cmd_name, f"Environment file '.env.{env_name}' not found in {root}")

        if not target_file.is_file():
            return user_error(cmd_name, f"'.env.{env_name}' is not a valid file")

        # Parse variables
        env_vars = parse_env_file(target_file)
        env_vars["REPOPILOT_ACTIVE_ENV"] = env_name

        shell_type = detect_shell(getattr(args, "shell", "auto"))
        shell_cmds: list[str] = []

        # 1. Environment variables
        for key, val in env_vars.items():
            shell_cmds.append(format_export_command(key, val, shell_type))

        # 2. Check for .nvmrc in repo root
        nvmrc_path = root / ".nvmrc"
        if nvmrc_path.is_file():
            nvm_ver = nvmrc_path.read_text(encoding="utf-8").strip()
            if nvm_ver:
                shell_cmds.append(f"nvm use {shlex.quote(nvm_ver)}")
                print(f"[repopilot] Detected .nvmrc: using Node {nvm_ver}", file=sys.stderr)

        # 3. Check for .python-version in repo root
        pyver_path = root / ".python-version"
        if pyver_path.is_file():
            py_ver = pyver_path.read_text(encoding="utf-8").strip()
            if py_ver:
                shell_cmds.append(f"pyenv shell {shlex.quote(py_ver)}")
                print(f"[repopilot] Detected .python-version: using Python {py_ver}", file=sys.stderr)

        # STDOUT: Only shell commands (evaluated by parent shell)
        for cmd in shell_cmds:
            sys.stdout.write(cmd + "\n")
        sys.stdout.flush()

        # STDERR: Human-readable notification
        var_count = len(env_vars) - 1  # exclude REPOPILOT_ACTIVE_ENV
        print(f"[repopilot] Switched to environment: '{env_name}' ({var_count} variables set)", file=sys.stderr)
        return 0

    except Exception as exc:
        return internal_error(cmd_name, f"Failed to switch environment: {exc}")


def handle_list(args) -> int:
    """
    Subcommand: repopilot env list
    Lists all available .env.* files found in the repository.
    """
    cmd_name = "env list"
    try:
        root = find_repo_root()
        current_env = os.environ.get("REPOPILOT_ACTIVE_ENV", "").strip()

        env_files = sorted(root.glob(".env.*"))
        # Exclude common template / backup patterns
        ignore_suffixes = {".example", ".sample", ".template", ".bak", ".backup"}
        active_envs = []

        for p in env_files:
            suffix = p.name[len(".env."):]
            if any(p.name.endswith(ign) for ign in ignore_suffixes):
                continue
            if suffix:
                active_envs.append(suffix)

        if not active_envs:
            print("No environment configurations (.env.<name>) found in repository.", file=sys.stdout)
            return 0

        print("Available environments:")
        for name in active_envs:
            is_active = (name == current_env)
            marker = "* " if is_active else "  "
            status = " (active)" if is_active else ""
            print(f"{marker}{name}{status}", file=sys.stdout)

        return 0

    except Exception as exc:
        return internal_error(cmd_name, f"Failed to list environments: {exc}")


def handle_current(args) -> int:
    """
    Subcommand: repopilot env current
    Prints currently active REPOPILOT_ACTIVE_ENV or indicates none.
    """
    current_env = os.environ.get("REPOPILOT_ACTIVE_ENV", "").strip()
    if current_env:
        print(current_env, file=sys.stdout)
    else:
        print("No active environment (REPOPILOT_ACTIVE_ENV is not set)", file=sys.stdout)
    return 0


# ----------------------------------------------------------------------
# Registration Entry Point
# ----------------------------------------------------------------------

def register(subparsers):
    """
    Shared entrypoint called by main.py.
    Registers 'env' and its subcommands: switch, list, current.
    """
    env_parser = subparsers.add_parser(
        "env",
        help="Manage and switch repository environment variables and tool versions"
    )

    env_sub = env_parser.add_subparsers(dest="env_subcommand")

    # env switch <name>
    switch_p = env_sub.add_parser("switch", help="Switch environment by applying .env.<name>")
    switch_p.add_argument("name", help="Name of the environment (.env.<name>)")
    switch_p.add_argument(
        "--shell",
        choices=["auto", "bash", "zsh", "powershell", "pwsh", "fish"],
        default="auto",
        help="Target shell syntax for exported variables (default: auto)"
    )
    switch_p.set_defaults(handler=handle_switch)

    # env list
    list_p = env_sub.add_parser("list", help="List all available environments")
    list_p.set_defaults(handler=handle_list)

    # env current
    current_p = env_sub.add_parser("current", help="Show currently active environment")
    current_p.set_defaults(handler=handle_current)

    def dispatch(args):
        if not getattr(args, "env_subcommand", None):
            return user_error("env", "Missing subcommand (switch, list, or current)")
        return args.handler(args)

    env_parser.set_defaults(handler=dispatch)

#!/usr/bin/env python3
"""repopilot logs subcommand.

Filter and optionally summarize logs from a file, docker container, or journalctl.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import re
import subprocess
import sys
from typing import Optional
import urllib.request
import urllib.error


def error_exit(message: str, code: int = 1) -> None:
    """Print standard error message to STDERR and exit."""
    sys.stderr.write(f"Error: {message}. Run 'repopilot logs --help' for usage.\n")
    sys.exit(code)


def parse_since(since_str: str) -> datetime:
    """Parse relative duration (e.g. '1h', '30m', '2d') or timestamp into timezone-aware datetime."""
    s = since_str.strip()

    # Relative duration pattern: e.g. 10s, 30m, 1h, 2d, 1w
    m = re.match(r"^(\d+(?:\.\d+)?)\s*([a-zA-Z]+)$", s)
    if m:
        val = float(m.group(1))
        unit = m.group(2).lower()
        if unit in ("s", "sec", "second", "seconds"):
            delta = timedelta(seconds=val)
        elif unit in ("m", "min", "minute", "minutes"):
            delta = timedelta(minutes=val)
        elif unit in ("h", "hr", "hour", "hours"):
            delta = timedelta(hours=val)
        elif unit in ("d", "day", "days"):
            delta = timedelta(days=val)
        elif unit in ("w", "wk", "week", "weeks"):
            delta = timedelta(weeks=val)
        else:
            raise ValueError(f"Unknown time unit '{unit}' in --since '{since_str}'")

        return datetime.now(timezone.utc) - delta

    # Absolute timestamp (ISO-8601 or common log date formats)
    try:
        dt = datetime.fromisoformat(s.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)
    except Exception:
        pass

    for fmt in (
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%d %H:%M:%S.%f",
        "%Y-%m-%d",
        "%Y/%m/%d %H:%M:%S",
        "%Y/%m/%d",
        "%b %d %H:%M:%S",
        "%d/%b/%Y:%H:%M:%S",
    ):
        try:
            dt = datetime.strptime(s, fmt)
            if dt.year == 1900:
                dt = dt.replace(year=datetime.now(timezone.utc).year)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt.astimezone(timezone.utc)
        except ValueError:
            continue

    raise ValueError(f"Invalid --since format '{since_str}'. Expected format like '10m', '1h', '2d' or ISO timestamp.")


def extract_timestamp(line: str) -> Optional[datetime]:
    """Extract and parse timestamp from beginning or metadata of a log line."""
    # 1. ISO-8601 format: 2024-09-12T15:30:00.123456Z or 2024-09-12 15:30:00,123
    iso_match = re.search(
        r"\[?(\d{4}[-/]\d{2}[-/]\d{2}[T ]\d{2}:\d{2}:\d{2}(?:[.,]\d+)?(?:Z|[+-]\d{2}:?\d{2})?)\]?",
        line[:60],
    )
    if iso_match:
        ts_str = iso_match.group(1).replace(",", ".").replace("Z", "+00:00")
        try:
            dt = datetime.fromisoformat(ts_str)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt.astimezone(timezone.utc)
        except Exception:
            pass

    # 2. Syslog / journalctl format: Sep 12 15:30:00 or Sep  2 15:30:00
    syslog_match = re.search(
        r"\[?([A-Z][a-z]{2}\s+\d{1,2}\s+\d{2}:\d{2}:\d{2})\]?",
        line[:30],
    )
    if syslog_match:
        ts_str = syslog_match.group(1)
        try:
            dt = datetime.strptime(ts_str, "%b %d %H:%M:%S")
            dt = dt.replace(year=datetime.now(timezone.utc).year, tzinfo=timezone.utc)
            return dt
        except ValueError:
            pass

    # 3. JSON timestamp format: {"time": "...", "timestamp": "...", "@timestamp": "..."}
    if line.strip().startswith("{"):
        json_match = re.search(
            r'"(?:time|timestamp|@timestamp|ts|date)"\s*:\s*"([^"]+)"',
            line[:150],
        )
        if json_match:
            try:
                dt = datetime.fromisoformat(json_match.group(1).replace("Z", "+00:00"))
                if dt.tzinfo is None:
                    dt = dt.replace(tzinfo=timezone.utc)
                return dt.astimezone(timezone.utc)
            except Exception:
                pass

    return None


def get_level_regex(level_str: str) -> re.Pattern:
    """Build a regex pattern for filtering by log level."""
    lvl = level_str.strip().lower()
    if lvl in ("warn", "warning"):
        return re.compile(r"\b(warn|warning)\b", re.IGNORECASE)
    elif lvl in ("err", "error"):
        return re.compile(r"\b(error|err|critical|fatal)\b", re.IGNORECASE)
    elif lvl in ("info", "information"):
        return re.compile(r"\b(info|information)\b", re.IGNORECASE)
    elif lvl in ("debug",):
        return re.compile(r"\b(debug|trace)\b", re.IGNORECASE)
    elif lvl in ("crit", "critical", "fatal"):
        return re.compile(r"\b(critical|crit|fatal)\b", re.IGNORECASE)
    else:
        return re.compile(rf"\b{re.escape(lvl)}\b", re.IGNORECASE)


def fetch_source_lines(args: argparse.Namespace) -> list[str]:
    """Fetch raw log lines from the specified source."""
    # 1. File source
    if getattr(args, "file", None):
        file_path = Path(args.file)
        if not file_path.exists():
            error_exit(f"Log file '{args.file}' does not exist")
        if not file_path.is_file():
            error_exit(f"'{args.file}' is a directory, not a file")
        try:
            with open(file_path, "r", encoding="utf-8", errors="replace") as f:
                return f.readlines()
        except PermissionError:
            error_exit(f"Permission denied reading file '{args.file}'")
        except Exception as e:
            error_exit(f"Cannot read file '{args.file}': {e}")

    # 2. Docker source
    elif getattr(args, "docker", None):
        container = args.docker
        try:
            proc = subprocess.run(
                ["docker", "logs", "--timestamps", container],
                capture_output=True,
                text=True,
                errors="replace",
            )
            if proc.returncode != 0:
                err = proc.stderr.strip() or f"container '{container}' not found or stopped"
                error_exit(f"Failed to read Docker logs: {err}")

            # Docker writes app logs to stdout, but some containers
            # (e.g. nginx) write to stderr.  Merge both streams but
            # only include stderr when stdout is empty — avoids mixing
            # Docker engine messages into the log output.
            content = proc.stdout
            if not content.strip() and proc.stderr.strip():
                content = proc.stderr
            return [line + "\n" for line in content.splitlines()]
        except FileNotFoundError:
            error_exit("Docker command not found. Please ensure Docker is installed and running")
        except Exception as e:
            error_exit(f"Failed to read Docker logs for '{container}': {e}")

    # 3. Journalctl source
    elif getattr(args, "journalctl", None):
        cmd = ["journalctl", "--no-pager"]
        if isinstance(args.journalctl, str) and args.journalctl.strip() and args.journalctl.strip().lower() != "true":
            cmd.extend(["-u", args.journalctl.strip()])

        try:
            proc = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                errors="replace",
            )
            if proc.returncode != 0:
                err = proc.stderr.strip() or f"exit code {proc.returncode}"
                error_exit(f"Failed to read journalctl: {err}")
            return [line + "\n" for line in proc.stdout.splitlines()]
        except FileNotFoundError:
            error_exit("journalctl command not found (only available on systemd Linux distributions)")
        except Exception as e:
            error_exit(f"Failed to read journalctl: {e}")

    else:
        error_exit("No log source specified. Must specify one of --file, --docker, or --journalctl")
        return []


def summarize_with_ollama(lines: list[str]) -> Optional[str]:
    """Request a summary of filtered logs from local Ollama LLM."""
    if not lines:
        return "No log lines to summarize."

    # Sample up to last 100 lines (or 16KB) to avoid exceeding local model context
    sample = lines[-100:] if len(lines) > 100 else lines
    sample_text = "".join(sample)
    if len(sample_text) > 16000:
        sample_text = sample_text[-16000:]

    payload = {
        "model": "llama3",
        "messages": [
            {
                "role": "system",
                "content": (
                    "You are a developer log analysis assistant. Summarize the provided logs "
                    "concisely. Highlight errors, warnings, potential root causes, key events, "
                    "and recommended actions."
                ),
            },
            {
                "role": "user",
                "content": f"Summarize the following filtered log lines ({len(lines)} lines total):\n\n{sample_text}",
            },
        ],
        "temperature": 0.2,
        "max_tokens": 500,
    }

    req = urllib.request.Request(
        "http://localhost:11434/v1/chat/completions",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            return data["choices"][0]["message"]["content"].strip()
    except Exception:
        # Fallback to Ollama native /api/generate endpoint if /v1/ is not configured
        try:
            native_payload = {
                "model": "llama3",
                "prompt": (
                    "You are a developer log analysis assistant. Summarize the provided logs "
                    f"concisely, highlighting errors and patterns:\n\n{sample_text}"
                ),
                "stream": False,
            }
            req2 = urllib.request.Request(
                "http://localhost:11434/api/generate",
                data=json.dumps(native_payload).encode("utf-8"),
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with urllib.request.urlopen(req2, timeout=15) as resp2:
                data2 = json.loads(resp2.read().decode("utf-8"))
                return data2.get("response", "").strip()
        except Exception:
            # Summarization is strictly optional: fail gracefully if Ollama is not running
            sys.stderr.write("Warning: Local Ollama (http://localhost:11434/v1) unreachable. Summary skipped.\n")
            return None


def handle(args: argparse.Namespace) -> int:
    """Execute the 'logs' subcommand according to input/output specifications."""
    try:
        # Validate log sources (mutually exclusive)
        has_file = bool(getattr(args, "file", None))
        has_docker = bool(getattr(args, "docker", None))
        has_journalctl = bool(getattr(args, "journalctl", None))

        source_count = sum([has_file, has_docker, has_journalctl])
        if source_count == 0:
            error_exit("No log source specified. Must specify one of --file, --docker, or --journalctl")
        elif source_count > 1:
            error_exit("Multiple log sources specified. Specify exactly one of --file, --docker, or --journalctl")

        # Parse --since filter if provided
        cutoff_time: Optional[datetime] = None
        if getattr(args, "since", None):
            try:
                cutoff_time = parse_since(args.since)
            except ValueError as e:
                error_exit(str(e))

        # Parse --level filter if provided
        level_pattern: Optional[re.Pattern] = None
        if getattr(args, "level", None):
            level_pattern = get_level_regex(args.level)

        # Parse --grep filter if provided
        grep_pattern: Optional[re.Pattern] = None
        if getattr(args, "grep", None):
            try:
                grep_pattern = re.compile(args.grep)
            except re.error as e:
                error_exit(f"Invalid regex pattern for --grep '{args.grep}': {e}")

        # Fetch source lines
        raw_lines = fetch_source_lines(args)

        # Apply pure scripting filters
        filtered_lines: list[str] = []
        last_time_passed = True

        for line in raw_lines:
            # Filter by timestamp (--since)
            if cutoff_time is not None:
                log_dt = extract_timestamp(line)
                if log_dt is not None:
                    last_time_passed = (log_dt >= cutoff_time)
                if not last_time_passed:
                    continue

            # Filter by level (--level)
            if level_pattern is not None:
                if not level_pattern.search(line):
                    continue

            # Filter by regex pattern (--grep)
            if grep_pattern is not None:
                if not grep_pattern.search(line):
                    continue

            filtered_lines.append(line)

        # --count: print count only and exit
        if getattr(args, "count", False):
            sys.stdout.write(f"{len(filtered_lines)}\n")
            sys.stdout.flush()
            return 0

        # Output filtered lines to STDOUT
        for line in filtered_lines:
            sys.stdout.write(line if line.endswith("\n") else line + "\n")
        sys.stdout.flush()

        # Optional LLM summary appended after raw filtered lines
        if getattr(args, "summarize", False):
            summary = summarize_with_ollama(filtered_lines)
            if summary:
                sys.stdout.write("\n--- Log Summary ---\n")
                sys.stdout.write(summary + "\n")
                sys.stdout.flush()

        return 0

    except SystemExit:
        raise
    except Exception as e:
        sys.stderr.write(f"Error: Internal error: {e}. Run 'repopilot logs --help' for usage.\n")
        sys.exit(2)


def register(subparsers: argparse._SubParsersAction) -> argparse.ArgumentParser:
    """Register the 'logs' subcommand with argparse."""
    parser = subparsers.add_parser(
        "logs",
        help="Filter and optionally summarize logs from a file, docker container, or journalctl",
        description="Filter and optionally summarize logs from a file, docker container, or journalctl.",
    )

    # Mutually exclusive log sources
    source_group = parser.add_mutually_exclusive_group(required=False)
    source_group.add_argument(
        "--file",
        "-f",
        metavar="PATH",
        help="Path to log file",
    )
    source_group.add_argument(
        "--docker",
        "-d",
        metavar="CONTAINER",
        help="Docker container name or ID",
    )
    source_group.add_argument(
        "--journalctl",
        "-j",
        nargs="?",
        const=True,
        default=None,
        metavar="UNIT",
        help="Read from systemd journalctl (optionally pass unit name)",
    )

    # Optional filters
    parser.add_argument(
        "--level",
        "-l",
        metavar="LEVEL",
        help="Filter by log level (e.g. error, warn, info, debug)",
    )
    parser.add_argument(
        "--since",
        "-s",
        metavar="DURATION",
        help="Filter logs since relative duration (e.g. '1h', '30m', '2d') or ISO timestamp",
    )
    parser.add_argument(
        "--grep",
        "-g",
        metavar="PATTERN",
        help="Filter logs matching regular expression pattern",
    )

    # Optional local LLM summarization
    parser.add_argument(
        "--summarize",
        action="store_true",
        default=False,
        help="Append local LLM-generated summary (via Ollama at http://localhost:11434/v1)",
    )
    parser.add_argument(
        "--count",
        "-c",
        action="store_true",
        default=False,
        help="Print count of matching lines instead of the lines themselves",
    )

    parser.set_defaults(handler=handle)
    return parser

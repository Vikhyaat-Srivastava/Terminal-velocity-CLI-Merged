# Design Note — RepoPilot

## The Problem

RepoPilot was built during the "Can You Hack It?" hackathon to solve common, daily developer workflow problems. It addresses four main pain points:
1. **Dependency Installation (`setup`)**: Every project has a different build system (`package.json`, `requirements.txt`, `Cargo.toml`). Running the correct install command manually is tedious.
2. **Environment Management (`env`)**: Switching between `.env.staging` and `.env.prod` usually involves manual copying or sourcing.
3. **Branch Cleanup (`clean`)**: Merged branches linger locally and clutter `git branch` output.
4. **Log Analysis (`logs`)**: Fetching logs from different sources (files, docker, journalctl) requires different tools, and parsing them for errors is noisy.

## Key Design Choices

**1. Unified Interface, Modular Implementation**
The four subcommands share a single entry point (`repopilot`), but each is implemented as a self-contained module in `commands/`. They all follow the same exit code and stderr-based error reporting conventions.

**2. Setup: Rule-based First, LLM Fallback**
The `setup` command relies on a fast, deterministic lookup table for known files (`package.json` -> `npm install`). An LLM (via local Ollama) is used only as an optional fallback for unknown or ambiguous build scripts, ensuring offline reliability.

**3. Env: Parent Shell Modification via STDOUT**
A child Python process cannot change the environment of the parent shell. To solve this, `repopilot env switch` prints raw shell export commands to `STDOUT`, allowing the user to wrap it in `eval` (e.g., `eval $(repopilot env switch staging)`). All human-readable logging is routed to `STDERR` to prevent polluting the shell evaluation.

**4. Logs: Source-Agnostic Filtering**
The `logs` subcommand normalizes streams from files, `docker logs`, and `journalctl`, providing a unified interface for timestamp (`--since`), level (`--level`), and regex (`--grep`) filtering before optionally passing the filtered subset to a local LLM for summarization.

**5. Clean: Git Plumbing Only**
`repopilot clean` shells out to `git branch --merged` and `git branch -d`. It respects existing git configurations, safely guards protected branches (`main`, `master`, `dev`), and defaults to an interactive confirmation prompt.

## Architecture

The project has been refactored into a single flattened canonical structure:

```
repopilot/
├── __init__.py          # version
├── __main__.py          # python -m repopilot entry
├── cli.py               # argparse, unified subcommand registration
├── main.py              # CLI dispatcher
└── commands/
    ├── __init__.py
    ├── clean.py         # Merged branch cleanup
    ├── env.py           # .env switching and shell export
    ├── logs.py          # Unified log filtering and summarization
    └── setup.py         # Dependency detection and installation
```

Adding a new subcommand is as simple as creating `commands/foo.py` with `register(subparsers)` and `handle(args)`, then registering it in `cli.py` and `main.py`.

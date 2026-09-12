# RepoPilot

> CLI tool for developer workflows — setup, env, clean, logs.

Built for the **"Terminal Velocity"** track (Track 4) at the _Can You Hack It?_ hackathon.

# RepoPilot 🚀

**One command to set up any repo.** RepoPilot scans your project, detects dependency files, and runs the right install commands — so you don't have to remember whether it's `npm install`, `pip install -r requirements.txt`, or `go mod tidy`.

Built for the **"Can You Hack It?"** hackathon — Track 4: Terminal Velocity.

---

## Install

```bash
cd repopilot
pip install -e .
```

This registers the `repopilot` command in your PATH.

---

## Commands

### `repopilot env switch <name>`

Reads `.env.<name>` from the repo root, plus optional `.nvmrc` / `.python-version`, and
prints shell commands to stdout. **Must be wrapped in `eval`** (see Shell Wrapper below).

```bash
eval "$(repopilot env switch staging)"
```

Options:

- `--shell {auto,bash,zsh,powershell,pwsh,fish}` — override target shell syntax (default: `auto`)

### `repopilot env list`

Lists available `.env.*` files in the repo. Marks the active one with `*`.

```bash
repopilot env list
```

### `repopilot env current`

Prints the currently active environment name (from `REPOPILOT_ACTIVE_ENV`).

```bash
repopilot env current
```

---

## Shell Wrapper (Required for `env switch`)

A child process **cannot** change its parent shell's environment. You need a thin wrapper
that `eval`s stdout.

### Bash / Zsh (`~/.bashrc` or `~/.zshrc`)

```bash
repopilot() {
    if [ "$1" = "env" ] && [ "$2" = "switch" ]; then
        local cmds
        cmds="$(command repopilot "$@")" || return $?
        eval "$cmds"
    else
        command repopilot "$@"
    fi
}
```

### PowerShell (`$PROFILE`)

```powershell
function repopilot {
    if ($args[0] -eq 'env' -and $args[1] -eq 'switch') {
        $cmds = & (Get-Command -CommandType Application repopilot) @args
        if ($LASTEXITCODE -eq 0 -and $cmds) {
            Invoke-Expression ($cmds -join "`n")
        }
    } else {
        & (Get-Command -CommandType Application repopilot) @args
    }
}
```

### Fish (`~/.config/fish/functions/repopilot.fish`)

```fish
function repopilot
    if test "$argv[1]" = "env" -a "$argv[2]" = "switch"
        set -l cmds (command repopilot $argv)
        and eval $cmds
    else
        command repopilot $argv
    end
end
```

---

## Testing

```bash
cd repopilot
pip install pytest
python -m pytest tests/ -v
# Clone and install (one command)
git clone https://github.com/<your-org>/repopilot.git && cd repopilot && pip install -e .
```

Or from a local checkout:

```bash
pip install -e .
```

That's it. The `repopilot` command is now available globally.

---

## Usage

### `repopilot setup`

Scan the current repo, detect dependencies, and run install commands.

```bash
# Interactive (asks for confirmation before running)
repopilot setup

# Skip confirmation
repopilot setup --yes

# See what would run, without executing anything
repopilot setup --dry-run

# Scan a different directory
repopilot setup --dir /path/to/repo
```

**What it detects:**

| File             | Project Type       | Command                           |
| ---------------- | ------------------ | --------------------------------- |
| requirements.txt | Python (pip)       | `pip install -r requirements.txt` |
| pyproject.toml   | Python (pyproject) | `pip install -e .`                |
| setup.py         | Python (setup.py)  | `pip install -e .`                |
| package.json     | Node.js            | `npm install`                     |
| go.mod           | Go                 | `go mod tidy`                     |
| pom.xml          | Java (Maven)       | `mvn install`                     |
| build.gradle     | Java (Gradle)      | `gradle build`                    |
| Gemfile          | Ruby               | `bundle install`                  |
| Cargo.toml       | Rust               | `cargo build`                     |
| composer.json    | PHP (Composer)     | `composer install`                |
| Dockerfile       | Docker             | `docker build -t <dirname> .`     |

**LLM fallback (optional):** If a `Makefile`, `CMakeLists.txt`, or other ambiguous file is found, RepoPilot can ask a local Ollama LLM for the right command. This requires [Ollama](https://ollama.ai) running at `localhost:11434` with the `llama3` model. If Ollama isn't running, the tool works fine without it — ambiguous files are simply skipped.

### Other subcommands (coming soon)

```bash
repopilot env     # Manage project environment variables
repopilot clean   # Clean stale branches and build artifacts
repopilot logs    # Search and filter project logs
```

---

## Architecture

```
repopilot/
├── main.py              ← entry point, imports commands/*.py
├── commands/
│   ├── __init__.py
│   └── env.py           ← env switch / list / current
├── tests/
│   └── test_env.py      ← 15 edge-case tests
├── setup.py             ← pip install -e .
└── README.md
```

Each teammate owns one `commands/*.py` module. `main.py` imports all four and calls
`register(subparsers)` to wire them into a single CLI.

**Exit codes:** `0` = success, `1` = user error, `2` = internal error.
├── pyproject.toml # Package config, console_scripts entry
├── README.md
└── repopilot/
├── **init**.py
├── main.py # Entry point — wires subparsers
└── commands/
├── **init**.py
├── setup.py # ← Scan + detect + install
├── env.py # (stub)
├── clean.py # (stub)
└── logs.py # (stub)

```

Each teammate owns one `commands/*.py` file. `main.py` calls `register(subparsers)` from each, so work merges cleanly.

---

## Exit Codes

| Code | Meaning                          |
|------|----------------------------------|
| 0    | Success                          |
| 1    | User error (bad input, not found)|
| 2    | Internal error (unexpected crash)|

---

## License

Hackathon project — no license yet.
MIT
```

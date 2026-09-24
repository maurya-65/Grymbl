# Grymbl

> Not AI that remembers: software that accumulates judgment.

Grymbl watches a repository the way an experienced engineer watches over your shoulder.
It stays silent by default and speaks up only when a pattern resembles something
consequential it has seen before, and only with evidence.

This is the v1 prototype from `docs/prototype_plan.md`: a local Python agent with SQLite
storage and no server. Nothing leaves your machine except escalated episodes sent to Claude
Sonnet for analysis.

## How it works

```
sensors ──► events (SQLite) ──► episodes ──► Jev triage ──► Sonnet ──► interventions.md
 files        redacted,           adaptive     4 rules,     evidence    silent unless
 terminal     content-deduped     window +     no LLM       rule        history backs it
 git, tests                       imports
```

| Stage | Module | Plan |
|---|---|---|
| File sensor, exact content-hash dedup | `sensors/files.py`, `dedup.py` | §2, §3 |
| Terminal hook (bash, zsh, PowerShell) | `hooks/`, `sensors/terminal.py` | §2 |
| Secret redaction (local, pattern-based) | `redact.py` | §5 |
| Git hooks (`post-commit`, `pre-push`) | `sensors/git.py` | §2 |
| Test runs (pytest, Jest, `go test`) | `sensors/tests.py` | §2 |
| Episode correlation | `correlate.py`, `imports.py` | §4 |
| Jev triage | `jev.py` | §6 |
| Experience Graph | `store.py` | §7 |
| Sonnet + evidence rule | `reasoning.py` | §11 |

## Setup

Requires Python 3.12+ and [uv](https://docs.astral.sh/uv/).

```sh
uv tool install --editable .      # puts `grymbl` on PATH
cd path/to/app-repo
grymbl init                       # creates .grymbl/, baselines files, installs git hooks
```

Load the terminal hook in your shell profile:

| Shell | Profile | Line |
|---|---|---|
| bash (Linux, macOS, Git Bash) | `~/.bashrc` | `eval "$(grymbl shell-hook bash)"` |
| zsh | `~/.zshrc` | `eval "$(grymbl shell-hook zsh)"` |
| PowerShell | `$PROFILE` | `grymbl shell-hook powershell \| Out-String \| Invoke-Expression` |

Then, in the watched repo:

```sh
export ANTHROPIC_API_KEY=...      # only escalated episodes are sent
grymbl watch                      # leave running in a terminal
grymbl test -- pytest             # or: grymbl test -- npx jest / grymbl test -- go test ./...
grymbl status                     # recent episodes
```

pytest needs `pytest-json-report` installed in the app's environment.

Interventions are appended to `.grymbl/interventions.md` and echoed in the watcher's terminal.

## Privacy

- Commands are captured only inside a repo that has a `.grymbl/` directory.
- Secrets are masked before storage. The raw command is never written anywhere.
- Commands typed with a leading space are skipped if your shell's history ignores them
  (`HISTCONTROL=ignorespace` in bash, `setopt HIST_IGNORE_SPACE` in zsh).
- `.grymbl/` ignores itself in git.

## Development

```sh
uv sync
uv run pytest
uv run ruff check . && uv run ruff format --check .
uv run mypy
```

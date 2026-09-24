# Grymbl

> **Not AI that remembers. Software that accumulates judgment.**

Every developer has a moment they wish someone had warned them about: the "harmless" refactor
that quietly broke auth, the test that went green only after three retries, the logic deleted
on a Friday that had been holding up something important. Somebody usually *had* seen it
before. That knowledge just wasn't in the room.

**Grymbl is that someone.**

It works like a senior engineer who has watched every change you've ever made. It reads your
edits, your terminal, your commits, and your test runs, and it groups them into episodes:
the actual stories of what you did. Over time it builds an **Experience Graph** of what
happened, where, and what each change assumed.

Most of the time, it says nothing. **Silence is a feature.** You get no pop-ups, no nagging,
and no chatbot asking how it can help. Grymbl speaks up only when what you're doing now looks
like something that mattered before, and when it does, it shows its evidence. If the evidence
is thin, it says so rather than guessing.

### Why it's different

- **Judgment, not autocomplete.** Other AI tools react to the file in front of them. Grymbl
  reasons from your history: which files carry scars, which changes broke things before,
  and which assumptions are still unverified.
- **Earned interventions.** A cheap, deterministic triage step handles almost everything
  locally. Only episodes that meet the escalation rules reach Claude, and Claude must back
  every claim with your diffs, commits, and history.
- **Private by design.** Everything runs on your machine. Secrets are stripped from terminal
  commands before anything is stored, the raw command is never written anywhere, and the
  only thing that ever leaves is an escalated, redacted episode.
- **Built into how you already work.** It hooks into bash, zsh, PowerShell, git, pytest, Jest,
  and `go test`, on Windows, macOS, and Linux. There's no new workflow to learn.

> **Status:** v1 prototype (spec: `docs/prototype_plan.md`). The local Python agent uses SQLite
> storage and runs with zero infrastructure.

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

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

## Documentation

**[The Grymbl Guide](docs/guide/README.md)** is the complete handover documentation. It
explains everything from the underlying concepts up to how to run and extend the code:

| Chapter | For |
|---|---|
| [1. Foundations](docs/guide/01_foundations.md) | Every technical concept, explained from zero |
| [2. The Product](docs/guide/02_the_product.md) | What Grymbl is and why |
| [3. How It Works](docs/guide/03_how_it_works.md) | Every part of the system in depth |
| [4. Tech Stack](docs/guide/04_tech_stack.md) | Every tool: what it is, the alternatives, and why it was chosen |
| [5. Codebase Tour](docs/guide/05_codebase_tour.md) | Every file and how data moves through the code |
| [6. Developing](docs/guide/06_developing.md) | Setup, rules, and recipes for changing the code |
| [7. Operating](docs/guide/07_operating.md) | Installing, the API key, costs, troubleshooting |
| [8. History and Lessons](docs/guide/08_history_and_lessons.md) | Decisions made, bugs found, lessons learned |
| [9. Status and Roadmap](docs/guide/09_status_and_roadmap.md) | What's proven, what's missing, what's next |
| [Glossary](docs/guide/glossary.md) | Every term |

The specifications the guide is based on: the [prototype plan](docs/prototype_plan.md) and the
[v1.1 agent-awareness addendum](docs/v1.1_agent_awareness.md).

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
| Coding-agent capture (Claude Code) | `sensors/agent.py` | v1.1 |
| Local HTML report (`grymbl report`) | `report.py`, `templates/report.html` | — |

## Setup

Requires Python 3.12+ and [uv](https://docs.astral.sh/uv/).

```sh
uv tool install --editable .      # puts `grymbl` on PATH
cd path/to/app-repo
grymbl init                       # creates .grymbl/, baselines files, installs git + Claude Code hooks
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
grymbl report                     # the full picture in your browser (charts, episodes, cost)
```

pytest needs `pytest-json-report` installed in the app's environment.

Interventions are appended to `.grymbl/interventions.md` and echoed in the watcher's terminal.

### Coding agents

Most code is now written by agents, and an agent can do something a human can't: tell you what
it intended and what it assumed. `grymbl init` adds hooks to the repo's local Claude Code
settings (`.claude/settings.local.json`, kept out of git). For each agent turn, Grymbl then
records the prompt, which is the episode's intent, along with every shell command and its exit
code, every file edit, and the agent's written account of its work. Each prompt opens its own
episode.

What the agent says is treated as a claim, not evidence. Sonnet compares it with what the diffs
and test runs show, and a mismatch between the two counts as a finding. Skip this with
`grymbl init --no-agent-hooks`. See `docs/v1.1_agent_awareness.md` for the roadmap: agents
recording their own assumptions over MCP, and warnings delivered to the agent itself.

## Cost

Model spend is capped by design:

- **Jev decides first.** Routine work never reaches the model. Only episodes that meet the
  escalation rules cost anything.
- **Medium effort** on Sonnet by default (`Settings.effort`).
- **At most 25 Sonnet calls per day** (`Settings.daily_call_cap`). Beyond that, escalations are
  still recorded, just without analysis.
- **Evidence capped at ~25k tokens per call.** The largest diffs are trimmed first, with an
  explicit marker, and at most the 10 most recent prior episodes are sent as history.
- The watcher logs the token usage of every call.

Also set a monthly spend limit in the Anthropic Console as a backstop.

## Privacy

- Commands are captured only inside a repo that has a `.grymbl/` directory.
- Secrets are masked before storage. The raw command is never written anywhere.
- Commands typed with a leading space are skipped if your shell's history ignores them
  (`HISTCONTROL=ignorespace` in bash, `setopt HIST_IGNORE_SPACE` in zsh).
- Agent prompts, commands, output, and narrative go through the same redaction before storage.
- `.grymbl/` ignores itself in git.

## Development

```sh
uv sync
uv run pytest
uv run ruff check . && uv run ruff format --check .
uv run mypy
```

## License

Copyright © 2026 Maurya Oganja. All rights reserved. This is proprietary software;
see [`LICENSE`](LICENSE). No use, copying, or distribution without written permission.

# Grymbl Tech Stack

*What we built Grymbl with, what else we could have used, and why we chose what we did.*

> **Read this alongside [`how_grymbl_works.md`](how_grymbl_works.md)**, which explains what
> each part *does*. This document explains what each part is *made of*. Technical words link to
> that document's [Glossary](how_grymbl_works.md#glossary).

---

## Contents

- [What matters to us](#what-matters-to-us)
- [How each decision is written](#how-each-decision-is-written)
- [The overall shape: a local program](#the-overall-shape-a-local-program)
- [Programming language](#programming-language)
- [Project and dependency management](#project-and-dependency-management)
- [Code quality tools](#code-quality-tools)
- [Packaging](#packaging)
- [Storage](#storage)
- [File watching](#file-watching)
- [Terminal capture](#terminal-capture)
- [Git capture](#git-capture)
- [Test results](#test-results)
- [Coding agent capture](#coding-agent-capture)
- [Secret detection](#secret-detection)
- [Finding related files](#finding-related-files)
- [Detecting real changes](#detecting-real-changes)
- [The AI model](#the-ai-model)
- [Talking to the AI](#talking-to-the-ai)
- [The command line interface](#the-command-line-interface)
- [Delivering warnings](#delivering-warnings)
- [Version control hosting and ownership](#version-control-hosting-and-ownership)
- [What changes at scale](#what-changes-at-scale)
- [The whole stack on one page](#the-whole-stack-on-one-page)

---

## What matters to us

Every choice below is a **trade-off**: gaining one thing by giving up another. To choose
consistently, we ranked what matters. Each decision refers back to these by number.

| # | Priority | What it means in practice |
|---|---|---|
| **P1** | **Prove the idea fast** | This is a *prototype*. The question is "does watching and judging actually work?", not "is it as fast as possible?" Prefer whatever gets a working answer soonest |
| **P2** | **Near-zero cost** | No servers to rent, no paid services except the AI calls, and those are tightly capped |
| **P3** | **Private by default** | Your code and commands stay on your machine. Only redacted, flagged episodes ever leave |
| **P4** | **Never get in the way** | Grymbl must not slow your typing, commits, or AI agent, and must never block anything |
| **P5** | **Works everywhere** | Windows, macOS, and Linux |
| **P6** | **Simple enough for one person** | Few dependencies (outside code we rely on), no infrastructure to babysit |
| **P7** | **Easy to replace later** | Pick the simple version now, and move to the "correct long-term" choice only once the idea is proven. The plan calls this *sequencing discipline* |

---

## How each decision is written

- **The need:** what this part has to do, in plain words.
- **The options:** realistic alternatives.
- **The choice:** what we picked.
- **Why:** linked to the priorities above.
- **What we gave up:** the honest cost of the choice.

---

## The overall shape: a local program

**The need:** Grymbl has to observe a developer's work and remember it.

| Option | What it is | Verdict |
|---|---|---|
| **A local program** | Runs on your own computer, stores data in a file there | ✅ **Chosen** |
| A cloud service | Your activity is sent to servers we run | ❌ Costs money every month (P2); your code leaves your machine (P3) |
| An IDE extension | A plugin inside your code editor (such as VS Code) | ⏸ Parked for v2: the heaviest thing to build, and it only sees the editor, not the terminal, git, or AI agents |

**Why:** zero infrastructure cost (P2), nothing leaves the machine (P3), and one person can run
it (P6).

**What we gave up:** no team features yet. Each developer's Grymbl knows only their own
history. Sharing memory across a team ("Team Master" in the plan) is a later layer.

---

## Programming language

**The need:** a language for the whole local program: sensors, database, rules, AI calls.

| Option | Strengths | Weaknesses |
|---|---|---|
| **Python** | Fastest to write; the best libraries for AI; very readable | Slower, and uses more memory than compiled languages; needs Python installed |
| Go | Small single-file programs, low memory, great at doing many things at once | Slower to write, weaker AI libraries |
| Rust | Fastest and leanest, very memory-safe | Much slower to write and learn |
| TypeScript/Node.js | Familiar to web developers, decent AI libraries | Heavier runtime, weaker fit for system-level work |

**The choice:** **Python 3.12+** (the plan's decision, §9.1).

**Why:** P1 above all. The prototype must prove that the *sensor → episode → triage* design
works at all, and Python gets there fastest. Anthropic's Python library is first-class, which
matters for the AI step.

**What we gave up:** a program that runs all day on every developer's laptop should ideally be
tiny and fast. The plan's answer is P7: **move the local agent to Go, then Rust, once the design
is proven.** Not before, because "paying Rust's learning-curve tax before there's proof the idea
works" would be premature.

**Two language features we lean on:**
- **Type hints**, labels saying what kind of data each value holds (`path: str`,
  `exit_code: int`). Python doesn't enforce them by itself, but a checker does (see
  [Code quality tools](#code-quality-tools)). They catch whole classes of bugs before the code
  ever runs.
- **Dataclasses**, compact definitions of data shapes like an [event](how_grymbl_works.md#event).
  Most are *frozen* (unchangeable once created), which prevents accidental edits.

---

## Project and dependency management

**The need:** install the libraries Grymbl uses, keep their versions fixed so the program
behaves the same everywhere, and isolate them from other Python projects.

A **dependency** is code written by someone else that your program relies on. A **virtual
environment** is a private folder of dependencies for one project, so projects don't
interfere with each other.

| Option | Notes |
|---|---|
| **uv** | One fast tool for environments, installing, and exact version locking. Written in Rust |
| pip + venv | Built into Python. Works, but it's several manual steps, and has no lock file by default |
| Poetry | Popular all-in-one tool, but noticeably slower |

**The choice:** **uv** (`pyproject.toml` declares what we need; `uv.lock` pins exact versions).

**Why:** fast and simple (P1, P6). The **lock file** guarantees that you, a future
collaborator, and your future self all get exactly the same versions.

**What we gave up:** one extra tool to install (it's installed with `pip install uv`).

**Grymbl has only three runtime dependencies (P6):**

| Library | What it does for us |
|---|---|
| `anthropic` | Anthropic's official library for calling Claude |
| `pydantic` | Defines and validates the four-field form Sonnet fills in |
| `watchdog` | File-change notifications on every operating system |

Everything else (the database, hashing, diffs, the command line) comes from Python's own
**standard library**, which ships with Python itself.

---

## Code quality tools

**The need:** catch mistakes automatically, and keep the code consistent enough that anyone,
human or AI, can read it.

| Job | Chosen | Alternatives | Why |
|---|---|---|---|
| **Linting** (spotting likely bugs and bad patterns) and **formatting** (consistent layout) | **ruff** | flake8 + black + isort (three separate tools) | One tool, extremely fast (P6) |
| **Type checking** (verifying the type hints) | **mypy, in strict mode** | pyright; no type checking | The long-standing standard. *Strict* means no unlabelled values are allowed anywhere |
| **Testing** (automated checks that the code does what it should) | **pytest** | unittest (built in) | Shorter, clearer tests; the de facto standard |

**The rule:** all four checks (lint, format, types,
tests) must pass before any commit. There are currently **96 tests**, one test file per module.
Tests never touch the internet: the AI is replaced by a stand-in ("fake") during testing, so
tests are free, fast, and repeatable.

**Why strictness is worth it:** live testing still found real bugs (see
[how_grymbl_works.md §18](how_grymbl_works.md#18-what-is-not-done-yet) and the
[decision log](how_grymbl_works.md#17-decision-log-the-small-choices-and-why)). Every bug found
became a new test, so it can't quietly return.

---

## Packaging

**The need:** turn the code into an installable program with a `grymbl` command.

**The choice:** a standard `pyproject.toml` with the **hatchling** build backend, installed via
`uv tool install --editable .`

- A **build backend** is the tool that packages Python code for installation. Hatchling is a
  modern, simple one. The main alternative, setuptools, is older and more configuration-heavy.
- **Editable** install means the installed `grymbl` command runs straight from the code folder,
  so code changes take effect immediately without reinstalling.

The shell hook scripts ship *inside* the package as data files, so `grymbl shell-hook bash`
can print them from wherever Grymbl is installed.

---

## Storage

**The need:** keep every event, episode, file snapshot, and assumption, safely, with several
programs writing at once (the watcher plus every hook).

| Option | What it is | Verdict |
|---|---|---|
| **SQLite** | A full database in one file, built into Python | ✅ **Chosen** |
| PostgreSQL / MySQL | Powerful database servers | ❌ A server to install and run all the time (P2, P6) |
| Neo4j / Amazon Neptune | *Graph* databases, built for connected data | ⏸ Later. Overkill for 3 node types and 2 relationships |
| JSON files | Plain text files | ❌ Unsafe with several writers at once; slow to search |

**Why SQLite:** no server, no cost, one file, zero setup, and already part of Python (P2, P6).
It handles far more data than one developer will ever produce.

**Settings that make it work:**
- **[WAL mode](how_grymbl_works.md#wal)** lets the watcher and many short-lived hook
  processes read and write safely at the same time.
- A **busy timeout** of 10 seconds: if the file is momentarily in use, a writer waits instead
  of failing.
- **Automatic [migrations](how_grymbl_works.md#migration)** add new columns to older
  databases on startup.

**What we gave up:** asking graph-shaped questions ("which assumptions were contradicted by
episodes that built on this one?") is clumsy in plain tables. The plan schedules the move to a
graph database for when those relationship types exist (P7).

---

## File watching

**The need:** know when any file in the project changes, on any operating system (P5), without
slowing the computer (P4).

| Option | How it works | Verdict |
|---|---|---|
| **watchdog library** | Wraps each operating system's own change-notification feature (inotify on Linux, FSEvents on macOS, ReadDirectoryChangesW on Windows) | ✅ **Chosen** |
| Polling | Re-read every file every few seconds to look for changes | ❌ Wastes effort; slow to notice |
| Each OS's feature directly | Write three separate versions | ❌ Triple the work (P6) |
| Editor events | Hook into the editor's save action | ❌ Needs an IDE extension (parked), and misses changes from terminals and AI agents |

**Why:** one library covers all three operating systems (P5, P6), and the OS tells us about
changes instead of us checking constantly (P4).

**What we learned the hard way:** operating systems report *events*, and events can mislead.
[Atomic saves](how_grymbl_works.md#atomic-save) look like deletions for a moment, so Grymbl
waits 2 seconds before believing one. That's why Grymbl also judges by **content**
([hashes](how_grymbl_works.md#hash)) rather than by save events.

---

## Terminal capture

**The need:** record each command typed, and whether it succeeded, without slowing the terminal
(P4), on all three platforms (P5).

| Option | How it works | Verdict |
|---|---|---|
| **Shell hooks** | Use each shell's built-in "run this after every command" feature | ✅ **Chosen** |
| Reading history files | Read `~/.bash_history` later | ❌ Delayed, has no success/failure information, and isn't written until the shell closes |
| Recording the whole session | Tools like `script` record everything on screen | ❌ Captures every output (secrets included) and is heavy |
| Wrapping the shell | Run the shell inside a Grymbl-controlled pseudo-terminal | ❌ Fragile, invasive, and platform-specific |

**Why hooks:** they're the official, lightweight way each shell offers (P4), and they provide
exactly what's needed: the command text and its exit code.

**The cost:** three shells means three small scripts to keep in step: `PROMPT_COMMAND` for
bash, `preexec`/`precmd` for zsh, and a wrapped `prompt` function for PowerShell. Each script
is short, and each hands its data to the same Python code, so the real logic (including
redaction) exists only once.

---

## Git capture

**The need:** record commits and pushes.

| Option | Verdict |
|---|---|
| **Git's own hooks** (`post-commit`, `pre-push`) | ✅ **Chosen**. Built into git, instant, local |
| Checking `git log` periodically | ❌ Delayed and wasteful |
| GitHub webhooks | ❌ Needs a server to receive them (P2), and only sees pushes |

**Why:** native, free, and immediate. The hooks are tiny shell scripts that always exit
successfully, so they can never block your work (P4).

---

## Test results

**The need:** know how many tests passed and failed, reliably.

| Option | Verdict |
|---|---|
| **Test runners' structured (JSON) reports** | ✅ **Chosen**. pytest via the `pytest-json-report` add-on, Jest with `--json`, Go with `-json` |
| Reading the text printed on screen | ❌ Breaks whenever a tool changes its wording |

**Why:** structured output is designed for machines and stays stable between versions. The cost
is a small wrapper: you run `grymbl test -- pytest` instead of `pytest`. pytest also needs one
extra add-on installed in the project being tested.

---

## Coding agent capture

**The need:** see what an AI coding agent was asked, what it did, and what it claimed.

| Option | Verdict |
|---|---|
| **Claude Code's hook system** | ✅ **Chosen** for v1.1 step 1. Official, structured data for each action, and it runs locally |
| Reading session transcripts after the fact | Partly used. The Stop hook reads the transcript for the agent's narrative, but hooks give real-time, per-action detail |
| Wrapping the agent program | ❌ Invasive and fragile |
| Telemetry export (sending metrics to a monitoring system) | ❌ Needs extra infrastructure (P2, P6) |
| MCP tools the agent calls itself | ⏭ Planned for step 2: lets agents *declare* assumptions, and works across many agents |

**Why hooks first:** they need no cooperation from the agent. They capture ground truth even if
the agent ignores every instruction. Adding the MCP layer later captures what the agent
*believes* on top.

**Verified, not assumed:** we captured real payloads from a live Claude Code session instead of
trusting the documentation, which had some field names and behaviours wrong.

**What we gave up:** this covers Claude Code only. Other agents (Cursor, Codex, …) need their
own adapters, or the MCP route.

---

## Secret detection

**The need:** remove passwords and keys from commands before saving them, locally, with no
network (P3).

| Option | Verdict |
|---|---|
| **Our own regex patterns** | ✅ **Chosen**. Small, fast, fully under our control, and they mask *only* the secret so the context survives |
| gitleaks / detect-secrets / trufflehog | Excellent tools, but built to scan files and repositories. They're heavier, and most report secrets rather than mask them inside a line. Their pattern lists are a good future source |
| An AI model | ❌ Would mean *sending the secret to the AI* to find it, which defeats the purpose |

**Why:** the plan requires fully local detection (P3), and masking only the secret keeps useful
context ("connected to the production database").

**What we gave up:** coverage is "common formats", not everything. The plan accepts that gap.
Our patterns also need care: one had a performance trap
([backtracking](how_grymbl_works.md#backtracking)) that live testing exposed and we fixed.

---

## Finding related files

**The need:** know that `tests/test_auth.py` is related to `app/auth.py` (because it imports
it), so their events belong to the same episode.

| Option | Verdict |
|---|---|
| **Regex scan of import lines** | ✅ **Chosen**. A few patterns per language; cheap, no dependencies |
| Full parsers (Python's `ast` module, tree-sitter) | More accurate, but a separate approach per language (or a large dependency) |
| Language servers (the engines behind editor features) | ❌ Heavy, one per language |
| An AI model | ❌ The plan says no LLM here: too slow and costly for every save |

**Why:** the plan asks for a "cheap static import check" (P1, P2), and regex handles the common
cases in Python and JavaScript/TypeScript.

**What we gave up:** unusual import styles can be missed, and Go isn't covered yet.

---

## Detecting real changes

**The need:** tell whether a file's content really changed, and describe exactly how.

| Job | Chosen | Alternatives | Why |
|---|---|---|---|
| Fingerprint the content | **SHA-256** from Python's `hashlib` | MD5 or SHA-1 (older), xxhash (faster, but another dependency) | Standard, built in, and accidental collisions are practically impossible |
| Describe the change | **`difflib` unified diffs** from the standard library | Running `git diff` | No dependency on git's state; works on files git doesn't track yet |

---

## The AI model

**The need:** careful reasoning about flagged episodes. It must follow the
[evidence rule](how_grymbl_works.md#evidence-rule) and answer in a fixed format, without
costing much.

Anthropic's current models (prices per million [tokens](how_grymbl_works.md#token), read /
written):

| Model | Price | Character |
|---|---|---|
| Claude Haiku 4.5 | $1 / $5 | Fast and cheap; lighter reasoning |
| **Claude Sonnet 5** | **$2 / $10** | ✅ **Chosen**. Strong reasoning at a moderate price |
| Claude Opus 5 | $5 / $25 | Stronger still, 2.5× the price |
| Claude Fable 5.1 | $10 / $50 | Anthropic's most capable, 5× the price |

**Why Sonnet:** the plan names it (§9.1). It's the balance point: capable enough to hold the
line on "insufficient evidence", cheap enough to run on every escalation.

**Where AI is deliberately *not* used:** triage ([Jev](how_grymbl_works.md#jev)), secret
detection, and import scanning. The plan explicitly keeps those rule-based: instant, free,
predictable, and private.

**Tuning for cost** (full detail in
[how_grymbl_works.md §13](how_grymbl_works.md#13-cost-controls)): medium
[effort](how_grymbl_works.md#effort), at most 25 calls a day, evidence capped at about 25,000
tokens, and history capped at 10 episodes.

---

## Talking to the AI

**The need:** send the evidence to Sonnet and get back a reliable answer.

| Option | Verdict |
|---|---|
| **Anthropic's official Python SDK** | ✅ **Chosen** |
| Raw web requests (writing HTTP calls by hand) | ❌ Reinvents retries, error types, and parsing |
| Generic multi-provider libraries | ❌ An extra layer between us and Claude-specific features |

**Features we rely on:**
- **[Structured output](how_grymbl_works.md#structured-output)** (`messages.parse` with a
  Pydantic model): Sonnet must fill in `evidence`, `summary`, `assumptions`, and
  `intervention`, and the SDK validates the answer's shape.
- **Typed errors:** separate handling for rate limits, network failures, server errors, and bad
  credentials, so each problem gets the right response and none crashes the watcher.
- **Automatic retries** on temporary failures.
- **Refusal check:** if the model declines a request, Grymbl notices instead of misreading an
  empty answer.

**Credentials:** the API key comes from the `ANTHROPIC_API_KEY`
[environment variable](how_grymbl_works.md#environment-variable). It's never written into code
or files.

---

## The command line interface

**The need:** the `grymbl` command and its subcommands.

| Option | Verdict |
|---|---|
| **argparse** (standard library) | ✅ **Chosen** |
| click / typer | Nicer to write, but add dependencies and startup time |

**Why:** hooks run `grymbl capture-…` after *every* command you type and every agent action. A
lean start with no extra imports keeps that cheap (P4), and there's no added dependency (P6).

---

## Delivering warnings

**The need:** show an [intervention](how_grymbl_works.md#intervention) to the developer.

| Option | Verdict |
|---|---|
| **A local markdown file + the watcher's window** | ✅ **Chosen** (the plan's v1 default) |
| Desktop notifications | Later. A different mechanism on each OS |
| Slack / email | ❌ Needs external services (P2, P3) |
| Telling the AI agent directly | ⏭ Planned in v1.1 step 3 |

**Why:** the plan treats the delivery channel as a detail to decide later, not a core system
decision. A file is the simplest possible channel, and nothing gets lost.

---

## Version control hosting and ownership

| Item | Choice | Why |
|---|---|---|
| Version control | **git** | The universal standard |
| Hosting | **GitHub, private repository** (`maurya-65/Grymbl`) | Backup and history. Private, because this is proprietary work |
| Ownership | **Proprietary, all rights reserved** ([`LICENSE`](../LICENSE)) | A solo commercial venture. Nobody may use, copy, or distribute the code without written permission |

---

## What changes at scale

The plan (§9.2) sets out where each layer goes once the prototype proves the idea. Each layer
is picked for *its own* constraints, not one language everywhere:

| Layer | Prototype (now) | At scale | Why the change |
|---|---|---|---|
| Local agent (sensors, redaction, dedup, correlation) | Python | **Go**, then **Rust** | Runs on every laptop all day: needs a tiny memory footprint, a single file to install, and no pauses |
| IDE extension | — | TypeScript (VS Code), Kotlin (JetBrains) | Dictated by each editor's platform |
| Event collection from many machines | — | **Go** | Handles bursts of simultaneous traffic cheaply |
| Team/company memory and AI orchestration | Python (inside the local agent) | **Python** on servers | Best AI and data libraries; few machines, so speed matters less |
| Experience Graph | SQLite | **Neo4j or Amazon Neptune** | Once richer relationships and cross-team questions exist |
| Human dashboard | — | TypeScript + Next.js | The standard for web interfaces |

**The principle (P7):** ship the simple version first, and migrate only once the design built
on it is proven.

---

## The whole stack on one page

| Area | Choice |
|---|---|
| Shape | Local program, no servers |
| Language | Python 3.12+ |
| Project tooling | uv (with `uv.lock`), hatchling |
| Quality | ruff (lint + format), mypy strict, pytest (96 tests) |
| Storage | SQLite in WAL mode, one file per project |
| File watching | watchdog, with content hashing (SHA-256) and difflib |
| Terminal | Shell hooks for bash, zsh, and PowerShell |
| Git | Native `post-commit` and `pre-push` hooks |
| Tests | JSON reports from pytest, Jest, and go test |
| AI agents | Claude Code hooks (MCP planned) |
| Secrets | Local regex redaction |
| Related files | Regex import scan (Python, JS/TS) |
| Triage | Jev: 4 deterministic rules, no AI |
| AI model | Claude Sonnet 5 via the official SDK, structured output, medium effort, capped |
| Command line | argparse |
| Warnings | `.grymbl/interventions.md` and the watcher window |
| Hosting | Private GitHub repo; proprietary license |
| Runtime dependencies | 3: `anthropic`, `pydantic`, `watchdog` |

---

<sub>Copyright © 2026 Maurya Oganja. All rights reserved. See [`LICENSE`](../LICENSE).</sub>

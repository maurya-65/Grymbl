# Chapter 4: Tech Stack

*Every tool and language: what it is, what else we could have used, why we chose it, and what
we gave up.*

A **tech stack** is the full set of technologies a product is built with: languages,
libraries, databases, tools. It's called a "stack" because the pieces sit on top of one
another: the language at the bottom, libraries on it, the product on top.

---

## How we decided

Every choice is a **trade-off**: gaining something by giving something up. To choose
consistently, we ranked what matters. Every decision below cites these by number.

| # | Priority | In practice |
|---|---|---|
| **P1** | **Prove the idea fast** | This is a prototype. The question is "does watching and judging work at all?" Prefer what gets an answer soonest |
| **P2** | **Near-zero cost** | No servers to rent. The only paid thing is AI calls, and those are capped |
| **P3** | **Private by default** | Code and commands stay on the machine |
| **P4** | **Never get in the way** | Never slow down or block the developer or their AI agent |
| **P5** | **Works everywhere** | Windows, macOS, Linux |
| **P6** | **Simple enough for one person** | Few dependencies, no infrastructure to babysit |
| **P7** | **Easy to replace later** | Choose the simple option now, and migrate only once the idea is proven. The plan calls this *sequencing discipline* |

Each section follows the same structure: **what it is** → **the options** → **the choice and
why** → **what we gave up**.

---

## The overall shape

**What we're deciding.** Where Grymbl runs and where its data lives.

| Option | What it is | Verdict |
|---|---|---|
| **Local program** | Runs on the developer's computer; data in a file there | ✅ Chosen |
| Cloud service | Activity is sent to servers we operate | ❌ Monthly costs (P2); code leaves the machine (P3) |
| Editor plugin (an "IDE extension") | Runs inside a code editor like VS Code | ⏸ Parked for v2. The heaviest lift, and it only sees the editor: not the terminal, git, or AI agents |

**Why:** zero infrastructure cost (P2), full privacy (P3), and one person can run it (P6).
**Gave up:** team features. Each developer's Grymbl only knows its own history for now.

---

## Programming language

**What it is.** A programming language is how instructions are written for a computer
([Foundations](01_foundations.md#programming-languages)).

| Language | What it's like | For Grymbl |
|---|---|---|
| **Python** | Interpreted, very readable, huge library ecosystem, the leading language for AI work | ✅ **Chosen** (plan §9.1) |
| Go | Compiled; produces one small program file; efficient at doing many things at once | Planned *later* for the always-running agent |
| Rust | Compiled; the fastest and leanest; very strong memory safety; slow to learn and write | Planned *after* Go, once the design is proven |
| TypeScript (Node.js) | JavaScript with types; popular for web work | Weaker fit for low-level system watching |

**Why Python (P1 first):** the prototype must prove the design works, and Python gets there
fastest. Anthropic's Python library is first-class, which matters for the AI step. Python 3.12
or newer is required for modern language features.

**Gave up:** speed and memory. A program running all day on every laptop should ideally be
tiny. The plan's answer (P7): move the local agent to Go, then Rust, **only after** the design
is proven, rather than "pay Rust's learning-curve tax before there's proof the idea works".

**Python features the code leans on:**
- **Type hints**, checked strictly ([Foundations](01_foundations.md#type-hints-and-type-checking)).
- **Dataclasses**: compact definitions of data shapes (an `Event`, a `Snapshot`), mostly
  *frozen* (unchangeable), which prevents accidental edits.
- **`from __future__ import annotations`** at the top of every file, a Python setting that
  makes type hints cheaper and more flexible.

---

## Project and dependency management

**What it is.** Tools that install the libraries a project needs, keep their exact versions
fixed, and isolate them in a private folder (a **virtual environment**; see
[Foundations](01_foundations.md#virtual-environments-and-lock-files)).

| Option | What it is | Verdict |
|---|---|---|
| **uv** | A modern, very fast all-in-one Python project tool (made by Astral, written in Rust). Creates the environment, installs dependencies, keeps a lock file, runs commands | ✅ Chosen |
| pip + venv | Built into Python. Works, but it's several manual steps and has no lock file by default | Simpler to explain, clumsier to use |
| Poetry | A popular all-in-one tool | Slower; heavier configuration |

**Why:** one fast tool (P1, P6), and its lock file `uv.lock` guarantees identical installs for
everyone, including your future self.

**Gave up:** one more tool to install (`python -m pip install uv`).

**The project's dependency list** (in `pyproject.toml`):

| Library | What it is | Why we need it |
|---|---|---|
| `anthropic` | Anthropic's official Python library for calling Claude | The Sonnet step ([Talking to the AI](#talking-to-the-ai)) |
| `pydantic` | A library for defining data shapes and validating data against them | Defines the four-field form Sonnet must fill in |
| `watchdog` | A library that gets file-change notifications from any OS | Sensor 1 ([File watching](#file-watching)) |

And for development only: `ruff`, `mypy`, `pytest` ([Code quality](#code-quality)).
**Only three runtime dependencies** (P6). Everything else (database, hashing, diffs, the
command line, JSON) comes from Python's **standard library**, which ships with Python.

---

## Code quality

**What it is.** Automatic tools that catch mistakes and keep code consistent
([Foundations](01_foundations.md#linting-and-formatting)).

| Job | Chosen tool | What the tool is | Alternatives | Why |
|---|---|---|---|---|
| Linting + formatting | **ruff** | A very fast linter *and* formatter in one (by Astral, like uv) | flake8 + black + isort: three tools doing the same | One tool, fast (P6) |
| Type checking | **mypy**, strict | The original Python type checker; "strict" rejects any unlabelled value | pyright (Microsoft's checker); none | The long-standing standard; strict catches the most |
| Testing | **pytest** | Python's most popular test framework | `unittest`, built in but wordier | Short, readable tests; excellent tooling |

**Why so strict?** A tool that watches your work must be trustworthy. And even with all this,
live testing found real bugs ([History](08_history_and_lessons.md#bugs-found-and-what-they-taught-us)).
Every bug became a test. **All four checks must pass before any commit**
([Developing](06_developing.md#the-quality-gate)).

---

## Packaging

**What it is.** Turning the code into an installable program that gives you a `grymbl` command.

- **`pyproject.toml`** is the standard file describing a Python project: name, version,
  dependencies, the `grymbl` command's entry point, and tool settings.
- A **build backend** is the tool that packages the code. We use **hatchling** (modern and
  minimal). The alternative, setuptools, is older and more configuration-heavy.
- **`uv tool install --editable .`** installs `grymbl` onto your `PATH`. *Editable* means it
  runs straight from the code folder, so code changes take effect without reinstalling.

The shell hook scripts (`grymbl.bash`, `.zsh`, `.ps1`) ship *inside* the package, so
`grymbl shell-hook bash` works wherever Grymbl is installed.

The package is marked `Private :: Do Not Upload`, so it can't be accidentally published to
PyPI, the public Python catalogue.

---

## Storage

**What it is.** Where Grymbl keeps its memory ([Foundations](01_foundations.md#databases-and-sql)).

| Option | What it is | Verdict |
|---|---|---|
| **SQLite** | A full database in one file, built into Python | ✅ Chosen |
| PostgreSQL / MySQL | Powerful database *servers* | ❌ A server to install and keep running (P2, P6) |
| Neo4j / Amazon Neptune | *Graph* databases, specialised for connected data | ⏸ Planned for scale (P7) |
| Plain JSON files | Text files | ❌ Unsafe when several processes write at once; slow to search |

**Why SQLite:** no server, no cost, one file, nothing to set up (P2, P6). Far more than
enough for one developer's history.

**How it's configured:** WAL mode, so the watcher and many hook processes can write at once;
a 10-second wait when the file is momentarily busy; automatic
[migrations](01_foundations.md#migrations) when new columns are added.

**Gave up:** graph-shaped questions ("which assumptions were contradicted by episodes that
built on this one?") are awkward in plain tables. That's fine for 3 node types and 2
relationships, and the move to a graph database is planned for when that changes.

---

## File watching

**What it is.** Getting told when files change ([Sensor 1](03_how_it_works.md#sensor-1-the-file-watcher)).

| Option | How it works | Verdict |
|---|---|---|
| **watchdog** | A library wrapping each OS's native notification system: *inotify* (Linux), *FSEvents* (macOS), *ReadDirectoryChangesW* (Windows) | ✅ Chosen |
| Polling | Re-read every file every few seconds | ❌ Wasteful and slow to notice (P4) |
| Native OS APIs directly | Write three platform-specific versions | ❌ Triple the work (P6) |
| Editor save events | Hook into the editor | ❌ Needs an editor plugin; misses changes from terminals and agents |

**Why:** one library, three platforms (P5, P6), and the OS pushes changes to us instead of us
checking constantly (P4).

**Lesson:** OS notifications describe *events*, and events can mislead (atomic saves look like
deletions). That's why Grymbl also judges by **content** (hashes) and waits before believing
deletions.

---

## Terminal capture

**What it is.** Learning which commands the developer types, and whether they succeeded
([Sensor 2](03_how_it_works.md#sensor-2-the-terminal-hooks)).

| Option | How it works | Verdict |
|---|---|---|
| **Shell hooks** | Each shell's built-in "run this after every command" slot | ✅ Chosen |
| Reading history files | Read `~/.bash_history` afterwards | ❌ No exit codes; delayed; written only when the shell closes |
| Recording the whole session | Tools like `script` record everything on screen | ❌ Heavy, and records every output, secrets included (P3) |
| Wrapping the shell | Run the shell inside a Grymbl-controlled terminal | ❌ Fragile and invasive (P4) |

**Why hooks:** official, lightweight, and they give exactly what's needed: the command and its
exit code (P4).

**Gave up:** three small scripts to keep in step (bash, zsh, PowerShell). They're kept thin:
each just hands the command to the same Python code, so the real logic, redaction included,
exists once.

---

## Git capture

**What it is.** Learning about commits and pushes ([Sensor 3](03_how_it_works.md#sensor-3-the-git-hooks)).

| Option | Verdict |
|---|---|
| **Git's own hooks** (`post-commit`, `pre-push`) | ✅ Chosen: built into git, instant, local |
| Periodically reading `git log` | ❌ Delayed and wasteful |
| GitHub webhooks (GitHub calling a web address you run) | ❌ Needs a server (P2); only sees pushes |

---

## Test results

**What it is.** Knowing how many tests passed and failed ([Sensor 4](03_how_it_works.md#sensor-4-test-runs)).

| Option | Verdict |
|---|---|
| **Structured JSON reports** from the test tools themselves | ✅ Chosen: pytest (with the `pytest-json-report` add-on), Jest `--json`, `go test -json` |
| Reading the text printed on screen | ❌ Breaks whenever a tool changes its wording |

**Gave up:** you type `grymbl test -- pytest` instead of `pytest`, and Python projects need one
extra add-on.

---

## Coding agent capture

**What it is.** Seeing what an AI coding agent was asked, did, and claimed
([Sensor 5](03_how_it_works.md#sensor-5-coding-agents)).

| Option | Verdict |
|---|---|
| **Claude Code hooks** | ✅ Chosen for now: official, structured, real-time, local, and needs no cooperation from the agent |
| Reading session transcripts afterwards | Partly used: the Stop hook reads the transcript for the agent's narrative |
| Wrapping the agent program | ❌ Invasive and fragile |
| Telemetry export (the agent sending metrics to a monitoring system) | ❌ Needs extra infrastructure (P2, P6) |
| **MCP tools the agent calls** ([Foundations](01_foundations.md#mcp)) | ⏭ Next step: lets agents *declare* assumptions, and works across many agents |

**Why hooks first:** they capture ground truth even if the agent ignores every instruction.
**Gave up:** Claude Code only, for now. Other agents need adapters or the MCP route.

---

## Secret detection

**What it is.** Finding and masking secrets before anything is saved
([Redaction](03_how_it_works.md#redaction)).

| Option | What it is | Verdict |
|---|---|---|
| **Own regex patterns** | A small set of text-shape rules | ✅ Chosen |
| gitleaks, detect-secrets, trufflehog | Established secret *scanners* | Excellent, but built to scan whole files and repos and *report* secrets, not mask part of a command line. Heavier. A good future source of patterns |
| An AI model | Ask an LLM "is there a secret here?" | ❌ That sends the secret to the AI, defeating the purpose (P3). The plan forbids it |

**Why:** fully local (P3), fast, and it masks *only* the secret so the context survives.
**Gave up:** coverage of every possible secret format. The plan accepts that.

---

## Finding related files

**What it is.** Knowing which project files import which ([Episodes](03_how_it_works.md#episodes)).

| Option | Verdict |
|---|---|
| **Regex scan of import lines** | ✅ Chosen: cheap, no dependencies, handles the common cases in Python and JS/TS |
| Real parsers (Python's `ast`, tree-sitter) | More exact, but one approach per language, or a large dependency |
| Language servers (the engines behind editor autocomplete) | ❌ Heavy; one per language |
| An AI model | ❌ The plan says no LLM here: too slow and costly for every save |

**Gave up:** unusual import styles may be missed, and Go isn't covered yet.

---

## Detecting real changes

| Job | Chosen | What it is | Alternatives | Why |
|---|---|---|---|---|
| Fingerprinting | **SHA-256** (`hashlib`) | The standard secure [hash](01_foundations.md#hashing) | MD5/SHA-1 (older); xxhash (faster, extra dependency) | Built in, trusted, collisions practically impossible |
| Describing changes | **difflib** unified diffs | Python's built-in [diff](01_foundations.md#diffs) maker | Calling `git diff` | Works even on files git doesn't track yet; no dependence on git's state |

---

## The AI model

**What it is.** The LLM that analyses escalated episodes ([Sonnet](03_how_it_works.md#sonnet)).

| Model | Price per million tokens (in / out) | Character |
|---|---|---|
| Claude Haiku 4.5 | $1 / $5 | Fast, cheap, lighter reasoning |
| **Claude Sonnet 5** | **$2 / $10** | ✅ Chosen: strong reasoning at moderate cost |
| Claude Opus 5 | $5 / $25 | Stronger; 2.5× the price |
| Claude Fable 5.1 | $10 / $50 | The most capable; 5× the price |

**Why Sonnet:** the plan names it (§9.1). It's capable enough to reliably say "insufficient
evidence" instead of guessing, and cheap enough for every escalation. Measured: about US$0.005
per small episode.

**Where AI is deliberately *not* used:** triage (Jev), secret detection, and import scanning.
Those stay rule-based: instant, free, predictable, private.

**Tuned for cost:** medium effort, 25 calls a day, evidence capped around 25,000 tokens
([Cost controls](03_how_it_works.md#cost-controls)).

---

## Talking to the AI

**What it is.** The code path that sends evidence to Sonnet and gets an answer
([Foundations: APIs](01_foundations.md#apis-and-http)).

| Option | Verdict |
|---|---|
| **Anthropic's official Python SDK** | ✅ Chosen |
| Hand-written web requests | ❌ Reinvents retries, error types, and parsing |
| Generic multi-provider libraries | ❌ An extra layer between us and Claude's features |

**SDK features relied on:**
- **Structured output** via `client.messages.parse(…, output_format=EpisodeAnalysis)`, where
  `EpisodeAnalysis` is a Pydantic model. The SDK checks Sonnet's answer has the right shape.
- **Typed errors** (`RateLimitError`, `APIStatusError`, `APIConnectionError`,
  `AuthenticationError`, `CredentialsError`), so each failure gets the right handling.
- **Automatic retries** on temporary failures.
- **`output_config={"effort": "medium"}`** to control thinking depth.
- **`response.usage`** for exact token counts, which are logged.

**Credentials:** the SDK reads `ANTHROPIC_API_KEY` from the environment. It's never in code or
files.

---

## Command line

**What it is.** The `grymbl` command itself ([Foundations](01_foundations.md#command-line-interfaces)).

| Option | Verdict |
|---|---|
| **argparse** (standard library) | ✅ Chosen |
| click / typer | Nicer to write, but extra dependencies and slower start |

**Why:** hooks run `grymbl capture-…` after *every* command and *every* agent action, so a
lean start matters (P4), and it adds no dependency (P6).

---

## Delivering warnings

| Option | Verdict |
|---|---|
| **Local markdown file + the watcher's window** | ✅ Chosen: the plan's v1 default |
| Desktop notifications | Later: different on each OS |
| Slack / email | ❌ External services (P2, P3) |
| Telling the AI agent directly | ⏭ Planned (v1.1 step 3) |

---

## Hosting and ownership

| Item | Choice | Why |
|---|---|---|
| Version control | **git** | The universal standard |
| Hosting | **GitHub, private** (`maurya-65/Grymbl`) | Backup, history, access control |

---

## What changes at scale

From plan §9.2. Each layer is picked for its own constraints:

| Layer | Now | At scale | Why change |
|---|---|---|---|
| Local agent | Python | Go → Rust | Runs on every laptop all day: must be tiny, a single file, no pauses |
| Editor plugins | — | TypeScript (VS Code), Kotlin (JetBrains) | Dictated by each editor |
| Collecting events from many machines | — | Go | Cheap handling of traffic bursts |
| Team/company memory and AI orchestration | Python | Python, on servers | Best AI and data libraries |
| Experience Graph | SQLite | Neo4j / Amazon Neptune | Richer relationships, cross-team questions |
| Dashboard | — | TypeScript + Next.js | The web standard |

---

## The whole stack on one page

| Area | Choice |
|---|---|
| Shape | Local program, no servers |
| Language | Python 3.12+ |
| Tooling | uv (`uv.lock`), hatchling, `pyproject.toml` |
| Quality | ruff, mypy (strict), pytest (100+ tests) |
| Storage | SQLite (WAL), one file per project |
| Files | watchdog + SHA-256 + difflib |
| Terminal | bash / zsh / PowerShell hooks |
| Git | `post-commit`, `pre-push` hooks |
| Tests | JSON reports: pytest, Jest, go test |
| Agents | Claude Code hooks (MCP next) |
| Secrets | Local regex redaction |
| Related files | Regex import scan (Python, JS/TS) |
| Triage | Jev: 4 deterministic rules |
| AI | Claude Sonnet 5 via the official SDK; structured output; medium effort; capped |
| CLI | argparse |
| Warnings | `.grymbl/interventions.md` + watcher window |
| Hosting | Private GitHub |
| Runtime dependencies | 3: `anthropic`, `pydantic`, `watchdog` |

---

<sub>Next: [Chapter 5: Codebase Tour](05_codebase_tour.md). Copyright © 2026 Maurya Oganja. All rights reserved.</sub>

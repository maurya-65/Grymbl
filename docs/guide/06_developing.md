# Chapter 6: Developing

*Setting up from scratch, the rules for changing code, and step-by-step recipes.*

This is the chapter for whoever takes over the code.

---

## Setting up from zero

You need four things. Commands are shown for Windows PowerShell; macOS/Linux equivalents are
in brackets.

| # | Install | Why | How to check |
|---|---|---|---|
| 1 | **Git** ([git-scm.com](https://git-scm.com)); on Windows this includes Git Bash | Version control; git hooks need it | `git --version` |
| 2 | **Python 3.12 or newer** ([python.org](https://www.python.org)) | The language | `python --version` |
| 3 | **uv** | Project and dependency manager ([Tech Stack](04_tech_stack.md#project-and-dependency-management)) | `python -m pip install uv`, then `python -m uv --version` |
| 4 | **GitHub CLI** (`gh`, [cli.github.com](https://cli.github.com)) | Access to the private repo | `gh auth login`, then `gh auth status` |

Then:

```powershell
gh repo clone maurya-65/Grymbl C:\dev\Grymbl     # (macOS/Linux: any folder)
cd C:\dev\Grymbl
python -m uv sync                                 # creates .venv/ and installs exact versions from uv.lock
python -m uv run pytest -q                        # should print "96 passed"
```

If all tests pass, your setup is correct.

> `python -m uv …` and plain `uv …` do the same thing. Use whichever works on your machine.

---

## The quality gate

**All four must pass before every commit.** This is a rule, not a suggestion.

```powershell
uv run ruff format .        # 1. formats the code (rewrites files)
uv run ruff check .         # 2. lint: likely bugs and bad patterns
uv run mypy                 # 3. strict type check of src/ and tests/
uv run pytest -q            # 4. all tests
```

| If this fails | It means | Usually fix by |
|---|---|---|
| `ruff check` | A likely bug or style problem; the message says which | Read the message. `uv run ruff check --fix .` fixes the simple ones |
| `mypy` | A value's type doesn't match its label, or something is unlabelled | Add or fix the type hint, or fix the logic that produces the wrong type |
| `pytest` | Behaviour changed | Decide: is the code wrong, or did the expected behaviour legitimately change? Never delete a test just to make it pass |

---

## Running Grymbl from the code folder

Without installing anything globally:

```powershell
uv run grymbl --help
uv run grymbl init C:\path\to\some\project
```

**To make hooks work** (they call plain `grymbl`), either install it globally:

```powershell
uv tool install --editable C:\dev\Grymbl        # puts `grymbl` on PATH; code edits apply immediately
```

…or, for a single test session, put the project's environment first on `PATH`:

```powershell
$env:PATH = "C:\dev\Grymbl\.venv\Scripts;" + $env:PATH      # (bash: export PATH="/path/Grymbl/.venv/bin:$PATH")
```

---

## A safe sandbox for trying changes

Never experiment on a real project's `.grymbl` history. Make a throwaway one:

```powershell
mkdir $env:TEMP\grymbl-demo; cd $env:TEMP\grymbl-demo
git init
mkdir app, tests
Set-Content app\auth.py "TTL = 3600`n`ndef check(t):`n    return t < TTL`n"
Set-Content tests\test_auth.py "from app import auth`n`ndef test_ok():`n    assert auth.check(1)`n"
uv run --project C:\dev\Grymbl grymbl init .
uv run --project C:\dev\Grymbl grymbl watch .          # in a second terminal
```

Then edit files, run commands, and commit, and inspect the results:

```powershell
uv run --project C:\dev\Grymbl grymbl status
python -c "import sqlite3; [print(r) for r in sqlite3.connect('.grymbl/grymbl.db').execute('select event_id, kind, files, episode_id from events')]"
```

**To shorten the 5-minute wait while testing**, lower `idle_gap` in `config.py` temporarily,
and put it back before committing.

> **Windows gotcha:** Git Bash's `timeout` command does *not* stop the Python process a
> launcher starts, so "timed-out" watchers can keep running invisibly. Stop stray watchers with
> PowerShell:
> `Get-CimInstance Win32_Process | ? { $_.CommandLine -match 'grymbl(\.exe)?"? watch' } | % { Stop-Process -Id $_.ProcessId -Force }`

---

## Code standards

The standards, with the reasons:

| Standard | Why |
|---|---|
| Full type hints; `mypy --strict` clean | Catches whole classes of bugs before anything runs |
| `from __future__ import annotations` at the top of every file | Consistency; cheaper type hints |
| Keep pure logic (`correlate`, `jev`, `redact`, `dedup`, `imports`) free of input/output | Trivial to test; easy to reason about |
| SQL only in `store.py`; network only in `reasoning.py` | Anyone can find (and audit) where data is stored and sent |
| Frozen dataclasses for data; small functions; no speculative abstractions | Simple code survives handovers |
| Match surrounding code. Comments explain *why*, not *what* | The code says what; comments carry the reasoning that isn't visible |
| Handle errors where you can act on them. At hook boundaries, catch everything and log | Hooks must never disturb the developer |
| For `anthropic` errors, catch specific error types, most specific first | Each failure needs different handling |
| Every behaviour change comes with a test; every bug found gets a test | Stops regressions quietly returning |

---

## Writing tests

- Put tests in `tests/test_<module>.py`, and name each test after the behaviour it proves:
  `test_pure_rename_is_dropped`, not `test_rename_2`.
- Use the **fixtures** `settings` (a temporary project) and `store` (a fresh database) by
  naming them as parameters:

  ```python
  def test_something(store: Store, settings: Settings) -> None:
      ...
  ```

- Build events with `tests/helpers.py`: `change("app/auth.py", minute=0)`,
  `command("make", 1, exit_code=2)`, `ran_tests(2, failed=0)`,
  `agent_event(EventKind.AGENT_PROMPT, 0, prompt="…")`. Times are minutes after a fixed start,
  via `at(minutes)`.
- **Never call the real API in tests.** Use `FakeAnalyst` and `RecordingSink` from
  `tests/test_pipeline.py`, or `monkeypatch` the client (see `test_cost_controls.py`).
- Test the *unhappy* paths too: the benign command that must not be redacted, and the rule
  that must *not* fire.
- For helpers that happen to start with `test`, don't. pytest would try to run them as tests
  (that's why the helper is called `ran_tests`, not `test_run`).

---

## Recipes for common changes

Each recipe lists every file to touch, in order. Finish every recipe with the
[quality gate](#the-quality-gate).

### Change a setting (time windows, thresholds, cost caps)

1. Edit the default in `Settings` in `src/grymbl/config.py` (or `MAX_EVIDENCE_CHARS` /
   `MAX_HISTORY` in `reasoning.py`).
2. Update the numbers in [Chapter 3](03_how_it_works.md) and [Chapter 7](07_operating.md).

> There's no user-editable configuration file yet: settings are code defaults. Adding one is
> in the [backlog](09_status_and_roadmap.md#the-backlog).

### Add a redaction pattern

1. In `src/grymbl/redact.py`, add a compiled pattern with **two groups**: group 1 is the
   context to keep, group 2 is the secret.
2. Add it to `redact()` in the right order (more specific patterns first).
3. In `tests/test_redact.py`, add a case to `test_masks_only_the_secret`, **and** a lookalike
   that must stay untouched to `test_leaves_ordinary_commands_alone`.
4. **Performance:** avoid unbounded `[\w…]*` on both sides of a word. Anchor with a lookbehind
   like `(?<![\w.-])` and use bounded repeats like `{0,64}`. `test_long_lines_redact_in_linear_time`
   will catch slow patterns.

### Add or change a Jev rule

1. Add a helper function in `src/grymbl/jev.py` and call it from `triage()`, appending a
   readable reason.
2. If the rule's result should be stored on the episode, add a column
   ([recipe below](#add-a-database-column)) and a field to `Triage` and `ClosedEpisode`.
3. Add tests to `tests/test_jev.py`: when it fires, *and* when it mustn't.
4. Think about cost: a rule that fires often means more Sonnet calls.
5. Update [Chapter 3: Jev](03_how_it_works.md#jev).

### Add a new event kind

1. Add it to `EventKind` in `src/grymbl/events.py`.
2. Produce it from a sensor, redacting any text a person or agent wrote.
3. Add a `case` for it in `_render_event` in `reasoning.py`, so Sonnet can read it. (mypy
   flags a missing return if you forget.)
4. Decide how it groups: should it be a "context" kind in `correlate.py` (`_CONTEXT_KINDS`)?
   Should it count as a failure (`Event.failed`)?
5. Update the event tables in [Chapter 3](03_how_it_works.md#events).

### Add a database column

1. Add the column to the `CREATE TABLE` in `_SCHEMA` (`src/grymbl/store.py`), for new
   databases.
2. Add it to `_ADDED_COLUMNS`, so existing databases get it on the next start.
3. Update the dataclasses and queries that read or write it.
4. Extend `test_store_migrates_databases_created_before_v1_1` in `tests/test_pipeline.py` (or
   add a similar test).

### Support another test runner

1. `src/grymbl/sensors/tests.py`: add a `Runner` value, teach `detect_runner()` to recognise
   the command, add a branch in `run_and_capture()` that adds the tool's JSON-report flag, and
   write a `parse_<tool>()` returning a `TestRun`.
2. Add a parser test with a real sample report in `tests/test_tests_sensor.py`.

### Support another shell

1. Write `src/grymbl/hooks/grymbl.<shell>`, mirroring the bash one: only inside watched
   repos, run in the background, send the command via stdin, and never print.
2. Register it in `SHELLS` in `cli.py`.
3. Add it to the table in [Chapter 7](07_operating.md#loading-the-terminal-hook).

### Support another AI agent

1. Create `src/grymbl/sensors/<agent>.py`, modelled on `agent.py`: one capture entry point
   producing the **same** event kinds (`agent_prompt`, `command`, `agent_tool`,
   `agent_turn_end`) with `agent` and `session_id` in the payload. Correlation then works
   unchanged.
2. **Capture real payloads first** (see [Lessons](08_history_and_lessons.md#bugs-found-and-what-they-taught-us)):
   point the agent's hooks at a tiny script that appends its input to a file, run one short
   session, and build the parser and tests from what actually arrived.
3. Add a `capture-<agent>` subcommand and an installer called from `_init`.

### Change the model or the prompt

1. The model name is `SONNET_MODEL` in `config.py`; the prompt is `SYSTEM_PROMPT` in
   `reasoning.py`.
2. **Keep `EVIDENCE_RULE` word for word.** It's locked by the plan (§11).
3. Verify with **one** real call on a small episode before relying on it: it costs about a
   cent, and the log shows the exact tokens.

---

## Git workflow

- Work on `main` for now (solo project); push after each logical change.
- **Small, focused commits**, with an imperative subject line: "Add X", "Fix Y". Add a body
  explaining *why* when it's not obvious.
- Commit under the owner's name.
- Never commit `.grymbl/`, `.venv/`, secrets, or `.claude/settings.local.json`.

---

## Never do this

| Don't | Why |
|---|---|
| Store or log a raw command, prompt, or narrative before `redact()` | Breaks the privacy promise ([invariant 1](03_how_it_works.md#safety-invariants)) |
| Call any network service outside `reasoning.py` | Breaks the local-only promise |
| Add a Sonnet call that skips Jev, the daily cap, or the evidence cap | Uncapped cost |
| Make a hook print, wait, or exit non-zero | It would disturb the developer or block git |
| Edit `EVIDENCE_RULE` | Locked by the plan |
| Trim evidence before redacting it | Can leak part of a secret |
| Trust documentation for a third-party message format without capturing a real sample | It was wrong before |
| Delete or weaken a test to make it pass | It exists because something broke once |

---

<sub>Next: [Chapter 7: Operating](07_operating.md). Copyright © 2026 Maurya Oganja. All rights reserved.</sub>

# Chapter 1: Foundations

*Every computing idea Grymbl relies on, explained from zero.*

Each section follows the same pattern:

- **What it is**, in plain words.
- **An analogy** from everyday life.
- **Why it matters**, and a pointer to **where Grymbl uses it**.

You don't need to memorise anything. Read it once, then come back when a later chapter links
here. The [Glossary](glossary.md) has short versions of every term.

---

## Part A: Computers and programs

### Files folders and paths

**What it is.** A **file** is a named container of data on a disk: a document, a photo, a
piece of code. A **folder** (also called a **directory**) holds files and other folders,
forming a tree. A **path** is the address of a file in that tree, for example
`C:\dev\Grymbl\src\grymbl\jev.py` on Windows or `/home/maurya/Grymbl/src/grymbl/jev.py` on
macOS/Linux.

- An **absolute path** starts from the very top (`C:\` or `/`).
- A **relative path** starts from wherever you are now (`src/grymbl/jev.py`).
- Windows separates folders with `\`. macOS and Linux use `/`. Grymbl stores every path in the
  `/` style ("POSIX style"), relative to the project's top folder, so the same file has the
  same name on every computer.

**Analogy.** A path is a street address: country → city → street → house. A relative path
is directions from where you're standing: "two doors down".

**In Grymbl.** Every event records files as relative `/`-style paths, like `app/auth.py`. See
[Events](03_how_it_works.md#events).

### Text files binary files and encoding

**What it is.** Computers store everything as numbers. A **text file** holds numbers that stand
for letters. The rule mapping numbers to letters is the **encoding**; **UTF-8** is the standard
encoding that covers every language and emoji. A **binary file** (an image, a compiled program)
holds numbers that aren't letters at all.

**Analogy.** An encoding is a codebook. The same numbers read with the wrong codebook produce
gibberish.

**In Grymbl.** The file watcher only reads text files. It skips any file containing a zero
byte, or that isn't valid UTF-8, because those are binary, and diffs of binary data are
meaningless. See [Sensor 1](03_how_it_works.md#sensor-1-the-file-watcher).

### Programs and processes

**What it is.** A **program** is a set of instructions stored in files. When you start it, the
operating system creates a **process**: a running instance of that program, with its own
memory. The same program can run as several processes at once.

**Analogy.** A program is a recipe in a book. A process is someone actually cooking that recipe
in a kitchen right now. Two cooks can follow the same recipe at the same time.

**In Grymbl.** `grymbl watch` is one long-lived process. Every time you type a command, the
terminal hook starts a *separate*, short-lived `grymbl` process that records it and exits. See
[The main loop](03_how_it_works.md#the-main-loop).

### Background processes and daemons

**What it is.** A **background process** runs without you interacting with it. A **daemon**
is a background process that runs continuously, waiting for things to happen.

**Analogy.** A security guard on night shift: always there, mostly quiet, reacting only when
something happens.

**In Grymbl.** The watcher (`grymbl watch`) is Grymbl's daemon. The hooks also launch their
`grymbl` processes in the background, so you never wait for them.

### Operating systems

**What it is.** The **operating system** (OS) is the base software that runs the computer and
lets programs use the disk, screen, network, and memory: Windows, macOS, or Linux. Each does
the same jobs differently.

**In Grymbl.** Grymbl runs on all three. Where they differ (how file changes are reported,
which shell people use, how locks work), Grymbl has a branch for each. See
[Tech Stack](04_tech_stack.md).

---

## Part B: The terminal

### The terminal and the shell

**What it is.** The **terminal** is a window where you type commands as text instead of
clicking. Inside it runs a **shell**: the program that reads your command, runs it, and shows
the result. Common shells:

| Shell | Where |
|---|---|
| **bash** | Linux; on Windows via "Git Bash" |
| **zsh** | The default on macOS |
| **PowerShell** | Windows |

**Analogy.** The terminal is a phone line to your computer. The shell is the operator who
understands what you ask and connects you to the right program.

**In Grymbl.** Grymbl needs to know which commands you run, so it plugs into all three shells.
See [Sensor 2](03_how_it_works.md#sensor-2-the-terminal-hooks).

### Commands arguments and options

**What it is.** A **command** is an instruction typed into the shell, like `git commit -m "fix"`.
It has parts:

- The **program** to run: `git`.
- **Arguments**: extra words telling it what to do: `commit`, `"fix"`.
- **Options** (or **flags**): arguments starting with `-` or `--` that switch behaviours on:
  `-m` means "the message follows".

**In Grymbl.** Secrets often hide in arguments (`--password hunter2`), which is why Grymbl
removes them before saving. See [Redaction](03_how_it_works.md#redaction).

### Standard input and output

**What it is.** Every process has three built-in channels:

| Channel | Short name | Purpose |
|---|---|---|
| Standard input | **stdin** | Data flowing *into* the program |
| Standard output | **stdout** | Normal results flowing *out* |
| Standard error | **stderr** | Error messages flowing out |

The `|` symbol (a **pipe**) connects one program's stdout to the next program's stdin:
`printf 'hello' | grymbl capture-command` sends "hello" into Grymbl.

**Analogy.** A process is a machine on an assembly line, with one conveyor belt in and two
out: one for finished products, one for rejects.

**In Grymbl.** The terminal hooks pass your command to Grymbl through **stdin**, not as an
argument. Arguments are visible to other programs on the computer (in the process list), so a
secret would be briefly exposed before redaction. stdin isn't visible that way.

### Exit codes

**What it is.** When a program finishes, it returns a number called its **exit code**. `0`
means success. Anything else means a failure of some kind, and the number often says which
kind.

**Analogy.** A thumbs-up (0) or a thumbs-down with a finger count saying what went wrong.

**In Grymbl.** Exit codes are how Grymbl knows a command failed, which drives
[Jev's rule 2](03_how_it_works.md#jev) ("something failed, then got fixed").

### Environment variables

**What it is.** An **environment variable** is a named value the operating system hands to
every program it starts. Names are usually in capitals: `PATH`, `HOME`,
`ANTHROPIC_API_KEY`. They can be set for one terminal session only, or permanently for your
user account.

- **`PATH`** is special: it lists the folders where the shell looks for programs. Typing
  `grymbl` works only if the folder containing `grymbl` is on your `PATH`.

**Analogy.** Sticky notes the operating system puts on every program's desk before it starts
working.

**In Grymbl.** The AI key is read from `ANTHROPIC_API_KEY`, so it's never written in code or
files. See [Operating](07_operating.md#setting-the-api-key).

---

## Part C: Version control

### Version control and git

**What it is.** **Version control** records every saved state of a project, so you can see
what changed, when, why, and by whom, and go back if needed. **Git** is the standard
version-control tool. Key words:

| Term | Meaning |
|---|---|
| **Repository** (repo) | A project folder whose history git tracks. The history lives in a hidden `.git` folder inside it |
| **Commit** | A saved snapshot of the project, with a message ("Fix login timeout") and a unique ID like `3e2d104` |
| **Branch** | A separate line of work, so experiments don't disturb the main version (`main`) |
| **Working tree** | The files as they are on disk right now, which may include changes not yet committed |

**Analogy.** A lab notebook where every page is dated and signed, and pages are never torn
out. You can always look back at page 12.

**In Grymbl.** Grymbl watches git activity ([Sensor 3](03_how_it_works.md#sensor-3-the-git-hooks)),
and Grymbl's own code is kept in git.

### GitHub and remotes

**What it is.** **GitHub** is a website that hosts copies of git repositories online. A
**remote** is a named online copy of your repo (usually called `origin`). **Push** uploads
your commits to the remote; **pull** downloads others'. A **private** repository is visible
only to people you invite.

**In Grymbl.** The code lives at `github.com/maurya-65/Grymbl`, a private repository.

### Ignoring files with gitignore

**What it is.** A file named **`.gitignore`** lists files git should never track, such as
passwords, caches, or generated files. A `.gitignore` containing just `*` means "ignore
everything in this folder".

**In Grymbl.** Grymbl's data folder `.grymbl/` contains a `.gitignore` with `*`, so your
activity history can never be committed and pushed by accident. See
[Setup](03_how_it_works.md#setup-with-grymbl-init).

---

## Part D: Hooks

### Hooks

**What it is.** A **hook** is a spot a program deliberately leaves open, where you can plug
in your own small script, and the program will run it automatically at a certain moment.

The program says, in effect: *"whenever X happens, I'll run whatever you've put here."* You
don't change the program itself; you just fill the slot.

**Analogy.** A doorbell. The house (the program) was built with a button by the door (the
hook). You decide what the button does: ring a chime, send a text to your phone. The house
doesn't care, as long as something is connected.

**Another analogy.** A hotel wake-up call. You don't run the hotel, but you can register a
request ("call me at 7am") and it happens automatically.

**Why hooks matter so much.** Grymbl has to learn about activity inside other programs (your
shell, git, Claude Code) without modifying those programs. Hooks are the official way to do
that. They're lightweight, supported, and easy to remove.

**The three kinds of hook Grymbl uses:**

| Program | Its hook | When it fires | What Grymbl's script does |
|---|---|---|---|
| **Your shell** (bash, zsh, PowerShell) | bash's `PROMPT_COMMAND`, zsh's `preexec`/`precmd`, PowerShell's `prompt` function | Every time a command finishes and the shell is about to show a new prompt | Sends the command and its exit code to Grymbl |
| **Git** | Script files in `.git/hooks/` named after moments: `post-commit`, `pre-push` | Right after a commit; right before a push | Tells Grymbl about the commit or push |
| **Claude Code** | Entries in its settings file, for moments like `UserPromptSubmit`, `PostToolUse`, `Stop` | When you send a request, after each action the AI takes, when it finishes | Sends the prompt, action, or summary to Grymbl |

For example, here is the whole git hook script Grymbl installs as `.git/hooks/post-commit`:

```sh
#!/bin/sh
# grymbl-hook
command -v grymbl >/dev/null 2>&1 || exit 0
grymbl capture-git post-commit "$@" >/dev/null 2>&1 || true
exit 0
```

Line by line: *"this is a shell script"* → *"a marker so Grymbl can recognise its own hook"* →
*"if grymbl isn't installed, quietly stop"* → *"tell Grymbl a commit happened, hide any output,
ignore any error"* → *"always report success"*. That last line matters: if a git hook reports
failure, git can refuse the commit, and Grymbl must never get in your way.

**In Grymbl.** Sensors 2, 3 and 5 in [How It Works](03_how_it_works.md) are all hooks.

---

## Part E: Code, libraries, and quality

### Programming languages

**What it is.** A **programming language** is a precise way of writing instructions for a
computer. Some are **compiled** (translated ahead of time into machine code: fast, like Go or
Rust). Others are **interpreted** (read and run on the fly: easier and faster to write, like
Python). Grymbl is written in **Python**. [Tech Stack](04_tech_stack.md#programming-language)
explains why.

### Libraries dependencies and packages

**What it is.** A **library** is reusable code someone else wrote: for example, code that
watches folders for changes. When your program relies on a library, that library is a
**dependency**. Libraries are distributed as **packages**, installed from public catalogues
(Python's is called **PyPI**). A language's **standard library** is the set of libraries that
come built in, needing no install.

**Analogy.** Buying flour instead of growing wheat. Dependencies save time, but you depend on
their quality, and every extra one is something that can break.

**In Grymbl.** Only three outside dependencies: `anthropic`, `pydantic`, `watchdog`. Everything
else uses Python's standard library. See
[Tech Stack](04_tech_stack.md#project-and-dependency-management).

### Virtual environments and lock files

**What it is.** A **virtual environment** is a private folder of libraries for one project, so
two projects needing different versions of the same library don't clash. A **lock file**
records the *exact* version of every dependency, so every installation is identical.

**In Grymbl.** The environment lives in `.venv/`, and the lock file is `uv.lock`, managed by a
tool called **uv**. See [Developing](06_developing.md).

### Type hints and type checking

**What it is.** Values have **types**: a number, text (a **string**), a list, true/false (a
**boolean**). **Type hints** are labels in the code saying what type each value should be:
`exit_code: int` means "a whole number". A **type checker** reads the whole codebase and
reports any place where the labels don't fit, *before* the code runs.

**Analogy.** Labelled electrical plugs that physically don't fit the wrong socket. Mistakes
are caught when you try to connect, not when something catches fire.

**In Grymbl.** Every value is labelled, and the checker **mypy** runs in *strict* mode (no
unlabelled values allowed).

### Linting and formatting

**What it is.** A **linter** scans code for likely bugs and bad patterns, like a spell-checker
for code. A **formatter** rewrites code into one consistent layout, so style never has to be
discussed.

**In Grymbl.** One tool, **ruff**, does both.

### Automated tests and fakes

**What it is.** An **automated test** is a small program that runs part of your code and checks
the result: *"when I redact `export API_KEY=abc`, I must get `export API_KEY=[REDACTED]`"*. A
**test suite** is all of them together, runnable with one command. A **fake** (or **stub**) is a
stand-in for something slow, expensive, or external, such as the AI model, so tests stay free,
fast, and predictable.

**Analogy.** A fire drill. You check that everything works under controlled conditions, often,
and cheaply, instead of waiting for a real fire.

**In Grymbl.** Over 100 tests, run with **pytest**. Sonnet is replaced by a fake that returns a
fixed answer. Whenever a bug is found, a test is added so it can't quietly return. See
[Developing](06_developing.md#writing-tests).

### Command line interfaces

**What it is.** A **CLI** (command-line interface) is a program you control by typing commands.
It usually has **subcommands**: in `git commit`, `commit` is a subcommand of `git`.

**In Grymbl.** `grymbl` is a CLI with subcommands `init`, `watch`, `status`, `test`,
`shell-hook`, and three hidden ones the hooks call. See
[Operating](07_operating.md#everyday-commands).

---

## Part F: Data and storage

### JSON

**What it is.** **JSON** is a simple, universal text format for structured data:

```json
{"runner": "pytest", "passed": 3, "failed": 1, "failed_tests": ["test_login"]}
```

Curly braces hold named fields, and square brackets hold lists. Almost every program can read
and write it.

**In Grymbl.** Test reports, Claude Code's hook messages, event details stored in the
database, and Sonnet's answers are all JSON.

### Databases and SQL

**What it is.** A **database** stores information so programs can find and update it reliably
and quickly. The common kind is a **relational database**, organised into **tables**:

- A **table** is like a spreadsheet tab with fixed **columns** (`episode_id`, `developer`,
  `escalated`, …).
- Each **row** is one record (one episode).
- A **primary key** is the column that uniquely identifies each row (like a passport number).
- The **schema** is the full design: which tables exist and which columns each has.
- **SQL** is the language used to ask a database questions: `SELECT * FROM episodes WHERE
  escalated = 1` means "show me all escalated episodes".

**Analogy.** A well-organised filing cabinet with an index. SQL is the librarian you ask:
"find me every file about auth from last week".

**In Grymbl.** Seven tables, described column by column in
[Storage](03_how_it_works.md#storage).

### SQLite and WAL

**What it is.** **SQLite** is a complete database stored in a single file. There's no separate
server program to install or keep running. It's built into Python and used by browsers and
phones everywhere.

**WAL** (write-ahead logging) is a SQLite mode that lets several processes read and write the
same database at the same time, safely. Changes go to a side file first and are merged in
safely afterwards.

**In Grymbl.** The whole memory is `.grymbl/grymbl.db`. WAL matters because the watcher and
many hook processes write at once.

### Transactions

**What it is.** A **transaction** groups several database changes so that either *all* of
them happen or *none* do. A half-finished change can never be left behind.

**Analogy.** A bank transfer: money leaves one account *and* arrives in the other, or neither.
Never just one side.

**In Grymbl.** Closing an episode (updating it *and* recording its files) is one transaction.

### Migrations

**What it is.** A **migration** changes a database's schema (adding a column, for example)
while keeping the existing data.

**In Grymbl.** When AI-agent support added `agent` and `intent` columns, older databases got
them automatically the next time Grymbl opened them.

---

## Part G: Techniques used inside Grymbl

### Hashing

**What it is.** A **hash function** turns any amount of data into a short, fixed-length
fingerprint, like `3f8a…c21`. The same input always gives the same fingerprint, and changing
even one character gives a completely different one. You can't reverse it to get the data
back. **SHA-256** is a standard, trusted hash function.

**Analogy.** A fingerprint. You can't rebuild a person from their fingerprint, but you can
tell instantly whether two fingerprints match.

**In Grymbl.** To decide whether a file *really* changed, Grymbl compares fingerprints instead
of trusting "the file was saved" signals. Same fingerprint → nothing changed → ignore. This is
**content-hash dedup** ([Sensor 1](03_how_it_works.md#sensor-1-the-file-watcher)).

### Diffs

**What it is.** A **diff** lists exactly which lines changed between two versions of a file.
Removed lines start with `-`, added lines with `+`:

```diff
-TTL = 3600
+TTL = 60
```

**In Grymbl.** Every file change is stored as a diff. Diffs are the core evidence Sonnet
reads, and they're used to count how much logic was deleted.

### Regular expressions

**What it is.** A **regular expression** (regex) is a compact pattern that describes a *shape*
of text rather than exact text. Some building blocks:

| Regex piece | Means |
|---|---|
| `sk-` | exactly the characters "sk-" |
| `[A-Za-z0-9]` | any one letter or digit |
| `{16,}` | the previous thing, 16 or more times |
| `\s` | any space or tab |
| `(…)` | a group we want to keep or replace |

So `sk-[A-Za-z0-9]{16,}` means "`sk-` followed by at least 16 letters or digits", which is the
shape of an AI provider's secret key.

**Analogy.** A police sketch: not a photo of one exact person, but a description anyone
matching it fits.

**A trap: backtracking.** When a pattern can match in many ways, the regex engine tries one,
fails, steps back, and tries another. Badly written patterns can try billions of combinations
on long text. Grymbl hit exactly this: one line of 50,000 characters took 35 seconds. See
[History and Lessons](08_history_and_lessons.md#bugs-found-and-what-they-taught-us).

**In Grymbl.** Regex powers secret [redaction](03_how_it_works.md#redaction) and finding
which files import which ([Episodes](03_how_it_works.md#episodes)).

### Time and UTC

**What it is.** **UTC** is the single world reference clock. Storing all times in UTC means
timestamps never get confused by time zones or daylight saving.

**In Grymbl.** Every event's time is stored in UTC. The daily AI-call cap resets at midnight
UTC (8pm Eastern / 5pm Pacific during daylight time).

### Concurrency threads and queues

**What it is.** **Concurrency** means several things happening at overlapping times. A
**thread** is one line of execution inside a process; a process can have several. Threads
sharing data can collide, so a common safe pattern is a **queue**: one thread drops messages
in, another takes them out, one at a time.

**Analogy.** A restaurant's order spike: waiters pin tickets on it, and the cook takes them
off in order. Waiters never walk into the kitchen and grab pans.

**In Grymbl.** The file-watching library reports changes on its own thread. It puts them in a
queue, and the watcher's main thread (the only one allowed to touch the database) processes
them.

### Locks

**What it is.** A **lock** is a marker that only one process can hold at a time, so two
processes don't do the same exclusive job. An **operating-system-level lock** is released
automatically if the process crashes, so it can never be left stuck.

**Analogy.** An "occupied" sign on a single-person bathroom door that flips back by itself if
the person leaves.

**In Grymbl.** Only one `grymbl watch` may run per project. A second one sees the lock and
refuses to start, because two watchers once recorded everything twice.

### Atomic saves

**What it is.** An **atomic save** writes a new file version safely: write the whole new
version to a temporary file, then swap it into place in one step. A crash halfway through
never leaves a half-written file.

**The catch.** Some programs swap by *deleting the original, then renaming the temp file*. For
a split second, the file doesn't exist.

**In Grymbl.** That split second used to look like "you deleted the file", a false alarm.
Grymbl now waits 2 seconds before believing any deletion. See
[Sensor 1](03_how_it_works.md#sensor-1-the-file-watcher).

---

## Part H: The internet and APIs

### APIs and HTTP

**What it is.** An **API** (application programming interface) is a doorway through which one
program asks another for something, following agreed rules. Web APIs use **HTTP**, the same
protocol your browser uses: the program sends a **request** to an address (an **endpoint**,
like `https://api.anthropic.com/v1/messages`) and gets a **response** back.

**Analogy.** A restaurant: you (the program) don't walk into the kitchen (the other system).
You order from a menu (the API) through the waiter (HTTP), and food comes back.

**An SDK** (software development kit) is a library that wraps an API, so you call a normal
function instead of assembling web requests by hand.

**In Grymbl.** The only API Grymbl calls is Anthropic's, through Anthropic's official Python
SDK. See [Sonnet](03_how_it_works.md#sonnet).

### HTTP status codes

**What it is.** Every HTTP response carries a three-digit **status code**:

| Code | Meaning | Example |
|---|---|---|
| **200** | OK | The request worked |
| **400** | Bad request: something about *your request* is wrong | A malformed key |
| **401** | Unauthorized: missing or wrong credentials | No API key sent |
| **429** | Too many requests: slow down | You hit a rate limit |
| **500–599** | The server had a problem | Temporary outage |

**In Grymbl.** Each kind is handled differently, and none of them crashes the watcher. A
real 400 while setting up the key taught us to check the key's format. See
[History and Lessons](08_history_and_lessons.md#bugs-found-and-what-they-taught-us).

### API keys and secrets

**What it is.** An **API key** is a long secret string that proves who you are to an API, and
decides who gets billed. Anyone who has your key can spend your money. General rules for
**secrets** (keys, passwords, tokens):

- Never paste them into chats, documents, or code.
- Never commit them to git.
- Store them in environment variables or a password manager.
- If one is exposed, **revoke** it (cancel it at the provider) and create a new one.

**In Grymbl.** Grymbl reads `ANTHROPIC_API_KEY` from the environment. It also strips secrets
out of everything it records ([Redaction](03_how_it_works.md#redaction)). See
[Operating](07_operating.md#setting-the-api-key) for the safe way to set the key.

---

## Part I: Artificial intelligence

### Large language models

**What it is.** A **large language model** (LLM) is an AI trained on enormous amounts of text
to read and write language. You send it text, and it replies with text. **Claude** is a family
of LLMs made by Anthropic, in several sizes:

| Model | Character |
|---|---|
| Haiku | Small, fast, cheap |
| **Sonnet** | Balanced: strong reasoning at moderate cost. **Grymbl uses Sonnet 5** |
| Opus | Stronger, pricier |
| Fable | The most capable, the most expensive |

**In Grymbl.** Sonnet is the careful thinker consulted only for flagged episodes. See
[Sonnet](03_how_it_works.md#sonnet).

### Tokens and cost

**What it is.** LLMs read and write in **tokens**, chunks of text roughly ¾ of a word each.
Providers bill per token, with separate prices for tokens read (**input**) and tokens written
(**output**). Sonnet 5 costs US$2 per million input tokens and US$10 per million output
tokens.

**In Grymbl.** The first real analysis used 1,367 input and 205 output tokens: about half a
US cent. See [Cost controls](03_how_it_works.md#cost-controls).

### Prompts and system prompts

**What it is.** A **prompt** is the text you send an LLM. A **system prompt** is a special part
of the prompt holding standing instructions: the model's role and rules, as opposed to the
specific question.

**In Grymbl.** The system prompt tells Sonnet its role, that silence is success, the
**evidence rule**, and that AI agents' claims aren't evidence. The user message holds the
episode's evidence.

### Structured output

**What it is.** Normally an LLM answers in free text. **Structured output** forces the answer
into a fixed form with named fields, which the software can rely on.

**Analogy.** A tax form versus a letter. The form has labelled boxes, so the reader always
knows where each answer is.

**In Grymbl.** Sonnet must fill in four boxes: `evidence`, `summary`, `assumptions`,
`intervention`.

### Effort and thinking

**What it is.** Modern models can "think" before answering, reasoning privately first. An
**effort** setting controls how much: more effort usually means better answers, more tokens,
and higher cost.

**In Grymbl.** Effort is set to **medium**: solid judgment at lower cost.

### Hallucination

**What it is.** A **hallucination** is when an LLM states something confident and plausible
that is simply not true or not supported.

**Why it matters here.** A judgment tool that invents reasons is worse than none. That's why
Grymbl's **evidence rule** forbids guessing and requires "insufficient evidence" when the
facts are thin.

### AI coding agents

**What it is.** An **AI agent** is an LLM that doesn't just answer but *acts*: it reads files,
edits code, and runs commands in a loop until a task is done. **Claude Code** is one. A
**session** is one continuous conversation with it; its **transcript** is the saved record of
everything said and done. Each action the agent takes (edit a file, run a command) is a
**tool call**.

**Why it matters here.** Agents now write much of the code, and unlike humans, they *say* what
they intend and assume. Grymbl captures that. See
[Sensor 5](03_how_it_works.md#sensor-5-coding-agents).

### MCP

**What it is.** The **Model Context Protocol** (MCP) is a standard way to give AI agents extra
tools, so one tool definition works across many agents (Claude Code, Cursor, Codex…).

**In Grymbl.** Not built yet. It's the planned way for agents to *declare* their assumptions
directly. See [Status and Roadmap](09_status_and_roadmap.md).

---

## Part J: Grymbl's own vocabulary

These words were invented for (or given a specific meaning in) this product. Each is fully
explained in [How It Works](03_how_it_works.md):

| Term | One-line meaning | Details |
|---|---|---|
| **Sensor** | A part of Grymbl that notices one kind of activity | [Events](03_how_it_works.md#events) |
| **Event** | One normalised observation: what, when, who, which files, details | [Events](03_how_it_works.md#events) |
| **Redaction** | Replacing secrets with `[REDACTED]` before saving | [Redaction](03_how_it_works.md#redaction) |
| **Snapshot** | The last known content of a file, used to spot real changes | [Sensor 1](03_how_it_works.md#sensor-1-the-file-watcher) |
| **Episode** | A group of related events telling one story of work | [Episodes](03_how_it_works.md#episodes) |
| **Correlation** | Grouping events into episodes | [Episodes](03_how_it_works.md#episodes) |
| **Intent** | The request that started an AI agent's episode | [Sensor 5](03_how_it_works.md#sensor-5-coding-agents) |
| **Jev** | Four fixed rules that decide which episodes deserve attention | [Jev](03_how_it_works.md#jev) |
| **Triage** | Sorting by urgency; what Jev does | [Jev](03_how_it_works.md#jev) |
| **Escalation** | Jev passing an episode to Sonnet | [Jev](03_how_it_works.md#jev) |
| **Evidence rule** | Sonnet may state only what the evidence directly supports | [Sonnet](03_how_it_works.md#sonnet) |
| **Experience Graph** | Grymbl's memory of episodes, files, and assumptions | [Storage](03_how_it_works.md#storage) |
| **Intervention** | Grymbl's rare, evidence-backed warning | [Interventions](03_how_it_works.md#interventions) |

---

<sub>Next: [Chapter 2: The Product](02_the_product.md). Copyright © 2026 Maurya Oganja. All rights reserved.</sub>

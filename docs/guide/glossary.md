# Glossary

Every term used in this guide, alphabetically. Each entry gives a plain definition and links
to where it's explained in full. **F** = [Foundations](01_foundations.md), **H** =
[How It Works](03_how_it_works.md).

[A](#a) · [B](#b) · [C](#c) · [D](#d) · [E](#e) · [F](#f) · [G](#g) · [H](#h) · [I](#i) · [J](#j) · [L](#l) · [M](#m) · [N](#n) · [O](#o) · [P](#p) · [Q](#q) · [R](#r) · [S](#s) · [T](#t) · [U](#u) · [V](#v) · [W](#w)

---

## A

### Absolute path
A file's full address from the top of the disk, like `C:\dev\Grymbl\README.md`. Compare
[relative path](#relative-path). → [F: Files folders and paths](01_foundations.md#files-folders-and-paths)

### Agent
An AI that takes actions (edits files, runs commands) in a loop until a task is done, rather
than only answering. Claude Code is one. → [F: AI coding agents](01_foundations.md#ai-coding-agents), [H: Sensor 5](03_how_it_works.md#sensor-5-coding-agents)

### API
*Application programming interface.* A defined doorway through which one program asks another
for something. Grymbl calls Anthropic's API. → [F: APIs and HTTP](01_foundations.md#apis-and-http)

### API key
A secret string proving your identity to an API, and deciding who gets billed. Never share it;
revoke it if exposed. → [F: API keys and secrets](01_foundations.md#api-keys-and-secrets)

### Argument
Extra words after a command's name telling it what to do: in `git commit -m "fix"`, `commit`
and `"fix"` are arguments. → [F: Commands arguments and options](01_foundations.md#commands-arguments-and-options)

### Assumption
In Grymbl, a belief recorded from an episode ("tokens are only checked at login"), stored with
a validity: `unverified`, `valid`, or `contradicted`. → [H: Storage](03_how_it_works.md#storage)

### Async
*Asynchronous*: started without waiting for it to finish. Grymbl's hooks run async so nothing
waits on them. Also called running "in the background".

### Atomic save
Saving by writing a complete new copy under a temporary name and then swapping it in. It can
briefly make the original look deleted. → [F: Atomic saves](01_foundations.md#atomic-saves)

## B

### Backtracking
When a pattern matcher tries one way to match, fails, steps back, and tries another. Badly
written patterns can do this billions of times on long text. → [F: Regular expressions](01_foundations.md#regular-expressions)

### Baseline
The first silent snapshot of every file, taken at setup and on watcher start, so later changes
have something to be compared against. → [H: Sensor 1](03_how_it_works.md#sensor-1-the-file-watcher)

### Binary file
A file whose contents aren't text: an image, a compiled program. Grymbl ignores them.
→ [F: Text files binary files and encoding](01_foundations.md#text-files-binary-files-and-encoding)

### Boolean
A value that is either true or false.

### Branch
In git, a separate line of work, so changes don't disturb the main version until they're ready.
→ [F: Version control and git](01_foundations.md#version-control-and-git)

### Build backend
The tool that packages Python code for installation. Grymbl uses hatchling. → [Tech Stack: Packaging](04_tech_stack.md#packaging)

## C

### CLI
*Command-line interface.* A program you control by typing commands. `grymbl` is one.
→ [F: Command line interfaces](01_foundations.md#command-line-interfaces)

### Commit
A saved snapshot of a project in git, with a message and a unique ID.
→ [F: Version control and git](01_foundations.md#version-control-and-git)

### Compiled language
A language translated ahead of time into machine code, for speed (Go, Rust). Compare
[interpreted language](#interpreted-language).

### Concurrency
Several things happening at overlapping times. → [F: Concurrency threads and queues](01_foundations.md#concurrency-threads-and-queues)

### Context event
In Grymbl, a command, test run, or push. These describe what you're doing now, so they join the
active episode even without a file link. → [H: Episodes](03_how_it_works.md#which-episode-does-an-event-join)

### Correlation
Grouping related events into episodes. → [H: Episodes](03_how_it_works.md#episodes)

## D

### Daemon
A program running continuously in the background. `grymbl watch` is Grymbl's daemon.
→ [F: Background processes and daemons](01_foundations.md#background-processes-and-daemons)

### Database
An organised store of information that programs can search and update reliably. Grymbl uses
[SQLite](#sqlite). → [F: Databases and SQL](01_foundations.md#databases-and-sql)

### Dataclass
A compact Python definition of a data shape, such as an `Event` with its fields. "Frozen"
dataclasses can't be changed after creation.

### Dedup
*De-duplication*: dropping repeats. Grymbl drops saves whose content didn't change.
→ [H: Sensor 1](03_how_it_works.md#sensor-1-the-file-watcher)

### Dependency
Outside code a program relies on. Grymbl has three at runtime. → [F: Libraries dependencies and packages](01_foundations.md#libraries-dependencies-and-packages)

### Deterministic
Always giving the same result for the same input. Jev is deterministic; AI models are not.

### Diff
A list of exactly which lines were added (`+`) and removed (`-`) between two versions of a
file. → [F: Diffs](01_foundations.md#diffs)

### Directory
Another word for a folder.

### Dogfooding
Using your own product yourself, to find its problems first.

## E

### Edge
A connection between two things in a [graph](#graph).

### Editable install
An installation that runs straight from the code folder, so code changes apply immediately.
→ [Tech Stack: Packaging](04_tech_stack.md#packaging)

### Effort
A setting controlling how much an AI model thinks before answering. Grymbl uses `medium`.
→ [F: Effort and thinking](01_foundations.md#effort-and-thinking)

### Encoding
The rule mapping stored numbers to letters. UTF-8 is the standard.
→ [F: Text files binary files and encoding](01_foundations.md#text-files-binary-files-and-encoding)

### Endpoint
A specific web address an API answers at, such as `https://api.anthropic.com/v1/messages`.

### Environment variable
A named value the operating system gives every program, such as `PATH` or
`ANTHROPIC_API_KEY`. → [F: Environment variables](01_foundations.md#environment-variables)

### Episode
One story of work: related events (a prompt, edits, test runs, a commit) grouped together.
Grymbl's main unit of judgment. → [H: Episodes](03_how_it_works.md#episodes)

### Escalation
Jev deciding an episode deserves Sonnet's analysis. → [H: Jev](03_how_it_works.md#jev)

### Event
One normalised observation from a sensor: kind, time, developer, files, details.
→ [H: Events](03_how_it_works.md#events)

### Evidence rule
The plan's rule that Sonnet may only state what the evidence directly supports, and must say
"insufficient evidence" otherwise. → [H: Sonnet](03_how_it_works.md#sonnet)

### Exit code
The number a finished command returns: `0` means success, anything else means failure.
→ [F: Exit codes](01_foundations.md#exit-codes)

### Experience Graph
Grymbl's memory: episodes, files, and assumptions, and how they connect.
→ [H: Storage](03_how_it_works.md#the-experience-graph)

## F

### Fake
A stand-in used in tests in place of something slow, costly, or external, such as the AI model.
→ [F: Automated tests and fakes](01_foundations.md#automated-tests-and-fakes)

### Fixture
In pytest, a ready-made test ingredient (a temporary project, a fresh database) supplied to
any test that asks for it by name. → [Developing: Writing tests](06_developing.md#writing-tests)

### Flag
See [option](#option).

### Formatter
A tool that rewrites code into one consistent layout. Grymbl uses ruff.
→ [F: Linting and formatting](01_foundations.md#linting-and-formatting)

## G

### Git
The standard version-control tool. → [F: Version control and git](01_foundations.md#version-control-and-git)

### GitHub
A website hosting git repositories online. Grymbl's code is in a private GitHub repository.
→ [F: GitHub and remotes](01_foundations.md#github-and-remotes)

### Gitignore
A `.gitignore` file listing files git must never track.
→ [F: Ignoring files with gitignore](01_foundations.md#ignoring-files-with-gitignore)

### Graph
A structure of things (**nodes**) connected by relationships (**edges**), like a family tree
or a subway map. Grymbl's memory is a graph of episodes, files, and assumptions.
→ [H: The Experience Graph](03_how_it_works.md#the-experience-graph)

## H

### Hallucination
When an AI states something confident and plausible that isn't true or supported.
→ [F: Hallucination](01_foundations.md#hallucination)

### Hash
A short fingerprint computed from content. Same content, same hash; any change, a different
hash. Grymbl uses SHA-256. → [F: Hashing](01_foundations.md#hashing)

### Hook
A slot a program deliberately leaves open, where your own script runs automatically at a
certain moment. Like a doorbell whose button you wire up yourself. Grymbl uses shell, git, and
Claude Code hooks. → [F: Hooks](01_foundations.md#hooks)

### HTTP
The protocol web requests use. → [F: APIs and HTTP](01_foundations.md#apis-and-http)

### HTTP status code
The three-digit result of a web request: 200 OK, 400 bad request, 401 unauthorized, 429 too
many requests, 5xx server trouble. → [F: HTTP status codes](01_foundations.md#http-status-codes)

## I

### IDE
*Integrated development environment*: a code editor with built-in tools, such as VS Code. An
"IDE extension" is a plugin for one. Parked for v2.

### Import
A line in a code file that uses another file (`from app import auth`).

### Import graph
Grymbl's map of which project files import which. Used to decide whether files are related.
→ [H: Episodes](03_how_it_works.md#is-the-event-related)

### Intent
The user's request that opened an AI agent's episode: *why* the work happened.
→ [H: Sensor 5](03_how_it_works.md#sensor-5-coding-agents)

### Interpreted language
A language run on the fly without a separate translation step. Easier and faster to write.
Python is one.

### Intervention
Grymbl's rare, evidence-backed warning. → [H: Interventions](03_how_it_works.md#interventions)

### Invariant
A rule that must always hold, whatever changes. Grymbl has nine.
→ [H: Safety invariants](03_how_it_works.md#safety-invariants)

## J

### Jev
Grymbl's gatekeeper: four deterministic rules that decide which episodes reach Sonnet. It's
code inside Grymbl, not a service. → [H: Jev](03_how_it_works.md#jev)

### JSON
A universal text format for structured data: `{"passed": 3}`. → [F: JSON](01_foundations.md#json)

## L

### Library
Reusable code someone else wrote. → [F: Libraries dependencies and packages](01_foundations.md#libraries-dependencies-and-packages)

### Linter
A tool that flags likely bugs and bad patterns in code. Grymbl uses ruff.
→ [F: Linting and formatting](01_foundations.md#linting-and-formatting)

### LLM
*Large language model*: an AI trained on huge amounts of text. Claude is a family of LLMs.
→ [F: Large language models](01_foundations.md#large-language-models)

### Lock
A marker only one process can hold at a time. OS-level locks release automatically on crash.
→ [F: Locks](01_foundations.md#locks)

### Lock file
A file (`uv.lock`) pinning the exact version of every dependency.
→ [F: Virtual environments and lock files](01_foundations.md#virtual-environments-and-lock-files)

## M

### MCP
*Model Context Protocol*: a standard way to give AI agents extra tools. Planned for
agent-declared assumptions. → [F: MCP](01_foundations.md#mcp)

### Meaningful line
A line that isn't blank and isn't a comment. Used to measure deleted logic.
→ [H: Events](03_how_it_works.md#events)

### Migration
Changing a database's structure while keeping its data. → [F: Migrations](01_foundations.md#migrations)

### Module
In Jev rule 3, a distinct area of the codebase: a top-level folder, or one level deeper inside
`src/`-style folders, with tests excluded. → [H: Jev](03_how_it_works.md#jev)

## N

### Narrative
Everything an AI agent wrote during one turn: its explanations, plans, and claims.
→ [H: Sensor 5](03_how_it_works.md#sensor-5-coding-agents)

### Node
A thing in a [graph](#graph): an episode, a file, an assumption.

## O

### Operating system
The base software running the computer: Windows, macOS, Linux.
→ [F: Operating systems](01_foundations.md#operating-systems)

### Option
A command argument starting with `-` or `--` that switches behaviour, like `-m` or
`--password`. Also called a flag.

## P

### Package
Distributable, installable code. Also: a folder of Python modules (`src/grymbl`).

### Path
A file's address in the folder tree. → [F: Files folders and paths](01_foundations.md#files-folders-and-paths)

### PATH
The environment variable listing the folders where the shell looks for programs.
→ [F: Environment variables](01_foundations.md#environment-variables)

### Payload
The kind-specific details inside an event: the diff, the command, the test counts.
→ [H: Events](03_how_it_works.md#events)

### Pipe
The `|` symbol, which sends one program's output into another's input.
→ [F: Standard input and output](01_foundations.md#standard-input-and-output)

### Pipeline
A chain of stages, each doing one job and passing results on. Grymbl is one.
→ [H: The pipeline at a glance](03_how_it_works.md#the-pipeline-at-a-glance)

### Primary key
The column that uniquely identifies each row in a table. → [F: Databases and SQL](01_foundations.md#databases-and-sql)

### Process
A running instance of a program. → [F: Programs and processes](01_foundations.md#programs-and-processes)

### Prompt
The text sent to an AI. For agent episodes, the user's prompt becomes the intent.
→ [F: Prompts and system prompts](01_foundations.md#prompts-and-system-prompts)

### Protocol
In Python, a description of the shape an object must have (for example "has an `analyze`
method"). It lets tests swap in fakes. → [Codebase Tour](05_codebase_tour.md#reasoningpy)

### Push
Uploading commits to a remote repository such as GitHub.

### Pydantic
A library for defining data shapes and validating data against them. Used for Sonnet's answer
form.

### PyPI
The public catalogue of Python packages.

## Q

### Queue
A line of messages that one part of a program adds to and another takes from, in order.
→ [F: Concurrency threads and queues](01_foundations.md#concurrency-threads-and-queues)

## R

### Rate limit
A cap on how many requests an API accepts in a period. Exceeding it returns 429.

### Redaction
Replacing secrets with `[REDACTED]` while keeping the surrounding text.
→ [H: Redaction](03_how_it_works.md#redaction)

### Refusal
When an AI model declines to answer. Grymbl logs it and records the episode without analysis.

### Regex
*Regular expression*: a compact pattern describing a shape of text.
→ [F: Regular expressions](01_foundations.md#regular-expressions)

### Relative path
A file's address starting from the current location, like `src/grymbl/jev.py`.
→ [F: Files folders and paths](01_foundations.md#files-folders-and-paths)

### Remote
A named online copy of a git repository, usually `origin`. → [F: GitHub and remotes](01_foundations.md#github-and-remotes)

### Repository
A project folder whose history git tracks. Also "repo".
→ [F: Version control and git](01_foundations.md#version-control-and-git)

### Revoke
Cancel a key at its provider, so it stops working even if someone has it.

## S

### Schema
The structure of a database: its tables and columns. → [F: Databases and SQL](01_foundations.md#databases-and-sql)

### SDK
*Software development kit*: a library that makes an API easy to use from code.
→ [F: APIs and HTTP](01_foundations.md#apis-and-http)

### Sensor
A part of Grymbl that notices one kind of activity and records events. There are five.
→ [H: Events](03_how_it_works.md#events)

### Session
One continuous conversation with an AI agent, with its own ID.
→ [F: AI coding agents](01_foundations.md#ai-coding-agents)

### SHA-256
A standard, trusted [hash](#hash) function. → [F: Hashing](01_foundations.md#hashing)

### Shell
The program that reads and runs typed commands: bash, zsh, PowerShell.
→ [F: The terminal and the shell](01_foundations.md#the-terminal-and-the-shell)

### Snapshot
The last known content and fingerprint of a file, used to spot real changes and compute diffs.
→ [H: Sensor 1](03_how_it_works.md#sensor-1-the-file-watcher)

### Sonnet
Claude Sonnet 5, the AI model Grymbl consults about escalated episodes.
→ [H: Sonnet](03_how_it_works.md#sonnet)

### SQL
The language used to query and update relational databases.
→ [F: Databases and SQL](01_foundations.md#databases-and-sql)

### SQLite
A complete database in a single file, with no server. → [F: SQLite and WAL](01_foundations.md#sqlite-and-wal)

### Standard library
The libraries built into a language, needing no install.

### stdin stdout stderr
A process's three built-in channels: input, normal output, error output.
→ [F: Standard input and output](01_foundations.md#standard-input-and-output)

### String
A piece of text, as a value in code.

### Structured output
Forcing an AI's answer into a fixed form with named fields.
→ [F: Structured output](01_foundations.md#structured-output)

### Subcommand
A command within a command: `init` in `grymbl init`.

### System prompt
Standing instructions given to an AI (its role and rules), separate from the specific question.
→ [F: Prompts and system prompts](01_foundations.md#prompts-and-system-prompts)

## T

### Table
In a database, a spreadsheet-like collection of rows with fixed columns.

### Terminal
The window where you type commands; the shell runs inside it.
→ [F: The terminal and the shell](01_foundations.md#the-terminal-and-the-shell)

### Test suite
All of a project's automated tests together. Grymbl's has 96.
→ [F: Automated tests and fakes](01_foundations.md#automated-tests-and-fakes)

### Thread
One line of execution inside a process. → [F: Concurrency threads and queues](01_foundations.md#concurrency-threads-and-queues)

### Tick
One pass of the watcher's loop, about once a second. → [H: The main loop](03_how_it_works.md#the-main-loop)

### Token
The unit AI models read, write, and bill in: roughly ¾ of a word.
→ [F: Tokens and cost](01_foundations.md#tokens-and-cost)

### Tool call
One action an AI agent takes, such as editing a file or running a command.

### Trade-off
Gaining one thing by giving up another. → [Tech Stack](04_tech_stack.md#how-we-decided)

### Transaction
A group of database changes that happen all together, or not at all.
→ [F: Transactions](01_foundations.md#transactions)

### Transcript
The saved record of an AI agent session. → [F: AI coding agents](01_foundations.md#ai-coding-agents)

### Triage
Sorting by urgency (from hospitals). Jev does triage. → [H: Jev](03_how_it_works.md#jev)

### Type checker
A tool that verifies type hints across the code before it runs. Grymbl uses mypy.
→ [F: Type hints and type checking](01_foundations.md#type-hints-and-type-checking)

### Type hint
A label saying what type a value should be (`exit_code: int`).
→ [F: Type hints and type checking](01_foundations.md#type-hints-and-type-checking)

## U

### UTC
The single world reference clock. All Grymbl times use it. → [F: Time and UTC](01_foundations.md#time-and-utc)

### UTF-8
The standard text encoding. → [F: Text files binary files and encoding](01_foundations.md#text-files-binary-files-and-encoding)

### uv
The tool that manages Grymbl's Python environment and dependencies.
→ [Tech Stack](04_tech_stack.md#project-and-dependency-management)

## V

### Validity
An assumption's status: `unverified`, `valid`, or `contradicted`. → [H: Storage](03_how_it_works.md#storage)

### Version control
Recording every saved state of a project. → [F: Version control and git](01_foundations.md#version-control-and-git)

### Virtual environment
A private folder of libraries for one project. → [F: Virtual environments and lock files](01_foundations.md#virtual-environments-and-lock-files)

## W

### WAL
*Write-ahead logging*: a SQLite mode letting several processes write safely at once.
→ [F: SQLite and WAL](01_foundations.md#sqlite-and-wal)

### Watcher
The long-running `grymbl watch` process. → [H: The main loop](03_how_it_works.md#the-main-loop)

### Working tree
The project's files as they are on disk right now. → [F: Version control and git](01_foundations.md#version-control-and-git)

---

<sub>Back to the [start](README.md). Copyright © 2026 Maurya Oganja. All rights reserved.</sub>

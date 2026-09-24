# Chapter 8: History and Lessons

*What was built and when, every decision and why, and every bug found and what it taught us.*

---

## Timeline

Everything so far was built on **2026-09-24**, in one working session. Each row is a commit on `main`:

| Commit | What it added |
|---|---|
| `9d86d3b` | Project skeleton: settings, event shape, the plan |
| `6edeceb` | Secret redaction, content-hash dedup, import scanning |
| `5e18408` | The SQLite Experience Graph, episode correlation, Jev |
| `df87f25` | File, terminal, git, and test sensors; the shell hooks |
| `6fa5fd3` | Sonnet reasoning, the judgment pipeline, the watcher, the CLI. **v1 feature-complete** |
| `c970a99` | Wording updated for a solo developer |
| `3e8c15a` | README rewritten around the product |
| `bfc042e` | v1.1 agent-awareness addendum (the plan for AI-agent capture) |
| `f13f58e` | Fix: false deletions from atomic saves; single-watcher lock |
| `9b5a566` | **v1.1 step 1:** Claude Code capture; missing-key crash fixed |
| `2e06ed2` | Token usage logged per AI call |
| `bf93755` | Fix: 35-second redaction on long lines |
| `fb34320` | Cost controls: medium effort, 25 calls/day, evidence cap |
| `3e2d104` | Proprietary license |
| `5718e9e` | First documentation (since replaced by this guide) |
| `20af405` | API error details logged; **first real Sonnet analysis** recorded |
| *(this guide)* | The complete handover guide |

Run `git log` for the full messages, which explain the *why* of each change.

---

## Decision log

Big decisions come from the [plan](../prototype_plan.md). These were made while building. Each
changes behaviour, and each is worth knowing before changing it.

### Product and rules

| # | Decision | Alternatives | Why |
|---|---|---|---|
| D1 | Grymbl is the judgment layer; the dev-matching app is a separate, later project it will watch | Build both together | Prove the watcher first |
| D2 | Solo project | The plan's 3-person team | The owner's decision; team features stay in the plan's later phases |
| D3 | **Jev rule 1** counts only earlier *escalated* episodes | Any earlier episode | Otherwise nearly every file qualifies within a day, and cost explodes |
| D4 | **Jev rule 3** modules = top-level folder, one level deeper for `src/`-style folders, tests excluded | Immediate parent folder | Fewer false alarms; still works in `src/` layouts |
| D5 | **Jev rule 4** = net loss of ≥ 3 meaningful lines per file, summed over the episode, or deleting a file with logic | Any removed line | Refactors aren't deletions; piecemeal deletion still counts |
| D6 | Jev rule 2 also covers commands (same command fails, then succeeds) | Tests only | Build failures and fixes matter as much as test failures |

### Capture

| # | Decision | Alternatives | Why |
|---|---|---|---|
| D7 | Data stored per project in `.grymbl/` | One global folder | Separate memories; capture only where asked |
| D8 | `.grymbl/` ignores itself (`.gitignore` = `*`) | Edit the project's `.gitignore` | Works without touching the user's files |
| D9 | Terminal hooks for bash, zsh, **and** PowerShell | bash/zsh only (the plan) | The owner requires Windows, macOS, and Linux |
| D10 | Commands passed via stdin | As an argument | Not visible in the process list; no encoding problems |
| D11 | Hooks only act inside watched projects | Everywhere | Privacy; less noise |
| D12 | Git hooks always succeed, and never overwrite others' hooks | Stricter | Never block commits; coexist with other tools |
| D13 | Silent baseline on `init` and watcher start | Record everything as new | Avoids floods of meaningless events |
| D14 | Wait 2 s before believing a deletion; ignore `*.tmp.*` files | Believe immediately | Atomic saves briefly delete files |
| D15 | One watcher per project (OS lock) | Allow many | Two watchers duplicated every event |

### AI agents (v1.1)

| # | Decision | Alternatives | Why |
|---|---|---|---|
| D16 | Passive capture via Claude Code hooks first; agent-declared assumptions (MCP) later | MCP first | Hooks capture ground truth without the agent's cooperation |
| D17 | Hooks in **local** Claude settings, kept out of git | Shared settings | Never alter what the project commits |
| D18 | Each prompt opens a new episode | Time window only | The prompt is the natural "why" boundary |
| D19 | Store the agent's narrative (redacted, ≤ 20,000 characters) | Prompts and actions only | It's where agents state their assumptions |
| D20 | Agent statements are "claims, not evidence" | Trust them | Agents can be confidently wrong |
| D21 | `Stop` hook synchronous; others in the background | All in the background | Background hooks were dropped at session end |

### AI and cost

| # | Decision | Alternatives | Why |
|---|---|---|---|
| D22 | Claude Sonnet 5 | Opus, Haiku | The plan names Sonnet; balances judgment and cost |
| D23 | Structured output (four fixed fields) | Free text | The software can rely on the shape |
| D24 | Effort **medium** | high (default), low | Big saving; judgment stays solid |
| D25 | **25** calls per UTC day | 20, 50, none | Chosen by the owner |
| D26 | Evidence capped at ~25,000 tokens; longest events trimmed first, visibly | Send everything | Caps the worst case; the model knows when evidence is partial |
| D27 | Redact *then* trim | Trim then redact | Trimming first can leave part of a secret |
| D28 | A missing API key never crashes the watcher | Crash loudly | Recording must continue even when analysis can't |

### Ownership and process

| # | Decision | Alternatives | Why |
|---|---|---|---|
| D29 | Proprietary license, "Copyright 2026 Maurya Oganja, all rights reserved" | Open source | Solo commercial venture |
| D30 | Private GitHub repo | Public | Proprietary |

---

## Bugs found and what they taught us

Every one of these was found by **running the real thing**, not by reading code. Each now has
a test.

| # | Bug | How it showed up | Root cause | Fix | Lesson |
|---|---|---|---|---|---|
| B1 | PowerShell auth headers not redacted | Live PowerShell hook test stored `Bearer abc123` unmasked | The pattern only knew curl's `Authorization:` form, not PowerShell's `@{Authorization="…"}` | Pattern accepts `:` or `=`, with optional quotes | Test each platform's real syntax, not just the familiar one |
| B2 | False "deleted logic" on ordinary saves | Every Claude Code edit produced a `file_deleted` event, falsely firing Jev rule 4 | Atomic saves delete the original, then rename a temp file into place | Ignore `*.tmp.*` files; wait 2 s before believing a deletion | OS events describe mechanics, not intent. Judge by content |
| B3 | Every event recorded twice | Duplicate identical events in the database | Two watchers ran at once (leftovers from testing) | OS-level single-watcher lock | Guard singleton processes in code, not by convention |
| B4 | Stray watchers survived their time limit | Watchers kept running after `timeout` expired | On Windows, Git Bash's `timeout` kills the launcher but not the Python process it started | Stop processes explicitly by PID | Verify cleanup; don't assume it |
| B5 | Agent "turn end" never recorded | The `Stop` event was missing in headless runs | Background hooks are dropped when a headless session exits | `Stop` hook runs synchronously | Test the exact runtime mode users will use |
| B6 | Documentation vs reality | Claude Code's docs described some hook fields and failure behaviour differently from what arrived | Docs lag or summarise | Captured real payloads from a live session; tests use those shapes | Capture real samples before writing a parser |
| B7 | Watcher crashed without an API key | Crash on the first escalation | The SDK raises a plain `TypeError` (not an API error) when no credentials exist at all; a different setup raises `CredentialsError` | Handle both; log once; keep recording | Missing configuration is a normal state, not an exception |
| B8 | 35-second redaction | One 50,000-character line (like minified code) froze processing | A regex with unbounded repeats on both sides of a keyword **backtracked** quadratically | Start only at word boundaries; bounded name lengths; a speed test | Regexes over untrusted, huge text need performance tests |
| B9 | Possible partial-secret leak when trimming | Found in design review, not in the wild | Trimming before redacting can shorten a secret below what the patterns recognise | Redact each event, *then* trim; a test sweeps every cut position | Order of safety steps matters |
| B10 | API error with no detail | "API error 400" and nothing else | The log didn't include the API's message | Log the error message | Every failure log must say *why* |
| B11 | Malformed API key (1 character) | 400 with an empty body and no request ID, meaning the request never reached the API properly | Ctrl+V into a hidden PowerShell prompt types an invisible control character | Documented a clipboard-based command that validates the key | Check the input's shape before blaming the system |
| B12 | Key replaced by the command text | Saved "key" was 255 characters | Copying the command overwrote the key on the clipboard | The command now pauses so the key is copied after | Instructions must work with one clipboard |

### How B11 was diagnosed

This is worth knowing as a technique:

1. The API returned **400** with an **empty body** and **no `request-id` header**. Every real
   Anthropic response carries a request ID, so this suggested the request was malformed before
   the API could even process it.
2. A plain unauthenticated request from the same machine got a proper **401** with a request
   ID, so the network path was fine.
3. So the difference was in *our* request. The key's **shape** was checked (length, prefix,
   hidden characters) **without printing it**: 1 character long, containing a control
   character.

**Principle: diagnose from the outside in, and never print a secret to debug it.**

---

## Process lessons

- **Run the real thing early.** The unit tests all passed while most of the bugs above were
  still waiting to be found in live runs.
- **Verify, don't assume:** third-party formats (B6), process cleanup (B4), runtime modes (B5).
- **Cheap real checks are worth it.** A few small real AI calls (Claude Haiku for payload
  capture, one Sonnet call to prove analysis) cost a few cents and removed all guesswork.
- **Measure cost before optimising it.** The estimate was US$0.025 per call; reality was
  US$0.005.
- **Write it down.** The *why* lives in commit messages, the
  plan documents, and this guide.

---

<sub>Next: [Chapter 9: Status and Roadmap](09_status_and_roadmap.md). Copyright © 2026 Maurya Oganja. All rights reserved.</sub>

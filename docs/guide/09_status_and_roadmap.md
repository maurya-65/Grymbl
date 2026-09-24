# Chapter 9: Status and Roadmap

*What's proven, what isn't, what's missing, and what to build next.*

Last updated: **2026-09-24**.

---

## Where things stand

**v1 (the plan) is feature-complete. v1.1 step 1 (AI-agent capture) is built.** Quality: over 100
automated tests, lint and strict type checks clean.

### Proven in real use

| Item | Evidence |
|---|---|
| File watcher, dedup, atomic saves, single-watcher lock | Live runs with real edits, including Claude Code's saves |
| Claude Code capture (prompt, edits, commands with exit codes, narrative) | Several live Claude Code sessions |
| Episode grouping for agent turns | Live: prompt, edits, and turn end landed in one episode |
| PowerShell hook's sending path | Live test, which found and fixed a redaction gap |
| Git capture (when invoked) | Live commit and push captured by calling the capture commands |
| **Sonnet analysis under the evidence rule** | One real call: it flagged the agent's unverified claim and correctly stayed silent. ≈ US$0.005 |
| Missing-key and bad-key handling | Live |
| `grymbl report` | Rendered and checked in a browser (both themes, tooltips, filters, empty states); generated on the real repo |

### Built but not yet proven in real use

| Item | What's missing | How to prove it |
|---|---|---|
| Git hooks firing on their own | `grymbl` wasn't globally installed during testing | `uv tool install --editable .`, then commit in a watched project |
| bash hook | Only syntax-checked | Load it in Git Bash or Linux; run commands; check `grymbl status` |
| zsh hook | Not run (zsh wasn't installed) | Test on a Mac |
| PowerShell hook in a live interactive prompt | Only the sending path was tested | Add it to `$PROFILE` and use it for a day |
| `grymbl test` wrapper | Report parsers are tested; the wrapper hasn't run a real suite | Run it on a real pytest project with `pytest-json-report` |
| macOS and Linux generally | All testing was on Windows | Run the test suite and a short session on each |
| A warning (intervention) from real history | Needs an earlier escalated episode on the same file | Will happen naturally with use |

---

## Known gaps

| Gap | Impact | Suggested fix |
|---|---|---|
| **Assumption validity never changes.** Assumptions stay `unverified` forever | The Experience Graph can't yet say "this belief turned out wrong" | Let Sonnet mark earlier assumptions `valid`/`contradicted` when new evidence speaks to them, or add a manual command |
| **Sonnet mixes assumptions and findings** | In the first call, "the agent's claim is unverified" was listed as an assumption | Add a separate `findings` field to the output |
| **Dependents aren't sent as evidence.** When `auth.py` changes, Sonnet isn't told which files use it, although the import graph knows | Sonnet can't check "nothing depends on this" claims | Add "files importing the changed files" to the evidence |
| **Go imports not scanned** | Weaker grouping for Go projects | Add a Go pattern, resolved via `go.mod` |
| **No config file** | Changing a setting means editing code | Read overrides from `.grymbl/config.toml` |
| **Watcher doesn't auto-start** | Easy to forget to run it | A login task (Windows Task Scheduler / macOS launchd / Linux systemd) |
| **Only Claude Code** among AI agents | Other agents' work looks human | The MCP layer (below), or per-agent adapters |
| **Rule 1 may snowball** | Busy files with history escalate more over time, raising cost. In a synthetic two-week test on six files, 47 of 51 episodes escalated, 44 of them via rule 1 | Watch "Why episodes escalated" in `grymbl report`; consider limiting rule 1 to recent history, or to files with warnings rather than any escalation |
| **Watched `.env` files keep secrets in the database** | File snapshots store raw content locally (redaction applies only to what's shown or sent) | Ignore `.env*` files in the watcher, or redact snapshots |

---

## The backlog

In recommended order. Effort is a rough guide for one developer.

| # | Item | Why now | Effort |
|---|---|---|---|
| 1 | **Prove the unproven**: global install, git hooks, bash hook, `grymbl test` on a real suite | v1 isn't really "done" until it runs day to day | Hours |
| 2 | **Build the dev-matching app** (plan §1), the project Grymbl should watch | Grymbl needs real work to judge; its stack is still undecided | Ongoing |
| 3 | **Decide the success criterion** (plan §10), e.g. "flagged at least one real thing I'd have missed in 3 weeks" | Avoid an ambiguous result later | Minutes |
| 4 | Separate `findings` from `assumptions` in Sonnet's output | Cleaner memory | Small |
| 5 | Send dependents as evidence | Lets Sonnet check "nothing uses this" claims | Small |
| 6 | **v1.1 step 2: agent-declared assumptions** via an MCP server (`record_assumption`, `record_decision`) plus a `grymbl note` fallback | Agents state beliefs directly, across many agents | Medium |
| 7 | **v1.1 step 3: warnings to the agent itself** before it edits a file with bad history | The best recipient of a warning is the one about to repeat the mistake | Medium |
| 8 | Assumption validity updates | Lets memory learn from being wrong | Medium |
| 9 | Config file; watcher auto-start | Everyday comfort | Small each |
| ✓ | ~~A way to see everything~~ **Done:** `grymbl report`, with token usage saved per call | — | — |
| 10 | Test on macOS and Linux | Cross-platform promise | Small |

Details for items 6 and 7: [`v1.1_agent_awareness.md`](../v1.1_agent_awareness.md).

---

## Deliberately later (plan §8)

Not gaps. These were parked on purpose:

- Editor plugins (VS Code, JetBrains)
- "Nearly identical" dedup
- Meaning-based and branch-aware episode grouping
- Multi-developer and team/company memory ("Team Master", "Company Master")
- Moving to a graph database (Neo4j / Amazon Neptune)
- Trained severity scoring (how urgent a warning is)
- Privacy framing for a company-wide rollout

And the at-scale technology moves (Go → Rust local agent, Go ingestion, Next.js dashboard) in
[Tech Stack](04_tech_stack.md#what-changes-at-scale).

---

## Open questions for the owner

| Question | Source |
|---|---|
| What's the success criterion for the prototype? | Plan §10 |
| What will the dev-matching app be called, and which stack will it use? | Plan §1, §10 |
| Should warnings eventually go to Slack, the terminal, or the agent? | Plan §10; v1.1 step 3 |
| How much agent narrative to keep per turn (currently 20,000 characters)? | v1.1 addendum §7 |
| Which AI agents to support after Claude Code? | v1.1 addendum §7 |

---

<sub>Back to the [start](README.md). Copyright © 2026 Maurya Oganja. All rights reserved.</sub>

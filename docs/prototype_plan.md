# Judgment Layer — Prototype Plan (v1)

**Status:** All decisions below are locked except where explicitly marked open in §10. This is the referenceable build spec.

---

## 0. Product philosophy (context, not a build item)

> The product is not AI that remembers. It is software that accumulates judgment.

Master/dad analogy: the system watches, stays silent by default, and intervenes only with evidence when a pattern resembles something consequential seen before. Silence is a successful outcome, not a failure to act.

---

## 1. Team & Repo

- **Team:** 3 developers (you + 2 friends).
- **Repo:** Brand new repo, built from scratch — not a clone of an existing project.
- **What gets built in the repo:** A full-stack + AI product — **a dev-matching app** (working idea: swipe-based matching for developers, with tech-stack compatibility as the core matching signal, same-gender matching supported, and a fun/funny tone throughout — profile prompts and bios leaning into CS/dev humor, "larp about your stack" energy rather than a serious dating app). This is dogfooding — the test subject and the product category (full-stack + AI) are intentionally similar to the actual judgment-layer product.
  - Core surface area expected: auth, user profiles (stack/tech preferences), a matching/compatibility algorithm, swipe UI, matches, real-time-ish chat.
  - AI component: compatibility scoring (tech-stack based matching logic) — a legitimate, non-decorative use of AI in the product, not a bolted-on chatbot.
  - Specific matching logic, feature scope, and app name still open — to be decided by the 3 of you before/during build.

---

## 2. Sensors (v1 scope)

| Sensor | In v1? | Notes |
|---|---|---|
| File watcher | ✅ | Content-based, not filename/save-event based (see Dedup) |
| Terminal hook | ✅ | Shell hook (`.zshrc`/`.bashrc` style), with mandatory secret redaction |
| Git hooks | ✅ | `post-commit` / `pre-push` |
| Test runner hook | ✅ | Structured output (e.g. `pytest --json-report`, Jest `--json`) |
| IDE extension | ❌ Deferred to v2 | Heaviest lift (VS Code Extension API); not needed to prove first signal |

---

## 3. Dedup logic

- **Rule:** Exact content-hash match only.
- A file save/rename with identical content to the last known meaningful state → **dropped, never becomes an event.**
- Similarity-based dedup (near-duplicate detection) is explicitly **out of scope for v1** — parked for later.

---

## 4. Episode correlation

**Problem:** raw events (save → test fail → save → test pass) need to be grouped into one "story" before Jev ever sees them — not treated as 4 unrelated events.

**v1 rule — time-window + file-overlap, with two refinements:**

1. **Adaptive time window** — the window extends while there's related activity (e.g. terminal output still being read after a test run), rather than using a single rigid timer.
2. **File-overlap by dependency** — uses a cheap static import/require check (regex/AST pass, no LLM) to relate files, not just "same folder" proximity. This catches cases like `auth.py` change + `test_auth.py` run even if they're in different directories.

**Explicitly deferred to v2:**
- Semantic diff similarity (embedding-based relatedness)
- Branch-awareness
- Cross-developer episode merging (this is Team Master / Layer 2 territory, not local sensor layer)

---

## 5. Secret redaction (terminal capture)

- **Non-negotiable, not optional**, even at 3-person prototype scale.
- **Approach:** pattern-based, fully local, zero network calls involved in detection (no LLM used to detect secrets — that would defeat the purpose).
- **Redaction granularity:** mask only the secret portion of a command; the rest of the command stays visible.
  - Example: `psql -h prod-db -U admin -p [REDACTED]` — command context preserved, secret masked.
- **Patterns covered in v1:** common key/token formats (`sk-...`, `ghp_...`, `AKIA...`, JWT-shaped strings), `key=`/`token=`/`password=`/`secret=` style assignments, `export VAR=...` where VAR name contains KEY/TOKEN/SECRET/PASSWORD/CREDENTIAL, connection strings (postgres/mysql/mongo/redis), values following auth flags (`-u`, `--password`, `--token`, `Authorization:` headers).
- **Original raw command is never stored and never sent anywhere.**
- Explicitly not doing in v1: perfect coverage of every possible secret format — known, accepted gap.

---

## 6. Jev triage criteria

Jev is cheap, rule-based, deterministic — **no LLM or ML needed for the triage decision itself.**

**Escalate an episode to Sonnet if ANY of the following are true (OR logic):**

1. The file/area touched has prior recorded history in the Experience Graph.
2. The episode contains a fail → retry → pass pattern.
3. The episode touches more than one distinct module/folder.
4. The episode includes deletion of existing logic.

**Otherwise:** the episode is recorded as a routine event in the Experience Graph. No Sonnet call. No intervention. Silence by default.

**Explicitly separate from triage:** severity scoring. Severity governs *how* an intervention is delivered (tone, whether pushback is accepted without new evidence), not *whether* to escalate. Severity is a future phase (see §8).

---

## 7. Experience Graph schema (v1)

Minimal schema — only what's needed to support §6's triage rules and produce a real intervention. **Stored as plain SQLite tables, not a graph database** — 3 nodes and 2 relationships don't justify a graph DB at this scale; that migration is a v2/scale decision.

**Nodes:**

```
EPISODE
  episode_id
  timestamp_start / timestamp_end
  developer
  files_touched (list)
  summary (Sonnet's output, if escalated — else null)
  had_deletion (bool)
  had_fail_retry_pass (bool)
  escalated (bool)

ASSUMPTION
  assumption_id
  statement
  source_episode_id
  created_at
  current_validity (valid / unverified / contradicted — starts "unverified")

FILE
  file_path
  imports (list of file_paths)
```

**Relationships:**

```
EPISODE --touched--> FILE
EPISODE --produced--> ASSUMPTION
```

**Explicitly not in v1:** Outcome node, severity fields on graph nodes, CONTRADICTS/BUILDS_ON/SUPERSEDES relationships, evidence-hierarchy modeling. These require multiple episodes touching the same assumption over time to be meaningful — not enough data will exist yet in a few weeks of 3-person activity.

---

## 8. Explicitly parked (not v1, revisit later)

- Severity as a trained scoring engine (currently just a future concept — starts naive/manual once outcome data exists).
- Any sync-off-machine / multi-user / cloud sync design.
- Privacy/framing language for a real company rollout (fine at 3-friends scale without formal design).
- IDE extension (VS Code / JetBrains).
- Near-duplicate (similarity-based) dedup.
- Semantic and branch-aware episode correlation.
- Cross-developer / hierarchical (Team Master, Company Master) aggregation.
- Graph database migration (Neo4j/Neptune) — SQLite is sufficient for v1 scale.

---

## 9. Tech stack

### 9.1 Prototype (v1) stack

- **Python** — file watcher (`watchdog`), local sensor/normalizer, SQLite storage, Anthropic API calls.
- **Bash/Zsh hook script** — terminal capture + local redaction.
- **Native git hooks** — commit-level events.
- **pytest-json-report / Jest `--json` / `go test -json`** — test signal (pick per whatever the repo's stack turns out to be).
- **SQLite** — single local datastore, no server.
- **Anthropic API** — Claude Haiku not used for triage (triage is rule-based, §6); Claude Sonnet used only for escalated deep-reasoning calls.
- **Infra cost target:** near-zero — everything runs locally, no cloud dependency required for v1.

Python is the deliberate choice for the v1 local agent too (not Go/Rust yet) — prototype priority is proving the sensor/episode/triage design works at all, not runtime efficiency. Language migration for the local agent happens only after that's proven (see 9.2).

### 9.2 At-scale stack (target architecture, post-prototype)

Each layer is chosen for that layer's actual constraints — not one language system-wide.

| Layer | Language/stack | Why |
|---|---|---|
| **Local Agent** (file watcher, terminal hook, dedup, episode correlation, secret redaction) | **Go for v1 rollout → Rust once sensor design is proven** | Runs silently on every developer's machine, all day — needs near-zero memory footprint, single static binary, no runtime dependency, no GC-pause lag. Rust's memory safety without GC is also a real argument in security-audit conversations, since this layer touches terminal history and file contents. Go ships faster while the design is still unproven; Rust is the correct long-term target once it's validated — don't pay Rust's learning-curve tax before there's proof the local-sensor thesis works at all. |
| **IDE Extension** (v2) | **TypeScript** (VS Code Extension API); Kotlin for JetBrains later | Platform-mandated, not a free choice. |
| **Ingestion API** (receives events from many local agents) | **Go** | Needs to handle bursty, concurrent, I/O-bound traffic (everyone commits around similar times) cheaply. Goroutines are built for exactly this; simpler to operate than a JVM-based alternative at this layer. |
| **Team Master / Company Master** (orchestration, graph queries, Claude API calls, future severity model) | **Python** | Deepest, most mature ecosystem for LLM SDKs, graph DB drivers, and ML tooling. This layer runs on a handful of servers, not thousands of laptops — iteration speed and library availability matter more here than raw runtime performance. |
| **Experience Graph DB** | **SQLite (v1)** → **Neo4j or Amazon Neptune** (multi-company scale) | 3 nodes / 2 relationship types don't justify a graph DB yet. Migrate once relationship types (CONTRADICTS/BUILDS_ON/SUPERSEDES) and cross-team queries are actually in scope. |
| **Human-facing dashboard** | **TypeScript + Next.js** | Standard for this layer; no reason to be contrarian here. |

**Sequencing discipline:** same principle applied everywhere else in this plan (naive severity before trained severity, simple dedup before similarity dedup) — ship the simpler, faster-to-build version first, migrate to the "correct" long-term choice only once the design it's built on is proven, not before.

---

## 10. Still open (not yet decided)

- Exact matching algorithm, feature scope, and name for the dev-matching app (§1) — product category and concept are locked, implementation details are for the 3 of you to decide.
- Delivery channel for interventions (Slack / terminal output / local file) — deliberately deferred; not a system decision, just a UI detail. Default for now: write to a local file/log.
- How you'll judge whether the prototype "worked" after a few weeks — this is a human judgment call for the 3 of you to make, not a system feature. Worth agreeing on informally before you start (e.g. "did it flag at least one real thing we'd have missed otherwise") so you don't end up with an ambiguous result like validation night's tie.

## 11. Jev / Sonnet evidence rule (prompt instruction, locked)

When Sonnet is escalated an episode (per §6 triggers), it must follow this rule:

> Only state a decision, assumption, or risk if the episode's diff, commit messages, and file history directly support it. If the evidence is thin — a change with no clear reason, no related history, no test signal explaining it — say "insufficient evidence" and record only the observed facts (what changed, where), not an inferred reason. Never fill a gap in the evidence with a plausible-sounding guess.

This mirrors the behavior already validated on validation night (Claude correctly said "insufficient evidence" rather than hallucinating when given a broken dataset) — codified here as an explicit instruction rather than left implicit.

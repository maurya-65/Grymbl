# Chapter 7: Operating

*Installing and running Grymbl for real, the API key, costs, and fixing problems.*

---

## Installing

Prerequisites: Git, Python 3.12+, and uv ([Developing: setup](06_developing.md#setting-up-from-zero)).

```powershell
uv tool install --editable C:\dev\Grymbl
grymbl --help                      # confirms `grymbl` is on your PATH
```

`grymbl` must be on your `PATH` ([Foundations](01_foundations.md#environment-variables)) for the
git, shell, and Claude Code hooks to work, because they all call plain `grymbl`.

---

## Setting the API key

Grymbl reads the key from the `ANTHROPIC_API_KEY` environment variable. Without it, Grymbl
still records everything; it just can't analyse escalated episodes.

**Rules for the key:**
- **Never paste it into a chat, document, or code**, including chats with AI assistants. It
  gets stored in plain text in transcripts. If that happens, revoke it.
- **Revoke and replace** a key at [console.anthropic.com](https://console.anthropic.com) →
  *API keys* whenever it may have been exposed.
- **Set a monthly spend limit** in the same Console. It's the one cost control no code bug can
  get around.

**The safe way to set it on Windows.** This was learned the hard way; see
[Lessons](08_history_and_lessons.md#bugs-found-and-what-they-taught-us). Run this in
**PowerShell** (not Command Prompt or Git Bash):

```powershell
Read-Host "Now copy your API key from the Anthropic Console, then press Enter here"; [Environment]::SetEnvironmentVariable("ANTHROPIC_API_KEY", (Get-Clipboard).Trim(), "User"); Set-Clipboard -Value " "; $k = [Environment]::GetEnvironmentVariable("ANTHROPIC_API_KEY", "User"); "length: $($k.Length), valid prefix: $($k.StartsWith('sk-ant-'))"
```

1. Paste and run the line. It pauses.
2. *Now* copy the key from the Console, come back, and press Enter.
3. It must print `valid prefix: True` with a length around 100.

**Why it's built this way:**

| Pitfall | What went wrong | How the command avoids it |
|---|---|---|
| Ctrl+V into a hidden-input prompt (`Read-Host -AsSecureString`) | Windows PowerShell 5.1 types an invisible control character instead of pasting. The "key" was 1 character long | Reads the clipboard directly |
| Copying the command overwrote the copied key | The clipboard held the command text, not the key | The pause lets you copy the key *after* the command is already running |
| Typing the key into a command (`setx ANTHROPIC_API_KEY "sk-…"`) | Saved in PowerShell's history file in plain text | The key never appears in any command |

**macOS/Linux:** add `export ANTHROPIC_API_KEY="…"` to `~/.zshrc` or `~/.bashrc` with a text
editor (not by typing the command, which saves it in shell history), then open a new terminal.

**Take effect:** only terminals opened *after* setting it see the new key. Restart
`grymbl watch` afterwards.

---

## Setting up a project

Inside the project you want watched:

```powershell
cd C:\path\to\your\project
grymbl init
```

This creates `.grymbl/`, takes a baseline, and installs git and Claude Code hooks
([Chapter 3](03_how_it_works.md#setup-with-grymbl-init)). Use `grymbl init --no-agent-hooks` to
skip Claude Code.

---

## Loading the terminal hook

Once per computer, add one line to your shell's settings file (create the file if it doesn't
exist), then open a new terminal:

| Shell | Settings file | Line to add |
|---|---|---|
| **PowerShell** | The path printed by `$PROFILE` | `grymbl shell-hook powershell \| Out-String \| Invoke-Expression` |
| **bash** (incl. Git Bash) | `~/.bashrc` | `eval "$(grymbl shell-hook bash)"` |
| **zsh** | `~/.zshrc` | `eval "$(grymbl shell-hook zsh)"` |

The hook does nothing outside projects that have a `.grymbl/` folder, so it's safe to load
globally.

**Privacy tip:** with `HISTCONTROL=ignorespace` (bash) or `setopt HIST_IGNORE_SPACE` (zsh), a
command typed with a leading space isn't captured.

---

## Running the watcher

```powershell
cd C:\path\to\your\project
grymbl watch
```

Leave it running in its own terminal tab while you work. It prints a start message, then stays
quiet except for warnings, AI-call token counts, and problems. Stop it with **Ctrl+C**.

- Only one watcher per project: a second one refuses to start.
- If the watcher isn't running, hooks still record events. They're grouped and judged the next
  time it starts. (File changes made while it was off become the new baseline, not events.)
- Auto-starting the watcher at login isn't built yet ([backlog](09_status_and_roadmap.md#the-backlog)).

---

## Everyday commands

| Command | Use |
|---|---|
| `grymbl watch` | Run the watcher (keep it open) |
| `grymbl status` | Recent episodes: time, ID, open/closed, routine/ESCALATED, files, the agent's intent, the summary |
| `grymbl status -n 30` | More episodes |
| `grymbl report` | **The full picture**: writes `.grymbl/report.html` and opens it (last 30 days; `--days 7`, `--all`, `--no-open`) |
| `grymbl test -- pytest` | Run tests through Grymbl (also `npx jest`, `go test ./...`) |
| `grymbl init` | Set up a project (safe to re-run) |
| `grymbl shell-hook <shell>` | Print a terminal hook |

**Reading what Grymbl concluded:**

| Where | What's there |
|---|---|
| `grymbl report` | Everything, systematically: charts, warnings, every episode's full timeline, hotspots, assumptions, cost ([details](03_how_it_works.md#the-report)) |
| `.grymbl/interventions.md` | Every warning, with time, episode, files, and reason |
| `grymbl status` | Episodes and their summaries |
| The watcher's window | Warnings and per-call token usage as they happen |
| `.grymbl/grymbl.log` | Grymbl's own errors from hooks (normally empty) |

---

## Watching costs

- **Per call:** the watcher logs `Sonnet analysed episode X: N input, M output tokens`. The cost
  is `N × $2/1,000,000 + M × $10/1,000,000`. The first real call: 1,367 in + 205 out ≈
  **US$0.005**.
- **Per day:** at most **25** calls (`daily_call_cap`). After that, the watcher logs *"Daily cap
  of 25 Sonnet calls reached"* and records escalations without analysis until midnight UTC.
- **Budget estimate:** 5 CAD (≈ US$3.60) lasts about a month even if the cap is hit daily with
  small episodes, and much longer in normal use. The theoretical worst case (every call at the
  evidence cap) is about 1.5 days.
- **In the report:** `grymbl report` shows cost per day and in total, from the saved per-call
  records.
- **Ground truth:** the Anthropic Console's usage page.

To change the cap or effort, see [Developing: change a setting](06_developing.md#change-a-setting-time-windows-thresholds-cost-caps).

---

## Your data

| What | Where |
|---|---|
| Everything Grymbl knows about a project | `<project>/.grymbl/grymbl.db` |
| Warnings | `<project>/.grymbl/interventions.md` |
| Grymbl's error log | `<project>/.grymbl/grymbl.log` |
| Claude Code hook settings | `<project>/.claude/settings.local.json` |
| Git hooks | `<project>/.git/hooks/post-commit`, `pre-push` |
| Terminal hook | One line in your shell's settings file |

- **Back up** the history: copy `.grymbl/grymbl.db` while the watcher is stopped.
- **Reset** a project's memory: stop the watcher, delete `.grymbl/`, run `grymbl init` again.
- It's all local and git-ignored. Nothing is uploaded except redacted evidence for Sonnet calls.

---

## Uninstalling

1. Remove the line from your shell settings file.
2. In each project: delete `.grymbl/`; delete `.git/hooks/post-commit` and `pre-push` (if
   they contain `# grymbl-hook`); remove the `grymbl capture-agent` entries from
   `.claude/settings.local.json`.
3. `uv tool uninstall grymbl`.
4. Optionally remove the key:
   `[Environment]::SetEnvironmentVariable("ANTHROPIC_API_KEY", $null, "User")`.

---

## Troubleshooting

| Symptom | Likely cause | Fix |
|---|---|---|
| `grymbl: command not found` / not recognised | Not installed on `PATH` | `uv tool install --editable C:\dev\Grymbl`, then open a new terminal |
| "Not a Grymbl-watched repository" | Running outside a project with `.grymbl/` | `cd` into the project, or `grymbl init` |
| "another watcher is already running" | A watcher is open elsewhere, or a stray one survived | Close the other one. On Windows, stop strays with the command in [Developing](06_developing.md#a-safe-sandbox-for-trying-changes) |
| Typed commands not appearing in episodes | Hook not loaded, or the shell wasn't restarted | Check your settings-file line; open a new terminal; confirm you're inside the project |
| Commits not appearing | `grymbl` not on `PATH` when git runs the hook, or another tool's hook blocked the install | Install globally; check `.git/hooks/post-commit` contains `# grymbl-hook` |
| Claude Code actions not appearing | Hooks missing, or `grymbl` not on `PATH` | Re-run `grymbl init`; check `.claude/settings.local.json` |
| Watcher logs "No Anthropic credentials" | Key not set, or set after the terminal opened | [Set the key](#setting-the-api-key); restart the watcher from a new terminal |
| Watcher logs "API error 400" | Usually a malformed key (stray characters from pasting) | Re-set it with the safe command; it must print `valid prefix: True` |
| "API error 401" | Key revoked or wrong | Create a new key |
| "API error 429" / rate limited | Too many requests | Wait. Grymbl records without analysis meanwhile |
| "Daily cap … reached" | 25 calls today | Normal. Resets at midnight UTC, or raise `daily_call_cap` |
| Episodes stay `open` | Watcher not running, or the quiet period hasn't passed | Start the watcher; wait 5 minutes (15 after a failure) |
| Too many escalations | Rule 1 snowballing on busy files, or broad multi-module work | Check `grymbl status`; consider tuning (see [Roadmap](09_status_and_roadmap.md)) |
| Something odd from a hook | A hook error | Read `.grymbl/grymbl.log` |

---

<sub>Next: [Chapter 8: History and Lessons](08_history_and_lessons.md). Copyright © 2026 Maurya Oganja. All rights reserved.</sub>

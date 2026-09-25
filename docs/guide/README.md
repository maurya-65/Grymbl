# The Grymbl Guide

**Start here.** This guide is written so that someone who has never seen Grymbl, and who may
not have a strong technical background, can understand it completely, run it, and keep
building it, even if the person who built it is no longer around to answer questions.

It is also written for the owner, so that you always know exactly what is going on inside
your product.

---

## Which path should I read?

| You are… | Read these, in order |
|---|---|
| **New to software concepts** | [1. Foundations](01_foundations.md) → [2. The Product](02_the_product.md) → [3. How It Works](03_how_it_works.md). Keep the [Glossary](glossary.md) open |
| **The owner** | [2. The Product](02_the_product.md) → [3. How It Works](03_how_it_works.md) → [9. Status and Roadmap](09_status_and_roadmap.md) → [8. History and Lessons](08_history_and_lessons.md) |
| **A developer taking over** | Everything, in order. Then [6. Developing](06_developing.md) before touching code |
| **Just want to use it** | [2. The Product](02_the_product.md) → [7. Operating](07_operating.md) |

---

## The chapters

| # | Chapter | What you'll learn |
|---|---|---|
| 1 | [Foundations](01_foundations.md) | Every computing concept Grymbl relies on, explained from zero with analogies: files, processes, terminals, git, hooks, APIs, databases, hashing, regex, AI models, and more |
| 2 | [The Product](02_the_product.md) | What Grymbl is, the problem it solves, its philosophy, and one story that follows a change all the way through |
| 3 | [How It Works](03_how_it_works.md) | Every part of the system in depth: sensors, redaction, storage, episodes, Jev, Sonnet, warnings, cost controls |
| 4 | [Tech Stack](04_tech_stack.md) | Every tool and language: what it is, what the alternatives were, why we chose it, and what we gave up |
| 5 | [Codebase Tour](05_codebase_tour.md) | Every file and important function, and how a piece of data travels through the code |
| 6 | [Developing](06_developing.md) | Setting up from scratch, the rules for changing code, and step-by-step recipes for common changes |
| 7 | [Operating](07_operating.md) | Installing and running Grymbl for real, the API key, costs, and a troubleshooting table |
| 8 | [History and Lessons](08_history_and_lessons.md) | What was built and when, every decision and why, and every bug found and what it taught us |
| 9 | [Status and Roadmap](09_status_and_roadmap.md) | What's proven, what isn't, what's missing, and what to build next, in priority order |
| — | [Glossary](glossary.md) | Every term, alphabetically, each linking to its full explanation |

---

## The one-paragraph summary

Grymbl is a program that runs on a developer's own computer and quietly watches them build
software: file changes, terminal commands, git commits, test runs, and the actions of AI
coding assistants like Claude Code. It groups that activity into "episodes" (stories of
work), uses four simple rules to decide which few episodes deserve attention, and asks an AI
model (Claude Sonnet) to analyse only those, under a strict rule never to guess beyond the
evidence. It speaks up only when current work resembles something that caused trouble before.
Most of the time it stays silent, and that is by design.

---

## Other documents in this repository

| Document | What it is |
|---|---|
| [`../prototype_plan.md`](../prototype_plan.md) | The original locked specification for v1. Chapters here cite it as "plan §N" |
| [`../v1.1_agent_awareness.md`](../v1.1_agent_awareness.md) | The extension that added AI-agent awareness, and its roadmap |
| [`../../README.md`](../../README.md) | The repository's front page |

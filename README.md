# Daily Automation: a COO Twin for Hermes Agent

**For builders, operators, founders, consultants, and anyone carrying too many projects in one head.**

Daily Automation turns [Hermes Agent](https://hermes-agent.nousresearch.com/docs) into a practical COO-style operating system: it reads your calendar, tasks, notes, and configured workstreams; helps you decide what matters today; captures what happened; and closes the loop before tomorrow starts.

It is not a productivity app you remember to open. It is a repeatable daily rhythm for people who are spread across multiple companies, clients, teams, and initiatives.

If your day looks like this:

- one business has urgent follow-ups,
- another has meetings and deliverables,
- a third has long-term strategy work,
- personal notes are scattered across your phone and laptop,
- and by 7pm you cannot remember which thread mattered most,

then this repo is for you.

---

## The problem this solves

Busy people do not fail because they lack tasks. They fail because their work has no operating layer.

A real COO does a few things relentlessly:

1. **Turns noise into priorities.** Not every message, meeting, or idea deserves equal weight.
2. **Protects execution.** The important work must show up before the day gets eaten.
3. **Maintains context.** Decisions, follow-ups, and open loops need a home.
4. **Closes the loop.** Work that did not finish today must become tomorrow's plan, not disappear.
5. **Improves the system.** The operating process should get sharper every week.

Daily Automation gives Hermes the structure to do that with you.

---

## What this repository is

This is a public-safe template for building a personal or business **COO Twin** on top of Hermes Agent.

The repo contains:

- **Skills** — Markdown operating procedures that teach Hermes how to run workflows like `/start-day`, `/end-day`, `/sync-sweep`, and `/automation`.
- **Scripts** — Python/Bash helpers for source checks, output planning, task routing, telemetry, idempotency, and validation.
- **Configuration** — YAML files for your workstreams, source systems, routing rules, and operating mode.
- **Local state folders** — places for daily logs, staged writes, vault notes, automation history, and outputs.
- **Validation gates** — tests and lint scripts so your personal operating system does not silently drift.

It is intentionally not a normal SaaS app. There is no dashboard to deploy. The interface is Hermes: terminal, Telegram, or any supported Hermes gateway channel.

---

## Who it is for

Daily Automation works best for someone who is balancing many threads inside one ecosystem:

| You are... | Daily Automation helps by... |
|---|---|
| A founder or startup operator | turning scattered tasks into daily execution outputs |
| A builder shipping across products | keeping projects, notes, decisions, and follow-ups connected |
| A consultant or agency lead | tracking clients, meetings, deliverables, and next actions |
| A business owner | making sure operations, sales, admin, and strategy all stay visible |
| A busy professional | creating a lightweight COO rhythm without hiring a COO |

The common pattern: **too many moving parts, not enough structured reflection.**

---

## The daily rhythm

Daily Automation is built around a simple loop.

```text
Morning      /start-day      decide what matters
During day   capture notes   keep raw context flowing
Recurring    cron jobs       run saved checks and nudges
Evening      /end-day        compare plan vs reality
Cleanup      /sync-sweep     route loose thoughts into durable systems
Learning     skills          improve the workflow as you use it
```

### 1. Start the day with order

Run `/start-day` when the day begins.

Hermes reads your configured sources — calendar, tasks, Notion, local Markdown vault, previous priorities, and daily logs — then produces a concise operating brief.

A good morning brief answers:

- What is already scheduled?
- What is overdue or stale?
- What changed since yesterday?
- What are the **top outputs** that would make today successful?
- Which tasks belong to which project, business unit, or workstream?
- What needs a decision before execution?

This replaces the habit of opening four apps and trying to remember what matters.

### 2. Keep daily logs as the source of truth

Daily logs are the running record of what actually happened.

They can include:

- morning plan,
- top three outcomes,
- meeting notes,
- raw braindumps,
- tasks completed,
- unexpected work,
- observations,
- carry-forwards,
- links to source systems.

The point is not journaling for its own sake. The point is operational memory. A daily log gives `/end-day`, `/sync-sweep`, and future Hermes sessions something concrete to reason over.

### 3. Use cron jobs for recurring attention

Some work should not depend on memory.

Daily Automation supports cron-style automations through `/automation` and `state/automations.yaml`. These are saved prompts with cadences and delivery targets.

Examples:

- weekly review,
- overdue client follow-up scan,
- stale task nudge,
- vault health check,
- morning readiness check,
- end-of-week reflection prompt.

Hermes can also run native scheduled jobs with `hermes cron`, so the system can deliver reminders, reports, or checks back to Telegram or another configured channel.

The philosophy: **if it matters repeatedly, schedule it.**

### 4. End the day with reflection and carry-forward

Run `/end-day` when the workday is over.

The end-day workflow compares your morning plan against what actually happened:

- Which top outputs moved?
- Which meetings or unplanned events changed the day?
- Which tasks were completed, created, or left stale?
- What should carry forward?
- What should be re-routed into Notion, Google Tasks, Calendar, or the vault?
- What did the day teach you about the system?

This is where the COO function matters most. A busy day is not complete just because it ended. It is complete when the residue has been sorted.

### 5. Sync loose thoughts before they disappear

`/sync-sweep` reads the braindump section of today's daily note, extracts entity mentions, resolves them against your workspace, and proposes updates to the correct destination.

For example, a raw line like:

> Follow up with Example Client about the onboarding blocker and next appointment.

can become a staged, approval-gated update on the relevant Notion page under a `## Latest:` section.

This keeps stray thoughts from staying trapped in the daily note forever.

### 6. Let the skills get better over time

The strongest part of Hermes is that workflows can become skills.

When a process works, you write it down as a skill. When it fails, you patch the skill. Over time, Hermes becomes better at your way of operating because the procedures live in the repo instead of disappearing into one-off chats.

That means Daily Automation is not only a set of prompts. It is an evolving operating manual for your life and work.

---

## Core outputs

Daily Automation is optimized around concrete outputs, not vague chat.

| Output | Where it shows up | Why it matters |
|---|---|---|
| **Daily operating brief** | `/start-day`, `logs/YYYY-MM-DD.md` | gives you the day's priorities before the day takes over |
| **Top outputs for the day** | morning plan | forces focus on work that actually moves the system |
| **Daily logs** | `logs/` and/or `vault/daily/` | creates an auditable trail of plans, events, and reflections |
| **Cron/automation reports** | `state/automations.yaml`, delivery targets, Telegram/stdout/vault | makes recurring reviews and nudges happen without relying on memory |
| **Meeting prep** | `/meeting-prep` | gives context before calls instead of after mistakes |
| **Meeting capture** | `/capture-meeting` | turns raw notes into tasks, decisions, follow-ups, and knowledge |
| **Sync sweeps** | `/sync-sweep`, `.context/`, Notion proposals | routes loose braindump items into durable records |
| **End-day reflection** | `/end-day`, daily log, priorities state | compares plan vs actual and sets up tomorrow |
| **Skill improvements** | `.claude/skills/` | compounds the system as your workflows mature |

---

## Main workflows

| Skill | Use it when... | What it produces |
|---|---|---|
| `/start-day` | you are beginning the day | phone-friendly plan, top outcomes, risks, stale items, source status |
| `/meeting-prep` | a meeting is coming up | short dossier: people, context, open tasks, suggested questions |
| `/capture-meeting` | you have rough meeting notes | proposed tasks, decisions, follow-ups, CRM/activity updates, vault notes |
| `/end-day` | you are closing the day | planned-vs-actual retro, carry-forwards, reflections, tomorrow setup |
| `/sync-sweep` | raw daily-note thoughts need routing | staged updates from braindump lines to the right Notion pages |
| `/automation` | saved prompts are due | recurring reviews/checks delivered to stdout, vault, daily note, or other channels |
| `/vault-health` | your local notes need cleanup | orphan note checks, broken-link checks, stale inbox review |
| `/refine-calendar` | priorities need time blocks | proposed calendar blocks from the daily plan |
| `/setup` | you are adapting the system | workstream and source configuration for your own ecosystem |

Experimental `*-team` variants exist for parallelized versions of the main workflows.

---

## Architecture

```text
Hermes Agent
  |
  | loads AGENTS.md / CLAUDE.md project context
  | loads COO Twin skills from .claude/skills/
  v
Daily Automation skills
  |
  | use deterministic scripts for checks, parsing, routing, and telemetry
  v
Local operating repo
  |
  |-- config/        streams, sources, routing, calendar planning
  |-- state/         operating mode, priorities, automation history
  |-- logs/          daily logs and telemetry
  |-- vault/         local Markdown notes / Obsidian-style knowledge base
  |-- .context/      staged and applied write payloads
  |-- scripts/       preflight, validation, parsing, sync, planning helpers
  v
External systems, approval-gated
  |
  |-- Notion         tasks, activity log, CRM/pages, meeting records
  |-- Google         Calendar and Tasks
  |-- Hermes Cron    scheduled agent runs and reports
  |-- Telegram       mobile delivery through the Hermes gateway
```

The key design rule is simple:

> **Read broadly. Propose clearly. Write only through approval gates.**

---

## Safety model

This repo is built for real operations, so it assumes mistakes are expensive.

Daily Automation uses:

- **read-first workflows** — collect and preview before writing;
- **trust gates** — external writes require approval unless explicitly allowed by mode;
- **operating modes** — observe, draft, approved, auto, locked;
- **staged payloads** — proposed writes live in `.context/` before they are applied;
- **idempotency IDs** — repeated runs should not duplicate work;
- **telemetry** — each skill records run status and timing;
- **PHI/sensitive-input gates** — capture workflows can refuse risky raw input;
- **validation scripts** — skill lint, stream/source checks, tests, and hygiene checks.

For most users, the right default is **draft mode**: Hermes can read, analyze, and propose, but asks before writing externally.

---

## Repository map

```text
.
├── AGENTS.md / CLAUDE.md          # project operating context for agents
├── .claude/skills/                # first-party COO Twin skills and support skills
├── config/                        # streams, sources, routing, calendar config
├── docs/                          # conventions, deploy notes, data-source docs
├── scripts/                       # helper scripts and validation gates
├── state/                         # local operating state and automation config
├── logs/                          # daily logs and telemetry output
├── vault/                         # local Markdown vault / daily notes
├── templates/                     # Notion templates and reusable setup files
├── tests/                         # unit/integration validation
└── .context/                      # staged/applied write payloads
```

Public releases should keep reusable skills, scripts, templates, and docs while excluding private runtime data.

---

## Quick start

### 1. Install Hermes Agent

```bash
curl -fsSL https://hermes-agent.nousresearch.com/install.sh | bash
hermes setup
hermes doctor
```

See the Hermes docs: <https://hermes-agent.nousresearch.com/docs>

### 2. Clone the repo

```bash
git clone https://github.com/afain12/daily-automation.git
cd daily-automation
```

### 3. Install the minimal Python dependency

```bash
python3 -m pip install pyyaml
```

### 4. Configure your sources

Start with the example config files and adapt them to your own ecosystem:

- `config/streams.yaml` — your companies, clients, projects, or life areas;
- `config/sources.yaml` — Notion, Google, vault, and workspace IDs;
- `config/routing-rules.yaml` — how notes and tasks should be routed;
- `state/coo_mode.yaml` — operating mode and approval posture;
- `state/automations.yaml` — recurring prompts and cadences.

### 5. Run validation

```bash
python -m unittest discover -s tests
bash scripts/skill_lint.sh
python scripts/streams_check.py
bash scripts/test_phi_gate.sh
```

### 6. Start using the skills

From the repo root, open Hermes:

```bash
hermes
```

Then try:

```text
/start-day
/meeting-prep
/capture-meeting
/end-day
/sync-sweep
/automation
```

If your Hermes installation does not automatically load project skills, copy or symlink the COO Twin skills into your Hermes skills directory, then restart Hermes or run `/reload-skills`.

---

## Example day

```text
7:30 AM   /start-day
          → "Here are the 3 outputs that matter today."

9:50 AM   /meeting-prep for Client A
          → "Here is the context, open loop, and ask."

1:20 PM   /capture-meeting with rough notes
          → "These are the tasks, decisions, and follow-ups I propose."

4:00 PM   /automation
          → "Two recurring checks are due; approve or skip?"

6:30 PM   /end-day
          → "Here is what moved, what drifted, and what carries forward."

6:45 PM   /sync-sweep
          → "These braindump items map to durable records; approve appends?"
```

The result is not a perfect day. The result is a day that leaves behind usable context.

---

## Customizing it for your ecosystem

Daily Automation is meant to be forked.

Replace the default streams with your own:

```yaml
streams:
  - name: Company A
  - name: Product B
  - name: Client Work
  - name: Personal Admin
  - name: Research
```

Then teach the system how to route work:

- which Notion database holds tasks,
- which calendar represents execution blocks,
- which tags or keywords map to each stream,
- which notes belong in the vault,
- which recurring automations matter,
- which writes require approval.

The first version can be simple. The system gets valuable once you run it daily and patch the skills when your real workflow teaches you something.

---

## Public/private hygiene

This repository is designed to be public-safe, but your fork may not be unless you keep private runtime data out of git.

Do **not** commit:

- `.env` or `.secrets/`,
- OAuth tokens or client secrets,
- Notion exports with private data,
- customer/client/provider records,
- personal daily notes,
- raw meeting transcripts,
- generated logs,
- staged write payloads,
- local vault content.

Before publishing your own version, run:

```bash
git status --short
python -m unittest discover -s tests
bash scripts/skill_lint.sh
python scripts/streams_check.py
bash scripts/test_phi_gate.sh
git grep -n -i -E 'token|secret|password|client_secret|refresh_token|access_token|private key' -- . ':!.env.example'
```

If a secret was committed, rotate it. Do not rely on a later delete commit.

---

## Why this matters

Most people try to solve overload with a better task list.

A task list is not enough when your work crosses many organizations, relationships, projects, and time horizons. You need a lightweight operating cadence:

- decide the day,
- protect the outputs,
- capture reality,
- route the residue,
- reflect,
- improve the system.

That is what a COO does for a business.

Daily Automation brings that function into your daily life through Hermes Agent: not as a replacement for judgment, but as a disciplined second brain that keeps asking, **what matters, what changed, what is next, and what did we learn?**

---

## Maintainer note

Keep the repo generic, reusable, and safe. The value is in the workflow architecture: skills, scripts, validation, daily logs, automations, and approval-gated execution. Your private data belongs in your local runtime, not in the public template.

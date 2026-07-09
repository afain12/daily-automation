# Daily Automation COO Twin for Hermes Agent

A complete, public-safe template for running a personal or business COO-style AI agent with [Hermes Agent](https://hermes-agent.nousresearch.com/docs).

This repository gives Hermes a structured operating system for daily execution: morning planning, meeting prep, meeting capture, end-of-day review, task routing, Notion/Google/Obsidian context, and approval-gated writes.

The original private production data has been removed. This repo is meant to be cloned by another operator and connected to their own Notion workspace, Google Calendar/Tasks, local Markdown vault, and Hermes installation.

---

## Table of contents

1. What this repo is
2. How the COO Twin works
3. What is included
4. What is intentionally excluded
5. System architecture
6. Required accounts and tools
7. A-to-Z local setup
8. Configure Hermes Agent
9. Configure this repo
10. Configure Notion
11. Configure Google Calendar and Tasks
12. Configure the local vault
13. Run validation
14. Use the COO skills
15. Daily operating rhythm
16. Safety model and approval gates
17. File and folder reference
18. Customizing for your business
19. Public/private hygiene checklist
20. Troubleshooting

---

## 1. What this repo is

This repo is a COO Twin / daily-operations workspace for Hermes Agent.

It is not a normal web app. There is no server to deploy and no frontend to open. The repo is a structured operations brain made of:

- Markdown skills that teach Hermes how to perform COO workflows.
- Python and Bash helper scripts for parsing, validation, routing, telemetry, and planning.
- YAML configuration for your business streams and data sources.
- Notion templates for a simple operating workspace.
- A local Markdown vault layout for daily notes and knowledge capture.
- Tests and validation scripts so changes do not silently break the operating system.

The goal is to let Hermes act like a practical Chief of Staff / COO assistant:

- Pull the day together from Notion, Calendar, Tasks, and notes.
- Identify the highest-leverage work.
- Prepare you before meetings.
- Convert meeting notes into tasks, decisions, follow-ups, and knowledge.
- Close the loop at the end of the day.
- Keep everything approval-gated so the agent proposes before it writes.

---

## 2. How the COO Twin works

The repo is built around a few repeatable workflows.

### Morning: `/start-day`

Hermes reads your configured sources and produces a phone-friendly daily operating brief:

- calendar context
- open tasks
- stale or overdue items
- top outputs for the day
- execution plan
- risks and unresolved pending writes

### Before a meeting: `/meeting-prep`

Hermes builds a short pre-meeting dossier:

- who is involved
- recent activity
- related tasks
- relevant notes
- suggested questions or next moves

### After a meeting: `/capture-meeting`

Hermes takes rough notes and splits them into the right destinations:

- action items → Notion tasks
- decisions → activity log
- follow-up meetings → calendar proposals
- useful context → Markdown vault notes
- ambiguous items → ask the operator

### End of day: `/end-day`

Hermes reviews the day against the plan:

- what moved
- what did not move
- what should carry forward
- what needs routing to Notion, Tasks, Calendar, or the vault
- what should become tomorrow's priority

### Ongoing: `/automation`, `/vault-health`, `/sync-sweep`, `/refine-calendar`

These supporting skills handle recurring prompts, vault hygiene, entity/routing cleanup, and calendar block proposals.

---

## 3. What is included

### First-party COO skills

These are the core reusable workflows:

- `.claude/skills/start-day/SKILL.md`
- `.claude/skills/start-day-team/SKILL.md`
- `.claude/skills/meeting-prep/SKILL.md`
- `.claude/skills/capture-meeting/SKILL.md`
- `.claude/skills/capture-meeting-team/SKILL.md`
- `.claude/skills/end-day/SKILL.md`
- `.claude/skills/end-day-team/SKILL.md`
- `.claude/skills/refine-calendar/SKILL.md`
- `.claude/skills/sync-sweep/SKILL.md`
- `.claude/skills/automation/SKILL.md`
- `.claude/skills/vault-health/SKILL.md`
- `.claude/skills/setup/SKILL.md`
- `.claude/skills/notion-probe/SKILL.md`
- `.claude/skills/notion-map/SKILL.md`
- `.claude/skills/notion-template-install/SKILL.md`
- `.claude/skills/notion-ui-ops/SKILL.md`

### Support skills

The repo also includes reusable support skills for Notion, documentation lookup, testing, security, startup planning, task coordination, and related workflows.

### Scripts

Important helper scripts include:

- `scripts/preflight.sh` — Step 0 check for mode and resources.
- `scripts/check_mode.sh` — reads local write mode.
- `scripts/skill_lint.sh` — validates first-party COO skills.
- `scripts/streams_check.py` — checks stream/source consistency.
- `scripts/phi_scan.sh` — simple sensitive-input gate.
- `scripts/test_phi_gate.sh` — integration test for the sensitive-input gate.
- `scripts/action_id.sh` — idempotency helper for proposed writes.
- `scripts/telemetry.sh` — local telemetry append helper.
- `scripts/capture_meeting_parse.py` — deterministic meeting-note parsing helpers.
- `scripts/output_planning.py` — daily output model helpers.
- `scripts/calendar_planning.py` — pure calendar block planning logic.
- `scripts/refine_calendar.py` — daily plan to calendar proposal helper.
- `scripts/vault_search.py` and `scripts/vault_health.py` — local Markdown vault support.

### Templates and config

- `config/streams.yaml` — your business units / workstreams.
- `config/sources.yaml` — Notion, Google, and vault source definitions.
- `config/calendar.yaml` — calendar block planning rules.
- `config/routing-rules.yaml` — meeting note routing rules.
- `templates/notion/*.json` — empty Notion database templates.
- `.env.example` — names of required secrets, with no values.
- `.claude/settings.local.json.example` — local Claude/Hermes-style settings example.

---

## 4. What is intentionally excluded

This public template does not include private runtime data.

Ignored or placeholder-only:

- `.env`
- `.secrets/`
- OAuth token files
- `client_secret_*.json`
- local agent settings with filled credentials
- Notion exports
- customer/contact records
- personal daily notes
- generated logs
- staged write payloads
- local vault content

Runtime folders exist only as placeholders:

- `.context/`
- `logs/`
- `state/`
- `vault/`

You fill these locally when you run the system.

---

## 5. System architecture

```text
Hermes Agent
  |
  | loads repo context from AGENTS.md / CLAUDE.md
  | uses skills in .claude/skills/
  v
COO Twin skills
  |
  | call scripts for deterministic parsing/validation
  v
Local repo runtime
  |
  |-- config/        source definitions and streams
  |-- state/         local operating mode and small runtime state
  |-- .context/      staged/applied write payloads
  |-- logs/          local telemetry and daily logs
  |-- vault/         local Markdown notes
  v
External systems, approval-gated
  |
  |-- Notion         tasks, CRM/contact records, activity log, meeting notes
  |-- Google         Calendar and Tasks
  |-- Telegram/etc.  optional Hermes gateway delivery
```

Core principle: Hermes reads broadly, proposes clearly, and writes only after approval.

---

## 6. Required accounts and tools

Minimum useful setup:

- macOS, Linux, or WSL.
- Python 3.10+.
- Git.
- Hermes Agent installed and configured with an LLM provider.
- A Notion workspace if you want Notion-backed tasks/CRM/activity logs.
- Google account if you want Calendar/Tasks integration.
- A Markdown editor or Obsidian if you want the local vault workflow.

Recommended:

- Python 3.11 or 3.12.
- `pyyaml` Python package.
- Telegram gateway for mobile field use.
- GitHub CLI `gh` if you maintain your fork on GitHub.

---

## 7. A-to-Z local setup

### Step 1 — install Hermes Agent

Follow the official docs if these commands change:

```bash
curl -fsSL https://hermes-agent.nousresearch.com/install.sh | bash
hermes setup
hermes doctor
```

Pick your model/provider during `hermes setup` or later with:

```bash
hermes model
```

Useful Hermes docs:

- Main docs: https://hermes-agent.nousresearch.com/docs
- Configuration: https://hermes-agent.nousresearch.com/docs/user-guide/configuration
- Messaging gateway: https://hermes-agent.nousresearch.com/docs/user-guide/messaging/
- Skills: https://hermes-agent.nousresearch.com/docs/reference/skills-catalog

### Step 2 — clone this repo

```bash
git clone https://github.com/YOUR_ORG/daily-automation.git
cd daily-automation
```

If you are testing this template from a fork, replace the URL with your fork.

### Step 3 — install Python dependency

```bash
python3 -m pip install pyyaml
```

The repo intentionally keeps dependencies light. Most scripts use the Python standard library.

### Step 4 — create local runtime folders

```bash
mkdir -p .secrets .context/preview .context/applied logs state vault/inbox vault/daily vault/meetings vault/notes
chmod 700 .secrets
```

### Step 5 — create local mode file

```bash
cp examples/coo_mode.yaml state/coo_mode.yaml
```

Default mode is `draft`, which means Hermes can prepare proposed writes but should ask before executing them.

### Step 6 — create local env file

```bash
cp .env.example .env
```

Then edit `.env` locally. Do not commit it.

At minimum, you may need:

```bash
NOTION_API_TOKEN=
TELEGRAM_BOT_TOKEN=
TELEGRAM_CHAT_ID=
```

Do not paste real keys into chat transcripts or commit history. Put them in `.env`, `.secrets/*.env`, your shell environment, or your Hermes config.

### Step 7 — copy local agent settings example

```bash
cp .claude/settings.local.json.example .claude/settings.local.json
```

Then fill only local values. This file is ignored and should not be committed.

### Step 8 — run validation

```bash
python -m unittest discover -s tests
bash scripts/skill_lint.sh
python scripts/streams_check.py
bash scripts/test_phi_gate.sh
```

Expected result:

- unit tests pass
- skill lint reports 0 failures
- streams check reports consistency
- sensitive-input gate test passes

---

## 8. Configure Hermes Agent

Hermes can use this repository in two complementary ways.

### Option A — run Hermes from the repo

This is the simplest path.

```bash
cd daily-automation
hermes
```

When Hermes runs from this directory, the project files (`AGENTS.md`, `CLAUDE.md`, config, scripts, and skills) are available as working context.

Start by asking:

```text
Use the setup skill and help me configure this COO Twin for my business.
```

### Option B — install/copy skills into Hermes

Hermes skills normally live under your Hermes home, often:

```text
~/.hermes/skills/
```

You can copy this repo's skills into a local skill category:

```bash
mkdir -p ~/.hermes/skills/coo-twin
cp -R .claude/skills/* ~/.hermes/skills/coo-twin/
```

Then reload or restart Hermes:

```text
/reload-skills
```

or start a new session.

You can also explicitly run Hermes with a skill loaded:

```bash
hermes -s start-day
```

If your Hermes installation expects a different skill layout, use the official Hermes skill docs and adapt the copy path.

### Recommended Hermes toolsets

For this repo, enable at least:

- file tools
- terminal tools
- skills
- memory, optional but useful
- cronjob, if you want scheduled automations
- web, optional for research/doc lookup

Use:

```bash
hermes tools
```

or:

```bash
hermes tools list
```

---

## 9. Configure this repo

### Configure streams

Edit:

```text
config/streams.yaml
```

Streams are the departments, businesses, teams, or focus areas your COO Twin routes work into.

Example:

```yaml
streams:
  - key: operations
    display_name: "Operations"
    is_default: false
    workspace_values: ["Operations"]
    keywords: ["ops", "operations", "admin", "finance"]

  - key: sales
    display_name: "Sales"
    is_default: false
    workspace_values: ["Sales"]
    keywords: ["sales", "lead", "pipeline", "customer", "account"]

  - key: other
    display_name: "Other"
    is_default: true
    workspace_values: ["Other"]
    keywords: []
```

Rules:

- Each stream needs a stable `key`.
- Exactly one stream should have `is_default: true`.
- `workspace_values` should match your Notion select options.
- `keywords` help route calendar events and notes.

After editing, run:

```bash
python scripts/streams_check.py
```

### Configure sources

Edit:

```text
config/sources.yaml
```

This file tells the system where to find:

- the local vault
- Notion databases and data sources
- Notion field names
- Google Tasks settings
- routing keywords
- follow-up thresholds

Use placeholders first, then replace with real IDs after your Notion workspace is ready.

---

## 10. Configure Notion

This template expects four canonical Notion databases.

### 1. Master Tasks

Purpose: system of record for work.

Recommended fields:

- `Task` — title
- `Status` — status
- `Due` — date
- `Workspace` — select matching `config/streams.yaml`
- `Assignee` — people
- `Last Activity` — date or text, optional
- `Updated` — date, optional

### 2. Contact CRM

Purpose: people, accounts, customers, vendors, and important external relationships.

Recommended fields:

- title field for contact/account name
- `Stage` — select
- `Last Contact` — date
- `Next Step` — text
- `Workspace` — select

### 3. Activity Log

Purpose: decisions, calls, emails, site visits, and notable updates.

Recommended fields:

- title field for entry
- `Type` — select
- `Date` — date
- `Workspace` — select
- `Outcome` — text
- `Next Action` — text

### 4. Meeting Notes

Purpose: meeting summaries and links back to tasks.

Recommended fields:

- `Meeting name` — title
- `Date` — date
- `Summary` — rich text
- `Attendees` — people/text
- `Workspace` — select
- `Related Tasks` — relation to Master Tasks, optional

### Use the included templates

Templates live in:

```text
templates/notion/
```

You can use them as a schema reference or with the `notion-template-install` skill.

Suggested flow:

1. Create a Notion integration.
2. Give the integration access to your workspace/page.
3. Create the four databases manually or via the template-install skill.
4. Copy database IDs and data source IDs into `config/sources.yaml`.
5. Confirm the field names match exactly.
6. Run a read-only probe:

```text
Use the notion-probe skill to inspect my Notion workspace and tell me what IDs/fields to put in config/sources.yaml. Do not write anything.
```

### Notion API token

Create a Notion internal integration and set the token locally:

```bash
export NOTION_API_TOKEN="your-token"
```

or put it in `.env` / `.secrets/notion.env` / `.claude/settings.local.json`.

Do not commit it.

---

## 11. Configure Google Calendar and Tasks

This repo can use Google Calendar and Google Tasks as execution surfaces.

Typical setup paths:

- Use your existing Hermes Google tooling, if configured.
- Use a local Google CLI/OAuth workflow.
- Use the scripts in this repo as adapters if you extend them.

The public template intentionally does not include OAuth credentials.

Common local files that must stay ignored:

- `client_secret_*.json`
- OAuth token caches
- Google credential JSON files

If your workflow uses Google Tasks/Calendar through a CLI, authenticate that CLI locally and verify it can read today's agenda/tasks before asking Hermes to use it.

---

## 12. Configure the local vault

The vault is a local Markdown knowledge base. It can be opened with Obsidian, VS Code, or any Markdown editor.

Default layout:

```text
vault/
  inbox/      quick captures
  daily/      daily notes
  meetings/   meeting notes
  notes/      durable notes and references
```

Create the folders:

```bash
mkdir -p vault/inbox vault/daily vault/meetings vault/notes
```

The repo tracks only `.gitkeep` placeholders. Your real notes should remain local/private unless you deliberately decide otherwise.

---

## 13. Run validation

Before using the system seriously, run:

```bash
python -m unittest discover -s tests
bash scripts/skill_lint.sh
python scripts/streams_check.py
bash scripts/test_phi_gate.sh
```

Before publishing or sharing your fork, also run:

```bash
git status --short
git grep -n -i -E 'token|secret|password|client_secret|refresh_token|access_token|private key' -- . ':!.env.example'
git grep -n -i -E 'customer name|private account|internal codename|personal email' -- .
```

Replace the second grep with terms relevant to your own private data.

---

## 14. Use the COO skills

You can invoke skills conversationally from Hermes. Examples:

### Setup

```text
Use the setup skill. Interview me and help configure streams.yaml and sources.yaml for my business.
```

### Morning plan

```text
Run start-day in read-only mode and produce my morning COO brief.
```

### Meeting prep

```text
Use meeting-prep for my next meeting. If calendar access is unavailable, ask me for the meeting title and attendees.
```

### Capture meeting notes

```text
Use capture-meeting on these notes. Show me the proposed task/activity/vault routing before writing anything.
```

### End of day

```text
Run end-day. Compare today's plan against what moved and propose carry-forward items.
```

### Calendar refinement

```text
Use refine-calendar to convert today's top outputs into proposed calendar blocks. Do not write to my calendar until I approve.
```

### Vault health

```text
Use vault-health to audit my local Markdown vault. Read-only first.
```

### Automation

```text
Use automation to show which saved automations are due. Do not execute writes without approval.
```

---

## 15. Daily operating rhythm

A simple operating cadence:

### Morning, 5-10 minutes

```text
/start-day
```

or:

```text
Run start-day for today. Give me the top 3 outputs and execution plan.
```

Then pick what you actually intend to do.

### Before meetings, 1-3 minutes

```text
Use meeting-prep for my next meeting.
```

### After meetings, 2-5 minutes

Paste rough notes:

```text
Use capture-meeting. Split these notes into tasks, decisions, follow-ups, and knowledge. Show the trust gate before writing.
```

### End of day, 5-10 minutes

```text
Run end-day. What moved, what did not, and what should carry forward?
```

### Weekly

Ask Hermes to review patterns:

```text
Review this week's daily notes, completed outputs, and stuck items. Propose next week's operating focus.
```

---

## 16. Safety model and approval gates

This repo is intentionally conservative.

### Operating modes

Configured in:

```text
state/coo_mode.yaml
```

Common modes:

- `observe` — read-only.
- `draft` — default; propose writes and ask for approval.
- `approved` — auto-approve only specific action prefixes.
- `auto` — more autonomous; use carefully.
- `locked` — emergency stop; skills should refuse.

### Trust gate

Any external write should be shown before execution:

- Notion creates/updates
- Google Calendar events
- Google Tasks updates
- vault writes
- outbound messages/emails
- destructive file changes

The operator should see:

1. what will be written
2. where it will be written
3. why it is being written
4. how to approve or decline

### Sensitive-input gate

`scripts/phi_scan.sh` catches obvious sensitive markers before raw notes are parsed. It is not a compliance system, but it prevents the most obvious mistakes.

Run its test:

```bash
bash scripts/test_phi_gate.sh
```

---

## 17. File and folder reference

```text
.claude/skills/                  Skill definitions
.claude/agents/                  Supporting subagent prompts
.claude/settings.local.json.example
                                 Local settings template; copy to ignored file
AGENTS.md                        Agent operating guide for Hermes/Codex-style agents
CLAUDE.md                        Parallel operating guide for Claude-style agents
config/calendar.yaml             Calendar block planning settings
config/routing-rules.yaml         Meeting-note routing indicators
config/sources.yaml               Source IDs and schema mapping
config/streams.yaml               Business streams / routing keywords
docs/                            Setup and architecture notes
examples/coo_mode.yaml            Safe starting mode config
scripts/                         Helper scripts and validation tools
templates/notion/                Notion database templates
state/                           Local runtime state; mostly ignored
logs/                            Local logs; ignored except placeholder
.context/                        Staged/applied write payloads; ignored except placeholders
vault/                           Local Markdown vault; ignored except placeholders
tests/                           Unit tests
```

---

## 18. Customizing for your business

Start with these edits:

1. Rename streams in `config/streams.yaml`.
2. Match Notion `Workspace` select values to those streams.
3. Update `calendar_business_keywords` in `config/sources.yaml`.
4. Update `config/routing-rules.yaml` if your meeting notes use different language.
5. Add your team members to `team_members` in `config/sources.yaml` if useful.
6. Adjust thresholds such as `staleness_days` and `contact_followup_days`.
7. Run validation.
8. Run `start-day` in read-only mode and inspect the output.
9. Only then allow write workflows.

Good stream examples:

```yaml
streams:
  - key: client-success
    display_name: "Client Success"
    workspace_values: ["Client Success"]
    keywords: ["renewal", "implementation", "support", "customer"]

  - key: sales
    display_name: "Sales"
    workspace_values: ["Sales"]
    keywords: ["lead", "proposal", "pipeline", "demo"]

  - key: product
    display_name: "Product"
    workspace_values: ["Product"]
    keywords: ["roadmap", "bug", "release", "engineering"]
```

Keep stream keys stable. It is fine to rename display names, but changing keys after you have data may break routing assumptions.

---

## 19. Public/private hygiene checklist

Before pushing your own version publicly:

```bash
git status --short
python -m unittest discover -s tests
bash scripts/skill_lint.sh
python scripts/streams_check.py
bash scripts/test_phi_gate.sh
```

Then scan for secrets and private terms:

```bash
git grep -n -i -E 'token|secret|password|client_secret|refresh_token|access_token|private key' -- . ':!.env.example'
```

Also scan for your own private names:

```bash
git grep -n -i -E 'your-company|your-client|your-private-codename|your-email@example.com' -- .
```

Make sure these are not tracked:

```bash
git ls-files .env .secrets logs state/tmp vault .context
```

If you accidentally committed secrets, do not just delete the file in a new commit. Rotate the secret and rewrite history or create a fresh sanitized repository.

---

## 20. Troubleshooting

### Hermes does not see the skills

Try one of these:

```bash
cd daily-automation
hermes
```

or copy skills into Hermes:

```bash
mkdir -p ~/.hermes/skills/coo-twin
cp -R .claude/skills/* ~/.hermes/skills/coo-twin/
```

Then restart Hermes or run:

```text
/reload-skills
```

### Notion reads fail

Check:

- `NOTION_API_TOKEN` is set locally.
- The Notion integration has access to the relevant pages/databases.
- IDs in `config/sources.yaml` are correct.
- Field names match exactly.

Run the Notion probe skill in read-only mode.

### Google Calendar/Tasks fail

Check:

- Your Google auth flow is complete.
- OAuth token files exist locally and are not committed.
- The CLI or adapter you use can read today's calendar/tasks outside Hermes.

### Skill lint fails

Run:

```bash
bash scripts/skill_lint.sh
```

Read the failure line. First-party COO skills need:

- `coo_twin:` frontmatter
- Step 0 mode/preflight language
- telemetry language
- trust-gate language if they write externally
- sensitive-input gate language if they process sensitive raw notes

### Streams check fails

Run:

```bash
python scripts/streams_check.py
```

Usually this means `config/streams.yaml` and `config/sources.yaml` disagree about workspace values or stream keys.

### The agent wants to write too much

Set mode to observe:

```yaml
mode: observe
```

in:

```text
state/coo_mode.yaml
```

Then restart or rerun the skill.

### You want mobile delivery

Configure the Hermes gateway:

```bash
hermes gateway setup
hermes gateway run
```

For persistent service mode, see the Hermes gateway docs.

---

## Maintainer notes

This repository is designed to be forked and personalized. Keep your private runtime data out of git, keep write actions approval-gated, and treat the Markdown skills as the operating manual for your AI COO.

When improving the system:

1. Update the relevant skill.
2. Update scripts/tests if behavior changed.
3. Run validation.
4. Keep examples generic.
5. Do not commit real business data or secrets.

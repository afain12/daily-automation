# VPS Ops-Agent Launch — Audit & Plan

**Compiled:** 2026-05-18
**Author:** Claude (strategic-overview pass)
**Sources:** `Ops-Agent-Master-Doc.md` (in-house design), `manus_suggestions_v_2_ops_agent_cleaned.md` (external review), and a survey of `C:\Users\aaron\daily-automation` as of today.

---

## 0. TL;DR

- **Pick Hermes Agent over OpenClaw.** Both source documents agree, and the 2026 security record (OpenClaw RCE + ClawHub malicious-skill saturation) makes it not a close call.
- **The two documents do not contradict each other.** The Master Doc is the architecture. The Manus revision is a safety/hygiene patch applied on top of it. Treat them as one combined spec.
- **The existing `daily-automation` repo is ~30% of the ops agent already.** Notion-via-curl, the `gws` Calendar/Tasks integration, the workspace routing logic, the carry-forward `priorities.yaml`, and the `start-day` / `end-day` / `capture-meeting` skills are real assets — not throwaway prototypes. The Hermes build should inherit from them, not start fresh.
- **The biggest gaps are operational, not architectural.** No always-on runtime, no Telegram surface in production, no structured audit log, no operating modes, no dispatch Gmail, no idempotency rails, no secret-rotation pattern.
- **Use the weekend runbook (§12 of the Master Doc) almost verbatim**, but fold in the Manus modes/whitelisting/idempotency before Phase 1 ends — not after.
- **Runtime decision (2026-05-18): VPS skipped. Go straight to a base-model Mac mini M4 ($599).** Since the Mac mini was always planned for Day 36–60, going direct removes the VPS rehearsal cost and the entire migration phase. Cheaper and simpler over any horizon beyond ~2 months. Full value equation in Appendix B.

---

## 1. Goal (G)

Stand up a single, always-on personal ops agent that:

1. Is reachable from a phone while Aaron is between offices, on a call, or in a parking lot.
2. Executes a small library of trusted "hands" tasks (supply orders, courier requests, IT tickets, follow-ups) via a contained outbound channel.
3. Does the Sunday-evening "plan my week" synthesis using Notion + Calendar + the existing carry-forward state, and proposes blocks on a separate overlay calendar Aaron can drag-confirm.
4. Logs every action to a structured audit trail that is both human-readable and queryable.
5. Holds a HIPAA line: no PHI in the agent surface, accession-number boundary, dispatch mailbox is outbound-only.

This is a **leverage system**, not an automation maximalist project. The success criterion is "Aaron stops drafting 80% of dispatch emails and stops manually building the week" — not "the agent runs unattended for a month."

---

## 2. Current State Audit — What's Actually in the Repo

Verified by walking `C:\Users\aaron\daily-automation` today. The Master Doc and Manus revision both write as if the agent will be built from scratch. That's not quite right. Here's what already exists.

### 2.1 Skills (`.claude/skills/` — ~15 first-party skills, more than first reported)

**Correction (2026-05-20):** the initial survey undercounted. There are ~15 first-party skills in `.claude/skills/` (plus ~21 vendored/reference skills in `.agents/skills/`). The core daily-loop trio below is the most relevant to the ops agent, but the workspace-setup and governance skills (`notion-probe`, `notion-map`, `notion-template-install`, `setup`, `automation`, `vault-health`, `meeting-prep`, `sync-sweep`) and the experimental parallel-fanout variants (`start-day-team`, `end-day-team`, `capture-meeting-team`) all exist and are real.

| Skill | Status | What it does | Relevance to the ops agent |
|---|---|---|---|
| `/start-day` | Active | Morning briefing: Notion overdue + stale scan, Calendar today, Tasks list, vault inbox surfacing, `.context/` pending-writes check, daily note generation. | Direct ancestor of "morning brief" and parts of "weekly planning." |
| `/end-day` | Active | EOD retro: planned vs actual, carry-forwards to `priorities.yaml`, completed task scan. | Direct ancestor of the "decision follow-through" and Sunday digest workflows. |
| `/capture-meeting` | Active | Meeting-note routing: action items → Notion, insights → Obsidian, follow-ups → Calendar, decisions → Activity Log. Handles Granola's two-pattern routing. Has a PHI input gate (`phi_scan.sh`). | Direct ancestor of `post-visit-recap.md`. |
| `/meeting-prep` | Active | Pre-meeting context dossier: attendees → CRM/Activity Log/Meeting Notes/vault. Read-only. | **This is essentially `pre-meeting-brief.md` already built.** |
| `/automation` | Active | Cron-style saved prompts; reads `state/automations.yaml`. Weekly-review + provider-followup-nudge run through it. | Direct ancestor of the Hermes cron layer. |
| `/vault-health` | Active | Read-only vault audit: orphans, broken wikilinks, untagged notes, stale inbox. Trust-gated batch fixes. | Maintenance skill; ports as-is. |
| `notion-probe` / `notion-map` / `notion-template-install` / `setup` | Active | Onboarding/genericization layer: scan a Notion workspace, map property roles, install canonical DBs, run the setup questionnaire. | Makes the whole system re-deployable to a fresh workspace — useful if the ops agent ever spans more than Aaron's. |
| `/weekly-review` | Superseded | Now an `automations.yaml` entry, invoked via `/automation`. | Direct ancestor of the Sunday-evening `weekly-planning.md` skill. |

### 2.2 Config (`config/`)

- `sources.yaml` — Notion data-source IDs (Master Tasks, Provider CRM, Activity Log, Meeting Notes), Obsidian vault paths, Calendar business-keyword tagging (lab / ipa / nestmate / dock_pro), staleness thresholds.
- `routing-rules.yaml` — Where meeting-note pieces go (Notion / Obsidian / Calendar / Activity Log / Provider CRM).

### 2.3 State (`state/`, `.context/`)

- `state/priorities.yaml` — 100+ carry-forward items across four workspaces, with `days_carried`, original due dates, blocking dependencies. This is the operational memory the ops agent will inherit.
- `state/coo_mode.yaml` — **system-wide operating mode** (`observe | draft | approved | auto | locked`). The Manus review's "add operating modes" recommendation is **already implemented here**, framework-neutrally. Read by `scripts/check_mode.sh` at every skill's Step 0.
- `state/profile.yaml` — Aaron-specific profile: businesses, ambiguous persons, operating gates, preferences. The seed of `weekly-planning.md`'s personalization.
- `state/automations.yaml` — saved prompts + cadence + delivery channel; consumed by `/automation`. The seed of the Hermes cron config.
- `state/tmp/` — ~120 ephemeral JSON files (Notion query results, Calendar/Tasks dumps). Scratch, not durable.
- `.context/applied/` — 10 archived staged-write payloads (Notion `block-children` PATCH bodies). The lifecycle ("stage → apply → archive") is the existing idempotency pattern; `scripts/action_id.sh` already stamps `{skill}:{target}:{date}:{hash}` action IDs into `.context/applied/`.
- `logs/_telemetry.jsonl` — **append-only structured JSONL telemetry**, one row per skill run, written by `scripts/telemetry.sh`. The Manus review's "add Loguru JSON audit logs" recommendation is **already partially implemented here**.
- `logs/YYYY-MM-DD.md` — 18 daily markdown logs (2026-04-14 → today). Human-readable retrospectives, complementary to the JSONL telemetry.

### 2.4 Settings (`.claude/settings.local.json`)

- `NOTION_API_TOKEN` lives here directly (mirrored from `.secrets/notion.env`). This is the current secret-management story — adequate for one machine, not for VPS + Mac-mini migration.
- `permissions.allow` permits Notion curl, `gws` calendar/tasks/auth, Obsidian file ops, git, Bash for `curl|python3|npm|npx`. Auto-mode environment is described as "trusted infrastructure" for these routine writes.
- No `hooks` defined yet. The CLAUDE.md "Future Enhancements" section already imagines `SessionStart` for vault sync and `PostToolUse` for Notion-write audit lines — these are the right hook targets.

### 2.5 Scripts (`scripts/` — 18 files, the AAC discipline layer is already built)

**Correction (2026-05-20):** the initial survey badly undercounted this directory (reported 3 files; there are 18). The framework-neutral helper suite the Manus review asks for as "net-new" mostly already exists here as plain shell/Python:

- `preflight.sh` — unified Step 0: mode check + NOTION/GWS/VAULT availability.
- `check_mode.sh` — reads `state/coo_mode.yaml` (the operating-mode gate).
- `action_id.sh` — idempotency: generate / check / stamp `{skill}:{target}:{date}:{hash}` action IDs.
- `telemetry.sh` — appends a structured row to `logs/_telemetry.jsonl`.
- `phi_scan.sh` + `test_phi_gate.sh` — PHI input gate (scans for SSN/DOB/MRN before LLM parsing) + its test.
- `skill_lint.sh` — validates SKILL.md frontmatter + AAC discipline.
- `vault_search.py`, `vault_health.py` — BM25-lite vault search + vault audit.
- `automation_due.py` — due-check + last-run stamping for `/automation`.
- `capture_meeting_parse.py`, `notion_probe_score.py`, `notion_field_map.py`, `streams_check.py`, `ingest-vault-to-gbrain.sh` — capture parsing, Notion scan/map scoring, stream validation, gbrain ingest.
- `mve-telegram-receive.ps1`, `mve-telegram-send.ps1`, `README-MVE.md` — Telegram infrastructure scaffolded in PowerShell, not yet wired into a skill. **The one genuine rewrite for macOS** (PowerShell → Python, or delete in favor of Hermes's native Telegram adapter).

**This is the headline correction to the whole audit:** the modes / idempotency / telemetry / PHI-gate disciplines the Manus review treats as gaps are *already implemented* as framework-neutral scripts. They port to Hermes unchanged.

### 2.6 Integrations actually in production

| System | Method | Status |
|---|---|---|
| Notion | `curl` REST API (`/v1/data_sources/{id}/query`, API version `2025-09-03`) with `--max-time 60` | Solid. The `sources.yaml` data-source IDs and field mappings are the contract. |
| Google Calendar | `gws calendar` CLI | Working. Used for agenda + business tagging. |
| Google Tasks | `gws tasks` CLI | Working. Default tasklist ID stored in CLAUDE.md. |
| Obsidian | Direct filesystem read/write to `vault/` and `cp -ru` from OneDrive | Working. Vault is read-mirror for business folders, write-target for `daily/` and `meetings/`. |
| Gmail / Email | **None** | Not present. This is the dispatch gap. |
| Telegram | PowerShell scripts staged | **Wired in form, not in flow.** |

### 2.7 Maturity signals

- 2 git commits total. Project is ~1 month old.
- 18 days of logs. Two weeks of pattern data exists — enough to start `/weekly-review`, almost enough to start `weekly-planning.md`.
- Vault has 50 files across 9 business folders; business sync via `cp -ru` from OneDrive is in CLAUDE.md but not yet a session hook.

**Headline (revised 2026-05-20):** the data plane (Notion / Calendar / Tasks / Obsidian) is connected and reliable, **and the safety/governance plane the Manus review recommends is already built** — operating modes (`coo_mode.yaml`), idempotency (`action_id.sh`), structured telemetry (`_telemetry.jsonl`), and a PHI input gate (`phi_scan.sh`) all exist as framework-neutral scripts. The genuinely unbuilt part is narrower than first stated: the **always-on runtime + Telegram surface + outbound dispatch (Gmail)**. Everything else is re-hosting, not building.

---

## 3. Document Comparison

### 3.1 Where the two docs agree

- **Hermes over OpenClaw.** Identical verdicts.
- **Telegram is the road-facing surface.** Both docs.
- **Notion stays as system of record.** Both docs.
- **Dispatch Gmail is outbound-only, isolated, no PHI.** Both docs.
- **`weekly-planning.md` is the most important file in the library.** Both docs.
- **Tier 1 ventures get disproportionate agent attention.** Both docs.
- **Append-only Notion writes, overlay Calendar writes, draft-approve by default.** Both docs.
- **Skill library is the durable asset; the harness is interchangeable.** Implicit in both.

### 3.2 Where they differ (and what to take from each)

| Topic | Master Doc | Manus revision | What to actually do |
|---|---|---|---|
| **First-weekend scope** | Broad: VPS + Hermes + Notion + Calendar + Dispatch Gmail + first three skills | Narrower: same minus the second/third dispatch skills, plus Loguru + modes + whitelist on day one | **Use Manus's narrower weekend scope.** Modes and audit logs are cheaper to build before there's history than to retrofit. |
| **Audit logs** | Mentions `~/agent-audit/` with daily rotation | Specifies structured JSON via Loguru with a defined record schema | **Take the Manus schema.** It's already a contract; markdown logs are not queryable. |
| **Operating modes** | Implicit "draft-approve by default" | Explicit Mode 0–4 with `LOCK AGENT` Telegram command | **Take the Manus mode system.** Cheap, blunt, exactly the kind of guardrail that turns "I trust this" into "I can prove it's safe." |
| **Idempotency** | Not addressed | Defines `action_id = skill:account:date:hash` with pre-send duplicate check | **Take Manus's pattern.** This prevents the worst dispatch failure (sending a supply order twice). |
| **Accession-number handling** | Treated as the workaround for PHI | Stricter: LLM gets `[ACCESSION_ID]` placeholder, local deterministic code substitutes the real value | **Take Manus's stricter pattern.** It costs nothing and narrows the LLM's surface meaningfully. |
| **Recipient whitelisting** | Mentioned briefly | Defined as a YAML class hierarchy with explicit `blocked` patterns | **Take Manus's pattern.** Same logic as above — cheap, blunt, hard to mess up. |
| **Secrets** | Bitwarden CLI **or** Infisical | Bitwarden first, Infisical on trigger (5+ long-lived secrets across machines) | **Take Manus's phased approach.** Infisical is overkill for one VPS. Inevitable at Mac-mini-migration time. |
| **Schedulers / Telegram libraries** | Implies adding APScheduler, python-telegram-bot | Defers both unless Hermes proves insufficient | **Take Manus's "defer."** Hermes ships cron + Telegram. Don't add second systems. |
| **Tool list** | Long | Short, with explicit "do not install" list | **Take Manus's short list.** Surface area is the enemy in v1. |

**Net read:** the Master Doc is the architecture and rollout sequence; the Manus revision is the production-readiness checklist. They are complements, not alternatives.

### 3.3 What neither doc handles (gaps you should know about)

1. **The existing `daily-automation` repo is not referenced by either doc.** Both write as if `~/lincoln-ops/` is being created from a blank folder. In reality, the Notion data-source IDs, business keywords, carry-forward state, and three production skills are already in `C:\Users\aaron\daily-automation`. The VPS build should inherit these via git, not re-author them.
2. **Workspace vocabulary — resolved 2026-05-18.** The Master Doc used "Lincoln Reference Laboratory / United IPA / Sovereign Phoenix / Specialty Pharmacy" as Tier 1 ventures. Aaron's clarification: **Sovereign Phoenix is a workstream under United IPA** (its successor), and **Specialty Pharmacy is a leg under Nestmate**. Both stay inside the existing 5-value `Workspace` enum (Lincoln Lab / United IPA / Nestmate / Dock Pro / Other) — no new Workspace values needed. But this means the Tier 1 forcing functions live *inside* a Workspace, not alongside it, which forces the design of the Tier layer in #3.
3. **Tier discipline + Workstream layer.** Because Tier 1 priority can vary *within* a Workspace (e.g. United IPA has Sovereign Phoenix as a hot sub-thread, but also has lower-priority IPA-general work), Tier cannot be inferred from Workspace alone. Two new properties are needed on Master Tasks:
   - `Tier` (select: `1` / `2` / `3`) — priority class, set per-task. Tier 1 = high-leverage, irreversible, exclusive-window, or external-deadline-driven. Tier 2 = active but not on a clock. Tier 3 = maintenance / optional.
   - `Workstream` (select, free-text-ish but governed) — the sub-thread inside a Workspace. Examples: `Sovereign Phoenix` (under United IPA), `Specialty Pharmacy onboarding` (under Nestmate), `Telcor pathway` (under Lincoln Lab). Null is fine; not every task has a workstream.

   `config/tiers.yaml` then becomes lightweight — it just documents the meaning of each Tier and lists the active Workstreams, so `weekly-planning.md` can recognize "Sovereign Phoenix" as a Tier-1 hot thread even though it shares its Workspace with lower-priority IPA work.
4. **Platform migration is non-trivial.** Repo lives on Windows (`C:\Users\aaron\...`). VPS is Ubuntu. Mac mini is macOS. The `gws` CLI, `curl`, and `git` are portable; the PowerShell Telegram scripts are not. Plan: rewrite the Telegram bridge in Python during Phase 0 so it runs on all three OSes.
5. **Granola routing.** CLAUDE.md has a careful two-pattern Granola → Notion routing rule (Meeting Notes DB **and** topic-page appends). The Master Doc's `post-visit-recap.md` skill design doesn't account for the topic-page pattern. Carry this rule into the new skill.
6. **No mention of hooks.** CLAUDE.md already imagines `SessionStart`, `PostToolUse`, and `Stop` hooks as future enhancements. These map naturally to the Manus revision's audit-log requirement and should be the implementation path for Loguru integration in Claude Code (the workshop), even though the production audit log on Hermes will be independent.

---

## 4. Strategy (St) — How the Old and New Systems Relate

The right mental model is **two runtimes, one knowledge base:**

```
                  ┌─────────────────────────────────┐
                  │   Notion + Obsidian + gCal      │  ← system of record
                  │   (unchanged)                   │
                  └────────────┬────────────────────┘
                               │
              ┌────────────────┴────────────────┐
              │                                 │
              ▼                                 ▼
┌──────────────────────────────┐   ┌──────────────────────────────┐
│  daily-automation (laptop)   │   │  ops-agent (Mac mini M4)     │
│  Claude Code, manual triggers│   │  Hermes, always-on, Telegram │
│  /start-day  /end-day        │   │  dispatch + weekly-planning  │
│  /capture-meeting            │   │  pre-meeting brief           │
│  /weekly-review (planned)    │   │  + the dispatch library      │
│                              │   │                              │
│  AUTHORS skills (workshop)   │   │  RUNS skills (worker)        │
└──────────────────────────────┘   └──────────────────────────────┘
              │                                 ▲
              └─────────────  git  ──────────────┘
                  (skills + config flow this way)
```

- **The laptop repo becomes the authoring environment.** Aaron writes/edits skills there in Claude Code. Git pushes them to a private repo. The VPS/Mac mini `git pull`s.
- **Notion / Obsidian / Calendar do not move.** They are the shared substrate.
- **The carry-forward state (`priorities.yaml`) eventually moves to Notion** so both runtimes see the same priorities. Until then, the ops agent reads it via git (read-only) and writes its own structured audit log.
- **Two skills become "shared":** `start-day` and `end-day` still run on the laptop for the long-form daily ritual; their VPS counterparts (`morning-brief.md`, `daily-digest.md`) run on Hermes for Telegram-delivered summaries. Different surfaces, same Notion reads.

This matters because it makes the Master Doc's Phase 0 weekend dramatically smaller: you are not re-implementing Notion access; you are giving Hermes the same `sources.yaml` and `curl` patterns the laptop already uses.

---

## 5. Architecture (A) — Recommended Topology

Adopting the Master Doc §6.1 topology with three corrections from the Manus revision and one from the codebase survey:

```
Phone (Telegram) ──Tailscale──┐
Laptop (Claude Code) ─────────┤
                              ▼
                       Mac mini M4 (home closet, on Tailscale)
                       ┌──────────────────────────────────────┐
                       │  Hermes Agent                        │
                       │  ├─ Telegram bot adapter (locked to  │
                       │  │  Aaron's user ID)                 │
                       │  ├─ Skill library (git pull from     │
                       │  │  daily-automation/.claude/skills) │
                       │  ├─ Mode controller (0–4)            │
                       │  ├─ Dispatcher (action_id, whitelist)│
                       │  └─ Loguru JSON audit log            │
                       └──────────────┬───────────────────────┘
                                      │
        ┌──────────────┬───────────────┼────────────────┬──────────────┐
        ▼              ▼               ▼                ▼              ▼
   Notion API   Google Calendar   Dispatch Gmail   Obsidian (git)   Bitwarden
   (existing    (overlay         (outbound-only,  (read-only        CLI
   curl path,   "Agent Proposed" whitelisted)     read of vault     (secrets)
   sources.yaml)calendar)                         from repo)
```

### Corrections from the Manus revision

1. **Mode controller is a first-class component, not an afterthought.** Every skill execution declares a mode; the mode controller is the gate between "skill wants to act" and "skill actually acts."
2. **Dispatcher enforces `action_id` + recipient whitelist** before any outbound action, on every skill, regardless of mode.
3. **Loguru audit log is the source of truth for "what did the agent do today,"** not the markdown daily logs. Markdown logs stay on the laptop as the human-readable retrospective; JSON logs on the VPS feed `tokencost` and the weekly cost report.

### Correction from the codebase survey

4. **Notion access via the existing curl pattern, not a Notion MCP.** The repo's `sources.yaml` + `curl --max-time 60` pattern is battle-tested across 18 days of `/start-day` runs. Don't introduce a Notion MCP in Phase 0 just because Hermes supports it; the curl path is the boring, reliable option Manus recommends.

---

## 6. Constraints (C)

| Constraint | Source | Implication for the plan |
|---|---|---|
| Beginner skill level (user preference) | Stated profile | Every Phase 0 step must be either copy-pasteable or have a single clear command. No "configure your Tailscale ACL" without a literal example. |
| HIPAA — Lincoln Lab and Specialty Pharmacy are Covered Entities | Master Doc §5 | v1 cannot touch any mailbox containing PHI. Accession-number boundary is the workaround. Compliance attorney is a Phase 4 gate before any v2 PHI work. |
| Single operator, no team | Master Doc §1 | Tier discipline matters more than throughput. Headroom from the agent goes to Tier 1 ventures, not new ventures. |
| Modest LLM budget cap | Master Doc §11 | $200/mo ceiling. `tokencost` is not optional — it goes in during Phase 1. |
| Telegram restricted to Aaron's user ID | Both docs | Phase 0 deliverable: bot accepts no other senders. |
| Existing repo lives on Windows | Codebase survey | Telegram bridge must be rewritten in Python. PowerShell scripts become reference, not runtime. |
| Notion writes are append-only in v1 | Both docs | Every agent-created row carries `🤖` tag. Bulk-revertable. |
| Calendar writes go to "Agent Proposed" overlay only | Both docs | Aaron drags to confirm. Primary calendar is never auto-modified. |
| No `.env` in production | Both docs | Bitwarden CLI on VPS in Phase 0; Infisical only when secret count crosses ~5 across machines. |

---

## 7. Hermes vs OpenClaw — Recommendation

**Pick Hermes Agent. Not close.**

### Why Hermes wins on the merits

| Dimension | Hermes | OpenClaw |
|---|---|---|
| **License** | MIT, free | Open-source but tarnished |
| **Telegram support** | First-class, in-box | First-class, in-box |
| **Skills format** | `.md` files in git — matches Aaron's existing pattern | `.md` files but registry-pulled by default |
| **VPS deployment** | $5–10/mo VPS sufficient for personal use | Same |
| **Scheduling** | Built-in cron with delivery to messaging platforms | Requires separate scheduler in many setups |
| **Memory** | Three-layer memory + learning loop (auto-creates skills from experience) | Skill marketplace, no first-class learning loop |
| **Default posture** | Conservative: pre-execution command scanning, container hardening, read-only root, rollback checkpoints | Permissive; many instances run without auth |
| **Security record (2026)** | Clean as of the May 2026 survey | **CVE-2026-25253** (CVSS 8.8) one-click RCE patched in v2026.1.29; **341+ malicious skills** found in ClawHub (rising to 800+ by April 2026, ~20% of registry); **30,000+ internet-exposed instances** identified; ClawHavoc campaign delivered Atomic macOS Stealer to victims who installed disguised skills |
| **Subscription** | BYOK (Anthropic or OpenAI API account) | BYOK |
| **Community size** | 95.6K stars in 7 weeks (fastest-growing 2026 framework) | Larger marketplace, smaller signal-to-noise ratio |

### Why this is not just "Hermes is the new shiny"

The security record matters disproportionately for Aaron's use case. The ops agent:

- Sits on a VPS with credentials for Notion, Calendar, and Gmail.
- Can send outbound email under Aaron's identity to providers and payers.
- Operates adjacent to Covered Entities (even though PHI never enters its surface).

An RCE on the harness, or a single malicious skill from a community registry, would mean a credential theft incident with downstream exposure on accounts that touch healthcare entities. The 2026 OpenClaw record proves this is not hypothetical: the ClawHavoc campaign already used social engineering through ClawHub to push macOS info-stealers to operators who installed skills the way Aaron will be installing them.

Hermes's "conservative defaults + pre-execution scanning + skill-library-from-git-not-marketplace" posture is the right fit. The Master Doc's verdict was correct in March; the security data published since has only made it less close.

### What would change the recommendation

If Hermes becomes unmaintained, has a comparable CVE event, or fails on a specific Telegram or Notion integration we need, revisit. None of those are true today.

---

## 8. Audit Table — Recommendations vs Reality

Every meaningful recommendation in both docs, mapped against the actual repo. Status legend: ✅ already built · 🟡 partially built · ❌ gap · ⚠️ contradicts current design.

| # | Recommendation | Source | Status | Where in repo / what's missing |
|---|---|---|---|---|
| 1 | Hermes as runtime | Both | ❌ | Not installed anywhere. Phase 0. |
| 2 | Telegram as primary surface | Both | 🟡 | `scripts/mve-telegram-*.ps1` exist but are not wired into any skill. Rewrite in Python; bind to Hermes Telegram adapter in Phase 0. |
| 3 | Notion as system of record | Both | ✅ | `config/sources.yaml` + curl integration is production-grade. Reuse as-is. |
| 4 | Google Calendar for read + overlay write | Both | 🟡 | `gws calendar` read is working. Overlay calendar "Agent Proposed" does not exist yet — create in Phase 2. |
| 5 | Dispatch Gmail, outbound-only | Both | ❌ | No Gmail integration of any kind. Create dedicated account in Phase 0. |
| 6 | Skills as `.md` files in git | Master | ✅ | Pattern is already established: `.claude/skills/{name}/skill.md`. |
| 7 | `weekly-planning.md` | Both | 🟡 | `/start-day` and the planned `/weekly-review` do partial work. The Sunday-evening cross-venture planner is unbuilt. |
| 8 | `supplies-order.md`, `courier-pickup-request.md`, `it-ticket-by-accession.md` | Both | ❌ | None of the dispatch skills exist. These are net-new. |
| 9 | `pre-meeting-brief.md` | Master | 🟡 | `/start-day` reads tomorrow's events but does not produce a Tier-1-event-specific brief 30 min before. |
| 10 | `provider-not-touched-in-N-days.md` | Both | 🟡 | Provider CRM data-source ID is in `sources.yaml`. The "not touched in N days" query is unwritten. |
| 11 | `post-visit-recap.md` | Both | 🟡 | `/capture-meeting` does this for laptop sessions. Telegram-driven recap doesn't exist. Carry the Granola two-pattern routing rule forward. |
| 12 | Append-only Notion writes with `🤖` tag | Both | 🟡 | Writes happen via `.context/*.json` → PATCH lifecycle, with applied-archive in `.context/applied/`. The lifecycle is the right shape; the `🤖` tag is not consistently applied. |
| 13 | Bulk-revertable action IDs | Manus | ✅ | **Already built.** `scripts/action_id.sh` generates/checks/stamps `{skill}:{target}:{date}:{hash}` into `.context/applied/`. Port unchanged; extend to dispatch. |
| 14 | Operating modes 0–4 | Manus | ✅ | **Already built.** `state/coo_mode.yaml` defines `observe/draft/approved/auto/locked` (5 modes); `check_mode.sh` enforces at Step 0. Maps onto Manus's Mode 0–4 with minor renaming. |
| 15 | `LOCK AGENT` Telegram emergency stop | Manus | 🟡 | The `locked` mode exists in `coo_mode.yaml`; the Telegram *command* to flip into it is net-new (Phase 0). CLAUDE.md already names "Telegram LOCK AGENT / UNLOCK AGENT" as the intended trigger. |
| 16 | Recipient whitelisting | Manus | ❌ | No email at all yet. Whitelist YAML lands when dispatch Gmail does. |
| 17 | Accession-number placeholder + local-substitution + PHI gate | Manus | 🟡 | `scripts/phi_scan.sh` (SSN/DOB/MRN input gate) **already exists** and runs in `/capture-meeting`. The placeholder/local-substitution rendering pattern is net-new (Phase 1). |
| 18 | Loguru JSON audit logs | Manus | 🟡 → ✅ | **Already partially built.** `scripts/telemetry.sh` writes structured `logs/_telemetry.jsonl` (one row per skill run). Markdown logs stay for retrospectives. Extend the JSONL schema to cover dispatch/cost fields. |
| 19 | `tokencost` LLM cost tracking per venture/skill | Manus | ❌ | No cost tracking today. Phase 1. |
| 20 | Bitwarden CLI for secrets | Both | 🟡 | Currently `.secrets/notion.env` + mirrored value in `settings.local.json`. Adequate for one machine; replace with Bitwarden in Phase 0 on the VPS. |
| 21 | Infisical when secrets ≥ 5 across machines | Manus | ❌ | Defer to Phase 3 (Mac-mini migration). |
| 22 | VPS hardening: UFW, fail2ban, key-only auth, Tailscale, FDE | Master | ❌ | No VPS yet. Phase 0. |
| 23 | Tier 1/2/3 venture discipline | Master | 🟡 → ❌ | **Decided 2026-05-18:** add `Tier` (select 1/2/3) + `Workstream` (select) properties to Master Tasks. `config/tiers.yaml` documents Tier meanings + active Workstream list. Not yet implemented. |
| 24 | Workspace vocab includes Specialty Pharmacy + Sovereign Phoenix | Master | ✅ resolved | **Decided 2026-05-18:** Sovereign Phoenix lives under `United IPA` as a Workstream; Specialty Pharmacy lives under `Nestmate` as a Workstream. No new Workspace values. |
| 25 | Mac mini M4 endgame on Tailscale | Master | ❌ | Phase 3 hardware purchase. |
| 26 | Compliance attorney engagement | Master | ❌ | Phase 4. |
| 27 | gbrain memory layer | Master | ⏸ | Deferred in both docs. Don't build. |
| 28 | APScheduler, python-telegram-bot, EZGmail as production deps | Master | ❌ | **Don't add.** Manus's "defer/reject" verdict stands. |
| 29 | Granola two-pattern routing (DB + topic-page append) | CLAUDE.md | ✅ | Already correctly implemented in `/capture-meeting`. Port the same logic when writing `post-visit-recap.md` on Hermes. |
| 30 | `.context/` stage → apply → archive lifecycle | CLAUDE.md | ✅ | Working. Generalize this into the Hermes dispatcher's idempotency check. |

---

## 9. Phased Launch Plan

Built on the Master Doc's four-phase structure, with Manus's safety items pulled forward, and the codebase's existing assets baked in.

### Phase 0 — Mac Mini Build (Days 1–7)

**Goal:** Telegram message from the phone returns a real answer pulled from Notion, plus one drafted (not sent) dispatch email — running on the Mac mini.

**Hardware setup (do this first):**

0. Buy base-model Mac mini M4 (16 GB / 256 GB). Set it up headless or with a spare monitor for first boot. Enable Remote Login (SSH) and screen sharing in System Settings. Put it in the closet with a $40 UPS and a $25 smart plug (for phone-based hard-reboot).

**On the existing laptop / repo:**

1. Add `config/tiers.yaml` documenting Tier 1/2/3 meanings + active Workstream list (Sovereign Phoenix → United IPA, Specialty Pharmacy → Nestmate). Add the `Tier` + `Workstream` properties to Notion Master Tasks (see Open Question #1).
2. Add `config/operating-modes.yaml` defining Modes 0–4.
3. Add `config/recipient-whitelist.yaml` with empty `internal_laboratory`, `known_provider_offices`, `blocked` classes.
4. Rewrite `scripts/mve-telegram-{send,receive}.ps1` as `scripts/telegram_bridge.py` (Python — runs on macOS and Windows).
5. Create private GitHub repo for the ops-agent skill library. Push.

**On the Mac mini:**

6. Install Tailscale on Mac mini, phone, laptop — all on one tailnet. No port forwarding, no static IP needed.
7. Install Homebrew, then Hermes Agent (pin the version — note the pin in `docs/hermes-version.md`).
8. Install Bitwarden CLI. Load Notion token, Telegram bot token, Anthropic API key.
9. Register Telegram bot via BotFather; restrict to Aaron's user ID in Hermes config.
10. `git clone` the ops-agent repo into `~/ops-agent/`.
11. Wire Notion read-only via the existing `curl` pattern (port `sources.yaml`).
12. Wire `gws` Calendar read-only (same CLI as laptop).
13. Set up Loguru JSON audit log writing to `~/agent-audit/YYYY-MM-DD.jsonl`.
14. Configure Hermes to launch on boot (`launchd` plist) so it survives a power-cycle unattended.
15. Implement Mode 1 (Draft Only) as the system default; implement `LOCK AGENT` Telegram command → Mode 4.
16. Implement dispatcher skeleton with recipient whitelist check and `action_id` idempotency check (both no-op pass-through for now since no skills send yet).

**Smoke tests:**

17. Telegram → Hermes: "what's on my calendar tomorrow" → real answer.
18. Telegram → Hermes: "summarize Tier 1 overdue tasks" → real list pulled from Notion.
19. Create Gmail dispatch account (neutral name, not Lincoln-branded); OAuth wire; send-only scope.
20. Telegram → Hermes: "draft a supply order for [test account]" → drafted in `~/ops-agent/drafts/`, logged to Notion Activity Log with `🤖`, audit-log entry written. **No send.**
21. Telegram → "LOCK AGENT" → confirmation message, mode flips to 4, subsequent draft requests refused.
22. Power-cycle the Mac mini from the smart plug; confirm Hermes relaunches and Telegram still answers.

**Exit criteria:** ✅ tests 17–22 all pass. ✅ One real Tier 1 overdue task is surfaced via Telegram that you didn't notice on the laptop today.

### Phase 1 — Dispatch Reliability (Days 8–21)

**Goal:** 5 real dispatch tasks/day flowing through the agent without Aaron drafting.

1. Author `supplies-order.md`, `courier-pickup-request.md`, `it-ticket-by-accession.md` in Claude Code on the laptop, push via git.
2. Implement the accession-number placeholder pattern: LLM emits `[ACCESSION_ID]`; local code substitutes.
3. Integrate `tokencost`; every audit-log entry carries token counts + venture/skill cost.
4. After 14 days of clean drafts in Mode 1, promote `supplies-order.md` and `courier-pickup-request.md` to Mode 2 (Approved Write, single-tap Telegram approval).
5. `it-ticket-by-accession.md` stays in Mode 1 until compliance review.
6. Weekly cost report runs Friday via Hermes cron, posted to Telegram.

**Exit criteria:** ≥ 5 dispatch tasks/day are flowing. Weekly LLM cost is < $50. Zero misdirected emails (whitelist held).

### Phase 2 — Planning Layer (Days 22–35)

**Goal:** Sunday-evening "plan my week" produces a draft week that's better than what you'd build alone in 30 minutes.

1. Author `weekly-planning.md` (longest, most personal file — encode geographic clustering, energy preferences, tier discipline, protected blocks).
2. Author `pre-meeting-brief.md` — fires 30 min before Tier 1 calendar events.
3. Author `provider-not-touched-in-N-days.md` — uses Provider CRM data-source ID and staleness threshold from `sources.yaml`.
4. Create "Agent Proposed" overlay calendar in Google Calendar. Wire Hermes to write to it (and **only** it).
5. First Sunday-evening run from a phone in a car.

**Exit criteria:** You stop manually building the week. Carry-forward items in `priorities.yaml` get auto-surfaced into the proposed week.

### Phase 3 — Library Expansion + Hardening (Days 36–60)

*(No migration phase — the agent is already on the Mac mini from Day 1. This phase is pure consolidation.)*

1. Skill library grows to 15–20 files (post-visit-recap, ar-aging-nudge, rep-activity-report, decision-followthrough, etc.).
2. Consider Infisical for secrets only if Bitwarden CLI handling has become messy (≥ 5 long-lived credentials and friction). Otherwise stay on Bitwarden.
3. Time Machine backup of the Mac mini to an external drive or NAS — the hardware-failure insurance the doc's risk table calls for (skill library is in git, but local audit logs and secrets cache are not).
4. Document the full rebuild path in `docs/runbook.md`: new Mac → Homebrew → Hermes (pinned) → `git pull` → re-auth → restore secrets. Target: < 2 hours to recover from total hardware loss.

**Exit criteria:** Agent runs reliably on owned hardware on Tailscale. A documented, tested recovery path exists.

### Phase 4 — Compliance Gate (Days 60–90)

1. Engage healthcare compliance attorney.
2. Evaluate Anthropic Enterprise BAA vs AWS Bedrock with BAA.
3. If BAA in place: design v2 with PHI-aware Outlook scopes.
4. If not: freeze v1 scope, hold the accession-number boundary, revisit at Day 180.

---

## 10. Open Questions That Block Phase 0

Decide before the weekend or Phase 0 will stall:

1. ~~**Tier mapping.**~~ **Resolved 2026-05-18.** Sovereign Phoenix → Workstream under United IPA. Specialty Pharmacy → Workstream under Nestmate. Workspace enum stays at 5 values. Add `Tier` (1/2/3) and `Workstream` (select) as new properties on Master Tasks. Create `config/tiers.yaml` to document Tier meanings and the canonical Workstream list.
2. ~~**VPS provider + location.**~~ **SUPERSEDED 2026-05-18 — VPS skipped entirely. See decision below.**

   **DECISION: Skip the VPS. Go straight to a base-model Mac mini M4 (16 GB / 256 GB, $599).**

   Rationale: the Master Doc already planned to buy the Mac mini at Day 36–60, so the $599 was always a sunk plan item. Going direct *removes* the VPS rehearsal hosting (~$25–50) and deletes the entire Phase 3 migration (double provisioning, secret migration, Telegram repointing, decommissioning). Over any horizon beyond ~2 months, Mac-mini-direct is cheaper and less work than the VPS path.

   Why base model is sufficient: the Hermes working set is ~500 MB against 16 GB of RAM; audit logs, skill library, and vault mirror are all small against 256 GB. Do not upgrade RAM/SSD now. Revisit 24 GB only if Phase 4 introduces local-LLM inference for PHI-bearing prompts (keeps prompts off external APIs → no BAA needed for those calls).

   Why this is easier (the binding constraint for a beginner): (a) familiar macOS from day one — no Linux-wrestling weekend; (b) Phase 3 migration disappears; (c) no monthly hosting bill; (d) owned hardware = cleaner data-control posture for healthcare-adjacent work; (e) Tailscale erases port-forwarding/static-IP/firewall-CLI entirely.

   Tradeoffs + mitigations:
   - Home internet/power dependency → $40 UPS on Mac mini + router covers brief outages.
   - No DO-app "power cycle from phone" → $25 smart plug (Kasa/Wemo) on the Mac mini gives phone-based hard-reboot from anywhere.
   - Owned hardware failure → skill library is in git; recovery is "new Mac, `git pull`, re-auth" (~2 hrs).
3. **Dispatch Gmail address.** `afain.dispatch@gmail.com` or a more business-y `lincoln.dispatch@gmail.com`? (Recommendation: a neutral name; this is your address, not Lincoln's, for the avoidance of Lincoln-on-the-hook concerns.)
4. **`priorities.yaml` ownership.** Stays on the laptop and gets read-only mirrored to the VPS via git, or moves into Notion as a dedicated DB? (Recommendation: stays in git for Phase 0–1; revisit at Phase 2 once `weekly-planning.md` is writing back to it.)
5. **Skill library repo name.** Same repo as `daily-automation`, or a new `ops-agent-skills` repo? (Recommendation: same repo. The skills are conceptually one library with two runtimes.)
6. **Hermes version to pin.** Latest stable as of the weekend, with a re-pin review every 30 days.

---

## 11. Risks Specific to This Build (vs the Master Doc's general risks)

| Risk | Why it matters here | Mitigation |
|---|---|---|
| **Two-runtime drift.** The laptop's `/start-day` and the VPS's morning brief diverge in logic. | They share Notion reads but live in two repos worth of code. | Single repo, single `config/sources.yaml`. Skills on Hermes import the same YAML the laptop does. |
| **Beginner debugging on a VPS at 11pm.** | Aaron is a beginner; remote Linux debugging is the hardest first-month surface. | Document every command in `docs/runbook.md` with exact copy-paste examples. Keep Claude Code on the laptop as the SSH'd debugging companion. |
| **PowerShell-to-Python rewrite gap.** | The existing Telegram scripts are in PowerShell and not currently used; rewriting them is "easy" but in practice often blocks. | Do this rewrite **first** in Phase 0, before VPS provisioning, on the laptop. Prove the Python bridge works locally with a noop Hermes mock before standing up the VPS. |
| **Carry-forward state collision.** | Both runtimes might try to write to `priorities.yaml`. | Phase 0: VPS is read-only on `priorities.yaml`. Phase 2 decision: who owns writes? |
| **Notion API version drift.** | Repo pins API version `2025-09-03`. Hermes may want to use a Notion MCP that uses a different version. | Don't use a Notion MCP. Use the same `curl --max-time 60` pattern as the laptop. |

---

## 12. What Success Looks Like at Day 90

- Telegram is the daily surface for ~30 dispatch actions/week, ~3 planning conversations/week.
- The laptop is still the workshop for skill authoring and the longer `/start-day` / `/end-day` rituals.
- `priorities.yaml` has fewer items, not more — the agent prevents slippage that used to land there.
- One Tier 1 venture-week has been executed unfairly well (the Master Doc's phrase) because dispatch and planning combined gave back 5+ hours.
- Zero misdirected sends. Zero PHI in the agent surface. Zero credential incidents.
- The skill library is at 15–20 files; the audit log has 90 days of structured records; the weekly LLM bill is < $150.

If any of these are missing, the next conversation is "what specifically broke?" — not "should we rebuild?"

---

## Appendix A — Sources

- **In-repo:** `CLAUDE.md` (project root), `config/sources.yaml`, `config/routing-rules.yaml`, `state/priorities.yaml`, `.claude/skills/{start-day,end-day,capture-meeting}/skill.md`, `scripts/mve-telegram-*.ps1`, `logs/2026-04-14` through `logs/2026-05-18`.
- **Uploaded:** `Ops-Agent-Master-Doc.md`, `manus_suggestions_v_2_ops_agent_cleaned (1).md`.
- **Web (May 2026):**
  - [Hermes Agent — Nous Research](https://github.com/nousresearch/hermes-agent)
  - [Hermes Agent Review: 95.6K Stars, Self-Improving AI Agent (2026)](https://tokenmix.ai/blog/hermes-agent-review-self-improving-open-source-2026)
  - [What is Hermes Agent? Step-by-Step 2026 Deployment Guide](https://www.tencentcloud.com/techpedia/144042)
  - [OpenClaw RCE Vulnerability (CVE-2026-25253)](https://www.proarch.com/blog/threats-vulnerabilities/openclaw-rce-vulnerability-cve-2026-25253)
  - [OpenClaw Security Risks: Skills, Exposure and Exploits](https://blog.cyberdesserts.com/openclaw-malicious-skills-security/)
  - [Investigating Malicious Skills in OpenClaw](https://www.immersivelabs.com/resources/c7-blog/openclaw-hunting-season-is-open)

## Appendix B — Mac Mini Value Equation

**Decision (2026-05-18):** skip the VPS, run Hermes on a base-model Mac mini M4 from Day 1.

### Cost

| Item | Amount |
|---|---|
| Mac mini M4 base (16 GB / 256 GB) | $599 one-time |
| Electricity (~5 W idle, 24/7) | ~$18/yr |
| LLM API (BYOK, realistic ~$100/mo) | ~$1,200/yr |
| Tailscale (personal tier) | $0 |
| UPS + smart plug (one-time) | ~$65 |
| **Year 1 total** | **~$1,882** |
| **Year 2+ ongoing** | **~$1,218/yr** |

### Value (deliberately conservative)

| Measure | Amount |
|---|---|
| Time recovered (Master Doc 4–6 hrs/wk → modeled at 5 hrs/wk) | 250 hrs/yr |
| Valued at $50/hr (rock-bottom admin rate) | $12,500/yr |
| Valued at $150/hr (realistic multi-venture operator rate) | $37,500/yr |
| Year-1 return on all-in cost (@ $50/hr) | ~6.6× |
| Year-1 return on all-in cost (@ $150/hr) | ~20× |
| Hardware payback period | < 3 weeks of recovered time |

### Why Mac-mini-direct beats the VPS path financially

The Master Doc already planned to buy the Mac mini at Day 36–60, so the $599 is not incremental. Going direct *removes* ~$25–50 of VPS rehearsal hosting and deletes the entire Phase 3 migration (provisioning twice, moving secrets, repointing Telegram). Beyond ~2 months, direct is strictly cheaper and less work.

### The value that isn't on the time ledger

The Master Doc's core thesis is that the bottleneck is single-operator *synthesis capacity* — dropped balls, not billable hours. The asymmetric value lives here and dwarfs the time arbitrage:

- A blown **Sovereign Phoenix exclusive window** is irreversible. The weekly "67 days left" surfacing is worth more than the system's lifetime cost if it prevents one miss.
- A **Tier 1 account going cold** from 3+ weeks of no-touch is a revenue event `provider-not-touched-in-N-days.md` exists to prevent.
- A missed **Morshed audit gate / Friday license payment** costs more than the entire stack.

One prevented Tier-1 miss pays for the hardware for its useful life. The $599 is a rounding error against that.

**Caveat:** these returns are conditional on the build actually delivering the projected savings — which depends on skill quality and trust being earned skill-by-skill. The value is not automatic; it is unlocked by execution discipline (§6 Build Philosophy of the Manus revision).

---

## Appendix C — Adoptability of the Existing `daily-automation` Workflow to a Local Agent

**Question:** how readily does the current workflow port to a local agent harness (Hermes, or OpenClaw)?

**Headline:** **Highly adoptable — this repo is unusually well-positioned.** It was effectively built as a harness-agnostic skill library already, even though it currently runs only under Claude Code. The reasons are structural, not lucky.

### C.1 What makes it portable

| Asset | Portability | Why |
|---|---|---|
| **Skills as `SKILL.md` with YAML frontmatter** (`.claude/skills/{start-day,end-day,capture-meeting}`) | ★★★★★ | Both Hermes and OpenClaw use markdown-with-frontmatter skill files. The `coo_twin:` frontmatter block + prose body is exactly the shape these harnesses expect. The harness reads the description to decide when to fire, then follows the body. |
| **Logic lives in `scripts/*.sh` + `*.py`, not in the harness** | ★★★★★ | `preflight.sh`, `action_id.sh`, `telemetry.sh`, `phi_scan.sh`, `vault_search.py`, `automation_due.py` are plain executables. Any harness that can run a shell command runs these unchanged. This is the single biggest portability win — the brain is in scripts the LLM *calls*, not in Claude-specific prompt magic. |
| **Notion via `curl` + `sources.yaml`** | ★★★★★ | No dependency on a Claude-specific Notion MCP. `curl` runs anywhere; the data-source IDs are in a config file. Hermes/OpenClaw call the same endpoint with the same token. |
| **Calendar/Tasks via `gws` CLI** | ★★★★☆ | A standalone CLI binary. Portable to any *nix host (macOS included). One-time `gws auth login` re-auth on the new machine. |
| **State as flat files** (`state/*.yaml`, `.context/*.json`, `logs/`) | ★★★★★ | No database, no Claude-hosted memory. Plain files in the repo. Any harness reads/writes them. |
| **Config-driven routing** (`routing-rules.yaml`, `sources.yaml`) | ★★★★★ | Behavior is data, not code. Re-targeting is editing YAML, not rewriting skills. |
| **Operating-mode discipline** (`coo_mode.yaml`, the AAC five disciplines) | ★★★★★ | The repo *already* implements the modes/idempotency/telemetry/PHI-gate patterns the Manus review wants. These are framework-neutral and map 1:1 onto Hermes. |

### C.2 What needs adaptation (the realistic friction)

| Item | Effort | Notes |
|---|---|---|
| **Skill trigger mechanism** | Low | Claude Code fires skills via the `/start-day` slash-command + description matching. Hermes uses its own skill-selection + cron. Re-expressing "run `/start-day` at 6am" as a Hermes cron entry is config, not code. |
| **`scripts/preflight.sh` mode check** | Low | Each skill's Step 0 calls `eval "$(scripts/preflight.sh)"`. Works as-is on macOS bash; just confirm bash 3.2 vs 5.x quirks (macOS ships old bash — install `bash` via Homebrew or keep scripts POSIX-clean). |
| **PowerShell Telegram scripts** | Medium | `mve-telegram-*.ps1` don't run on macOS. Already flagged for rewrite as `telegram_bridge.py`. On Hermes this may be unnecessary entirely — Hermes ships a native Telegram adapter, so the bridge could be deleted rather than ported. |
| **`.claude/settings.local.json` permissions + hooks** | Medium | The `permissions.allow` allowlist and any hooks are Claude-Code-specific. Hermes has its own permission/tool-gating config. The *intent* (allow curl/gws/git, gate writes) ports; the *file format* does not. Re-express in Hermes config. |
| **Slash-command skills** (`commands/*.md`) | Low | `enforce-voice`, `generate-guidelines` etc. are Claude-Code command files. If needed on Hermes, restate as skills; most aren't part of the ops-agent core anyway. |
| **`gws` re-auth + token storage** | Low | Move from `settings.local.json` env to Bitwarden CLI on the Mac mini. One-time. |

### C.3 Hermes vs OpenClaw for *this specific repo*

- **Hermes:** near-drop-in. The `SKILL.md` + scripts + config + flat-state design is exactly Hermes's model. Estimated port: re-express triggers/permissions in Hermes config, point it at the repo, re-auth tokens. The skills themselves need little-to-no rewriting. **This is the recommended target and the reason Hermes was chosen.**
- **OpenClaw:** also technically adoptable — same markdown-skill + shell-script model — but inherits the security posture problems in §7 (CVE-2026-25253, ClawHub malicious-skill saturation). The repo's own AAC disciplines (modes, idempotency, PHI gate) would partially compensate, but you'd be bolting your safety rails onto a harness with a worse default posture. **Not recommended**, for the same reasons as the main verdict.

### C.4 Bottom line

The reason this ports so cleanly is a design decision already baked into the repo: **the harness is a thin trigger layer; the actual work lives in shell/Python scripts, flat-file state, and YAML config.** CLAUDE.md even says it explicitly — *"The library is the agent. The harness is interchangeable."* That principle is now paying off. Moving to a local Hermes runtime on the Mac mini is mostly a *re-hosting* exercise (auth + triggers + permissions config), not a *re-writing* one. Budget roughly a weekend for the port, most of it spent on auth re-wiring and trigger/cron config rather than touching skill logic.

The one genuine rewrite is the Telegram bridge (PowerShell → Python, or delete it in favor of Hermes's native adapter). Everything else is move-and-re-auth.

---

## Appendix D — First-Boot Checklist (Mac mini Arrival Day)

For tomorrow when the Mac mini lands. Beginner-friendly, in order. Each step has a check-when-done box and the *one* command you need.

### Stage 1 — Hardware on, macOS configured (~20 min)

- [ ] Plug in mini → monitor + keyboard for first boot.
- [ ] First-boot setup wizard. **Skip Apple ID for now if it complicates things** — you can add it later. Local account is fine for a server.
- [ ] **FileVault: turn ON.** Settings → Privacy & Security → FileVault → Turn On. Disk encryption.
- [ ] **Remote Login (SSH): ON.** Settings → General → Sharing → toggle Remote Login. Note the username + computer name shown.
- [ ] **Screen Sharing: ON** (same panel). For headless GUI access when you need it.
- [ ] **Never sleep.** Settings → Lock Screen → set every "turn display off / lock" option to longest, AND Settings → Battery (or Energy) → "Prevent automatic sleeping when the display is off" → ON.
- [ ] **Start up after power failure.** Settings → Energy → "Start up automatically after a power failure" → ON.
- [ ] Plug into UPS. Plug your router into the same UPS. Plug the UPS into the smart plug.
- [ ] Test the smart plug from your phone — make sure it actually power-cycles the mini.

### Stage 2 — Network: Tailscale (~10 min)

- [ ] On the Mac mini, install Tailscale (macOS app from tailscale.com). Sign in with the same identity you'll use on your phone + laptop.
- [ ] On your iPhone, install the Tailscale app. Sign in. Confirm you can see the Mac mini in the device list.
- [ ] From your laptop, `tailscale ping <mac-mini-name>` — confirms the mesh works.
- [ ] **From now on, you can move the mini to the closet** — monitor and keyboard not needed. Everything is over Tailscale.

### Stage 3 — Toolchain (~15 min, in Terminal on the mini, via SSH from your laptop or Screen Sharing)

- [ ] Install Homebrew: `/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"`
- [ ] Install the basics: `brew install git python@3.13 gh` (verified 2026-05-28: Python 3.13 is the safest pick — Hermes minimum is 3.11, latest stable is 3.14.5, 3.13 has ~1.5 yrs of library compatibility. `bitwarden-cli` removed — see Stage 4 secrets-manager decision.)
- [ ] Sign in to GitHub: `gh auth login` (this is how you'll `git clone` the private repo).
- [ ] Sign in to Bitwarden: `bw login` → `bw unlock` → export `BW_SESSION` per the prompt.

### Stage 4 — Repo + secrets (~10 min)

- [ ] `git clone` your `daily-automation` repo into `~/daily-automation/`.
- [ ] Create `~/daily-automation/.secrets/` and pull each secret from Bitwarden into a sourced file:
  - `notion.env` — `NOTION_API_TOKEN` (you already have this value).
  - `telegram.env` — `TELEGRAM_BOT_TOKEN` + `TELEGRAM_CHAT_ID` (same values as on the laptop).
  - `anthropic.env` — `ANTHROPIC_API_KEY` (from console.anthropic.com → API Keys).
- [ ] Install `gws` CLI: follow the same install path you used on Windows, then `gws auth login --scopes calendar,tasks` and step through the OAuth in a browser (Tailscale lets you do this from your laptop's browser pointed at the mini's session — or just run it on the mini once).

### Stage 5 — Hermes (~20 min)

- [ ] Install Hermes per its current docs. **Pin the version.** Write the exact version into `docs/hermes-version.md` so future-you can reproduce.
- [ ] **CRITICAL — model choice.** Configure Hermes to use Anthropic API as the LLM. *Do not* point it at a small local model "to save money" — that's the #1 reason Hermes setups feel broken. Frontier model from day one.
- [ ] Configure the Telegram adapter (token + chat ID from `telegram.env`). Allowlist your numeric user ID.
- [ ] Configure Hermes to launch on boot via `launchd` — create a plist in `~/Library/LaunchAgents/` so the agent comes back up after any reboot.

### Stage 6 — Smoke tests (~15 min)

- [ ] Telegram → "what's on my calendar tomorrow" → real answer.
- [ ] Telegram → "what Tier 1 items are open" → real list from Notion.
- [ ] Telegram → "LOCK AGENT" → confirmation + mode flips to 4. Then "UNLOCK AGENT" → back to draft.
- [ ] **Hard power-cycle test:** pull the plug (or smart-plug it off). Wait 10s. Power back on. Within 2 minutes, Telegram should answer again — confirms launchd + auto-start works.
- [ ] Add a `~/agent-audit/YYYY-MM-DD.jsonl` first row (Loguru), confirm permissions are right.

### Stage 7 — Stop and write the runbook (~10 min)

- [ ] Create `docs/runbook.md` and write down: how to SSH in, how to restart Hermes, where the logs live, where secrets live, and how to recover if the mini dies (new mini → Homebrew → git clone → Bitwarden → relaunch). Future-you will thank present-you.

**If you hit the end of Stage 6 with all green checks, you have a working ops agent.** Phase 1 (the dispatch skills, the first real automation) starts the next weekend.

---

## Appendix E — Cross-Venture Utilization Audit (Grounded in Your Logs)

The brief is: *beyond email drafting templates, where does Hermes create the most leverage given the way your time and effort are actually spread today?* I mined your last 10 daily logs, `priorities.yaml`, `profile.yaml`, `automations.yaml`, `_telemetry.jsonl`, and the routing-evidence notes to ground this in real patterns, not theory.

### E.1 The five patterns the logs revealed

1. **Notion writes lag field outcomes by 4+ days — structurally.** The flag `notion_silence_resumes_5_21` recurs across the week. May 19–21: zero Activity Log entries despite Dr. D'Angelo Practice Fusion go-live, the 5/18 Specialty Pharmacy full-team meeting, and Essen call outcomes. Your braindump prose in the daily note *is* the working memory; Notion is the trailing archive. This is not a discipline failure — it's the natural shape of an in-the-field operator's day.

2. **Top 3 priority slots are noise, not signal — but only after the fact.** The telemetry pattern `top3_scoring_vs_actual_output_mismatch` shows `top3_tracked=0, real=2.5` on multiple days. You consistently produce ~2 real outcomes that *weren't* in the morning Top 3 (D'Angelo go-live + Big Apple no-prescribe on 5/20; SP visit cluster 5/22). The Top 3 underperforms the field day.

3. **Calendar skips cluster after heavy field days.** Goyal skipped 5/20 (first skip in 2 weeks) → Rookwood + Nestmate/DocPro weekly both skipped 5/21. The system flagged this as `calendar_action_skip_pattern_5_21`. Three+ field visits trigger cascading time slips.

4. **Carry-forwards age non-linearly and don't get re-evaluated.** Mechanical rotation. The "get invoice from Richard for GPO + lunch" item is *44 days old*. Rookwood revisit: 37 days. Specialty Pharmacy Notion-page refresh: 22 days. There's no auto-drop, no auto-escalate.

5. **Three of the four active workstream gates have hard, near-term deadlines.** *(See E.3 below — these are urgent.)*

### E.2 Where attention actually lives (last 10 days)

| Venture | Share of Top-3 slots | Carries (5/27) | Real status |
|---|---|---|---|
| **Nestmate** (incl. Specialty Pharmacy) | 39% | ~40 | Over-extended. 6 field visits in 3 days. SP pipeline blocks revenue. |
| **Lincoln Lab** | 31% | ~15 | Active but decision-gated. Telcor close is the gate. |
| **United IPA** (incl. Sovereign Phoenix) | 23% | ~12 | Bottlenecked. 84-day exclusive window. |
| **Dock Pro / CardioPro** | <5% | ~8 | Back-burner until 2026-06-01 (per `profile.yaml`). |
| Other / Personal | rest | ~15 | Mostly stale (Richard invoice 44d, AI textbook 22d). |

You are **over-extended on Nestmate**, **time-boxed on Lincoln**, and **bottlenecked on United IPA**. Dock Pro is correctly dormant. This shape is what Hermes should be optimized for — not a generic "help me across 7 ventures" lens.

### E.3 The forcing functions Hermes should clock on day one

These came out of the log mining and are time-critical:

1. **Thu 2026-05-28 (3–4pm) — Abid + Gary Telcor close meeting.** Gates Friday's Lincoln license payment. The single most consequential meeting of this week.
2. **Thu 2026-05-29 — Patrick credentialing referrals** (Ashley Orenshteyn + Williamsburg Ray's gyns). Hard stop, no extension visible.
3. **Thu 2026-08-14 — Sovereign Phoenix 3-month exclusive deadline.** ~84 days remaining. Three deliverables open: PMPM+shared-savings model, IPA contract comparison, $1.2M loan diligence.
4. **2026-06-01 — Dock Pro back-burner lifts.** Plan ahead so it doesn't blindside the schedule.
5. **Already passed and aging:**
   - Dr. Eng Medicaid extension (deadline 5/23, "+2d" extension applied — now 5/25, still open).
   - Dr. Rybstein green-light (deadline 5/22, "awaiting textback from alex").
   - NYCDOCS check + remaining checks (12–13 days overdue).

These are the items that *must* appear in Hermes's morning brief every day until they resolve. Top 3 should be derived *from* this list, not from a generic priority score.

### E.4 The ten utilities beyond email templates, ranked by leverage for *your* shape of work

| # | Utility | Why it's high leverage for *you specifically* | Build phase |
|---|---|---|---|
| 1 | **Field-outcome → Notion Activity Log bridge** (Telegram capture → Hermes drafts AL entry → you approve once at EOD) | Directly attacks the 4+ day Notion silence pattern. Your single highest-leverage workflow. | Phase 0–1 |
| 2 | **Forcing-function countdown brief** (every morning: "Telcor close in 1 day, SP window 84d, Patrick credentialing in 2 days") | Replaces the noisy Top-3 with the deadlines that actually move money. | Phase 0 |
| 3 | **Stale-carry escalation rule** (anything >14 days carry triggers a "drop or pin a deadline" prompt) | Fixes the 44-day Richard-invoice / 37-day Rookwood / 22-day SP-page pattern. | Phase 1 |
| 4 | **Provider-not-touched-in-N-days** (Dr. Rybstein 8d, Dr. Eng 8d, Dr. Yili Huang 7d, Dr. Remzy Meny 8d) | The dropped-ball insurance you specifically asked about. CRM-driven, no email reading required. | Phase 2 |
| 5 | **Heavy-field-day buffer warning** (when 3+ field visits are scheduled in 2 days, pre-flag the highest-skip-risk one) | Caught by `calendar_action_skip_pattern_5_21`. Hermes can see the pattern forming. | Phase 2 |
| 6 | **Specialty Pharmacy onboarding velocity tracker** (Acousta, Sandra, Hui Tzu Chou, Eleni LIC, Inna Gordin pipeline status) | SP is your largest active workstream and the revenue gate. Tracking it explicitly is more useful than a generic "Nestmate" lump. | Phase 2 |
| 7 | **Pre-call context primer** (when a Tier-1 event is 30 min out, Hermes texts a 5-line dossier: who, last touchpoint, open commitment, Activity Log snippet) | Saves 10–20 min/meeting of context assembly. The `meeting-prep` skill is already partly built. | Phase 2 |
| 8 | **Cross-venture context primer** ("you have Lincoln-Telcor, IPA-panel-loss, and Nestmate-Patrick-credentialing all today — switching cost is high; here's the order") | Unique to your multi-venture shape. Cowork-at-desk doesn't naturally surface this. | Phase 2 |
| 9 | **Decision follow-through sweep** (read DECISION pages monthly; flag commitments that have not moved) | The Telcor and Kader deferrals show how decisions go stale. Hermes can be the conscience. | Phase 2 |
| 10 | **Dispatch templates** (supplies, courier, IT tickets via accession #, AR aging nudges) | The thing the Master Doc emphasized — still valuable, but ranked here because the Notion-bridge above outranks it for *your* observed bottleneck. | Phase 1 |

### E.5 What Hermes's `MEMORY.md` should be seeded with on day one

Pull these directly from the log mining so Hermes doesn't have to rediscover them:

- **Tier 1 ventures and their workstreams:** Lincoln Lab (Telcor pathway, MDland integration, AR collections); United IPA (Sovereign Phoenix consolidation, panel-loss reassurance); Nestmate (Specialty Pharmacy onboarding, Patrick credentialing, GI outreach).
- **Active forcing functions:** the five items in §E.3.
- **Back-burner flag:** Dock Pro / CardioPro demoted until 2026-06-01.
- **Person disambiguation map:** Cyrus (urgent care → nestmate, credentials → ipa, specimen → lab); Ilene (urgent care → nestmate, provider → ipa); Ahmed (context-driven, default ipa); Ryan (dental → nestmate, monitoring → dock_pro); Kader (default lab, **excluded from any SP-acquisition work**).
- **Trust flags:** `kader_untrusted_documented` (May 14) — permanent exclusion from SP routing.
- **Structural facts:** Notion Activity Log writes lag field outcomes by 4+ days; the daily-note braindump is the real working memory; Top-3 mismatches real output by +0.5 to +2.5 consistently.
- **Communication style:** terse, lead with recommendation, surface trade-offs in 1–2 sentences, don't summarize what was just done.

### E.6 What this means for the build sequence

Phase 0 (this weekend, post-mini-arrival) gets the **forcing-function countdown brief** + the **Telegram capture → Notion AL draft** plumbing live. That single combination — knowing the Telcor/Patrick/SP clocks every morning, plus having a friction-free way to dump field outcomes from a car — addresses the two biggest patterns in your logs. Everything else in §E.4 builds on top.

---

## Appendix F — Network Segmentation Plan (Phase 1.5, Deferred)

**Decision 2026-05-27:** the network-hardening work is deferred until *after* Hermes is up on the flat home network. Reason: stacking networking, macOS server admin, Tailscale, Bitwarden, and Hermes onto one weekend is beginner overload. Get the agent working first so the firewall allowlist can be written against real observed traffic, not guessed.

### F.1 Interim baseline (Phase 0–1 on flat network)

What protects you in the meantime, without any new hardware:

- Home router NAT blocks inbound from the internet by default.
- Tailscale-only management — SSH and Screen Sharing bound to the Tailscale interface, not the LAN.
- Bitwarden CLI keeps secrets out of plaintext `.env` files.
- macOS Application Firewall ON (Settings → Network → Firewall → On).
- Anthropic API key has a hard monthly spend cap configured at creation.
- Hermes draft-approve default + `coo_mode.yaml` modes — nothing writes externally without explicit approval.

These five give a defensible posture for v1 work (no PHI in agent scope).

### F.2 Phase 1.5 triggers — when to actually do this

Do the network work when **any** of these is true:

1. **~Day 21 stability checkpoint** — Phase 1 dispatch is reliable and you have ~2 weeks of audit logs to model the allowlist against.
2. **An unexplained pattern in the audit log** that warrants tighter controls.
3. **Compliance-attorney prep for Phase 4** — the conversation goes materially better when "where does the agent run?" answers as "segmented VLAN with allowlisted egress + full firewall logging" instead of "my home network."

### F.3 Recommended path when triggered: existing Protectli + U7-Lite (revised 2026-05-27)

**Updated hardware reality (confirmed 2026-05-27):** Aaron already owns a **Protectli FW4B running OPNsense as the live house router** and a **UniFi U7-Lite AP**. This means Phase 1.5 is a *pure config project* — no purchases, no router swap, no fresh OS install, no whole-house downtime. The earlier UniFi Dream Router recommendation is superseded; the Protectli + U7-Lite combination is the technically stronger architecture and is already in production.

**Estimated Phase 1.5 work:** ~2–3 hours on a single Saturday once you have ~2 weeks of audit logs to model the firewall allowlist against. Specifically: add VLAN definitions in OPNsense → configure one Protectli LAN port as a VLAN trunk → trunk it to the U7-Lite → add three additional SSIDs on the U7-Lite (Infra, IoT, Guest) each tagged to its VLAN → reconnect the mini to the Infra SSID → apply the §F.5 firewall allowlist.

**Topology when Phase 1.5 fires:**
- Protectli FW4B running OPNsense as the router/firewall (LAN + WAN + 2 spare ports).
- One Protectli LAN port configured as a **VLAN trunk** carrying VLAN 10/20/30/99, connected to the U7-Lite.
- U7-Lite broadcasts **multiple SSIDs**, each tagged to its VLAN: "Home" (10), "Infra" (20, the Hermes SSID), "IoT" (30), "Guest" (99).
- Mac mini connects to the "Infra" SSID → lands on VLAN 20 automatically → firewall rules in §F.5 apply.

**Why no managed switch needed (yet):** the U7-Lite is the only downstream device needing VLAN trunking. If you ever add other wired devices that need VLANs, then add a small managed switch (TP-Link TL-SG108E, ~$30) between the Protectli and the U7-Lite.

**Mac mini placement — no Ethernet in the room (decided 2026-05-27):**

The mini will live in a room without a wired drop. Connection options, ranked for an always-on server:

| Option | Cost | Reliability | When to pick |
|---|---|---|---|
| **MoCA adapters** (coax → Ethernet) | ~$80–120/pair | ~95% of wired | If the new room has a coax outlet. Best wired-equivalent option. |
| **Powerline adapters** | ~$50–80/pair | ~80–90% of wired, varies by wiring | If no coax. Works for this low-bandwidth workload. |
| **WiFi to U7-Lite** | $0 | ~90–95% | **Phase 0 default.** Wi-Fi 7 is fast/stable; Hermes workload is text-only. Mini may drop briefly once every few weeks — Tailscale + Hermes reconnect transparently. |
| Run flat Cat6 along baseboards | ~$30 | 99%+ | If aesthetics allow and the run is straightforward. |

**Phase 0 (this weekend):** WiFi to U7-Lite, current flat home network. No segmentation yet.

**Phase 1.5 wireless segmentation:** the U7-Lite broadcasts an "Infra" SSID tagged to VLAN 20. Mini reconnects to that SSID — same firewall rules apply as if it were wired. WiFi doesn't prevent segmentation; the AP handles the VLAN tag at the wireless edge.

### F.4 VLAN scheme

```
VLAN 10 "Trust"   — laptops, phones; full internet + Tailscale; can manage VLAN 20 over Tailscale
VLAN 20 "Infra"   — Mac mini Hermes; allowlisted egress only; no inbound except Tailscale
VLAN 30 "IoT"     — cameras, smart plugs, UPS network port; internet-only, isolated from other VLANs
VLAN 99 "Guest"   — visitors; internet-only, isolated from everything
```

The mini connects via Ethernet to a switch port tagged VLAN 20.

### F.5 Firewall allowlist for VLAN 20 (Hermes)

Default-deny outbound, then allow:

```
ALLOW 443/TCP →
  api.anthropic.com           (Claude API)
  api.telegram.org            (Telegram bot)
  api.notion.com              (Notion)
  *.googleapis.com            (gws calendar/tasks/Gmail)
  accounts.google.com         (OAuth)
  oauth2.googleapis.com       (OAuth)
  github.com, *.github.com    (git pulls)
  *.githubusercontent.com     (release downloads)
  controlplane.tailscale.com  (Tailscale auth)
  login.tailscale.com         (Tailscale auth)
  vault.bitwarden.com         (Bitwarden vault)
  api.bitwarden.com           (Bitwarden API)
  formulae.brew.sh, *.brew.sh (Homebrew updates)
  api.tavily.com OR api.exa.ai (web search, whichever you configure)
  *.apple.com                 (macOS updates — broad but acceptable)

ALLOW 53/UDP → UniFi/OPNsense's resolver only
ALLOW 123/UDP → UniFi/OPNsense's NTP only
ALLOW UDP 41641 + STUN ports → Tailscale NAT traversal
DENY all other outbound (logged)
```

Inbound to the mini: nothing from the internet, ever. Management only via Tailscale.

### F.6 Build the allowlist from real logs

When Phase 1.5 fires, do this in order:

1. Provision the UniFi gear, set up VLAN 20, plug the mini into a VLAN 20 port.
2. **Start with default-allow** outbound (log everything for 7 days).
3. After 7 days, export the firewall log, group destinations by host. The list above will be ~95% accurate; the log will catch the 5% you missed.
4. Switch to default-deny + the curated allowlist.
5. Watch the deny log for a week. Add anything legitimate that surfaces; investigate anything that shouldn't be there.

### F.7 Update the runbook

When Phase 1.5 lands, append a "Network" section to `docs/runbook.md`: VLAN map, port assignments, firewall rule diff for the next 30 days. If the network changes later, future-you needs to remember which port was VLAN 20.

---

*End of audit. Open to edits — flag any section that needs to go deeper or any decision that needs an explicit recommendation rather than a "you choose."*

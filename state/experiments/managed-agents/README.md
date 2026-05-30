# Managed Agents — experiment (NOT BUILD-READY)

**Status:** Backlog. Do not execute against live API without first fixing the P1 findings below.
**Created:** 2026-05-19
**Demoted:** 2026-05-19 (same day) after `/codex review` flagged 9 P1 / 7 P2 findings, and self-review against logs showed the proposal was premature.

## Why these files are here

These three files were drafted 2026-05-19 as a parallel-spike proposal for adding
Anthropic Managed Agents as a third orchestrator option alongside `alphaclaw` (PRD v0.3
default) and `Hermes-on-Railway` (PRD v0.6 default, locked 2026-05-13). They were
demoted to experiment status the same day because:

1. **MVE Phase -1 is still running.** Day 1 = 2026-05-19; verdict 2026-05-26. PRD §9.-1
   blocks all Phase 0+ orchestrator work until verdict.
2. **The `*-team` skills already validate the coordinator+worker pattern locally** via
   Claude Code subagents (`state/experiments/start-day-team.md` A/B methodology).
   Until those reach promotion (5+ runs at `quality_delta == 0` + wall-time win),
   there is no demand signal for a hosted multi-agent runtime.
3. **`/sync-sweep` was spec-locked 2026-05-19**, 7–9h build-ready, and competes for
   the same engineering time as a hypothetical G7-MA spike (3–4 days).
4. **Real pain points in May 2026** were API reliability (gtask 500 bursts 5/13–5/15,
   13-day Notion PATCH silence 5/02→5/15) and capture surface (in-person bypass) —
   none of which a new orchestrator solves.

The PRD addition was demoted to a single backlog paragraph in §19.7. The full
capability comparison and risk tables (R26/R27/R28) were stripped.

## P1 findings from `/codex review` (must fix before execution)

If the MVE passes, Hermes G7 runs, Hermes G7 fails, and we want to actually try
this path — these are the bugs that need fixing first:

### `agents-roster.yaml`

- **Tool types are wrong.** `bash_20250124` and `file_editor_20250124` are
  Messages/Claude API tool types, not Managed Agents shapes. Managed Agents uses
  `agent_toolset_20260401` with sub-configs (`bash`, `read`, `write`, `edit`).
  Verify against `/docs/en/managed-agents/tools` before rewriting.
- **MCP schema is underspecified.** Bare `mcp_servers: [{id: notion}]` is not a
  valid declaration. Spec requires `type`, `name`, `url` at agent creation, plus
  an `mcp_toolset` tool entry and `vault_ids` at session creation for auth.
  Verify against `/docs/en/managed-agents/mcp-connector` before rewriting.
- **`sync-sweep` system prompt is a placeholder** pointing at `end-day/SKILL.md`.
  Either build `/sync-sweep` first or drop it from the roster.
- **Codex disagreement to verify:** Codex claims the coordinator key is
  `callable_agents`, not `multiagent.agents`. The Anthropic multi-agent docs
  fetched 2026-05-19 show `multiagent: {type: coordinator, agents: [...]}`.
  Re-verify before rewriting — possible API drift.

### `agents-bootstrap.sh`

- **Heredoc variable interpolation bug.** The unquoted Python heredoc that
  builds `FINAL_COORD` embeds `${COORD_PAYLOAD}` directly into shell-expanded
  Python. Any `$...` or `${...}` inside the embedded SKILL.md prompt body
  expands under `set -u`, either corrupting JSON or crashing with "unbound
  variable." Fix: pass payload via stdin/env or base64-encode before
  interpolation, and use quoted heredocs (`<<'PY'`).
- **Idempotency hashes the wrong thing.** `action_id` hashes the full payload
  including the embedded SKILL.md body. Any whitespace, CRLF, comment, or
  unrelated skill edit re-fires agent creation and orphans old agents. Hash a
  canonical roster spec/version instead.

### `webhook-handler.py`

- **Dedup race loses events.** `_seen(event.id)` marks the ID BEFORE `_route()`
  succeeds. If `_route()` throws, the handler returns 500 → Anthropic retries
  → retry is dropped as duplicate → event lost permanently. Fix: only mark
  seen after durable route/dead-letter success.
- **5xx retry-loop risk.** Returning 500 on deterministic route bugs creates an
  infinite retry loop until Anthropic auto-disables the endpoint after ~20
  failures. Verified-signature events should go to a durable dead-letter log
  and return 2xx unless storage itself is transiently unavailable.
- **No GET hydration.** Webhook docs say payloads carry only `type`+`id` and the
  receiver should fetch the current object. As written, telemetry can't see
  status, stop_reason, duration, or thread outcome. Add `client.beta.sessions.retrieve(event.data.id)` after dedup.
- **`session.thread_terminated` is not always failure.** Code treats any
  "terminated" string as `status: failed`. Docs describe thread_terminated as
  archival; failure requires hydrating the object and checking stop_reason.
- **SEEN_FILE grows unbounded on disk.** Startup trims in-memory deque to 10k
  but the file never compacts. Long-running use grows forever. Use SQLite with
  a unique key, or periodic compaction with a checkpoint marker.

## Verified-correct things to preserve

- The nine webhook event types listed in `webhook-handler.py` (`session.status_*`,
  `session.thread_*`, `session.outcome_evaluation_ended`, `vault_credential.refresh_failed`)
  are real, documented webhook event types per the 2026-05-19 doc fetch.
- The SDK `unwrap()` signature-verification pattern matches the Python webhook
  docs verbatim.
- The general capability mapping (coordinator+roster as native, Telegram/cron
  as gaps, Anthropic-only as policy lock) is accurate research and worth
  preserving as the durable artifact if/when this gets revived.

## How this gets revived

Conditions, all required:

1. MVE Phase -1 passes (verdict 2026-05-26 or later).
2. `*-team` skills A/B reaches a promotion decision (pass or reject).
3. `/sync-sweep` is shipped.
4. Hermes G7 spike runs and **fails**, OR a new audit-grade requirement emerges
   that Hermes can't satisfy.
5. Routing-redesign analysis is complete.

If all five hold, fix the P1 findings above before any `POST /v1/agents` call.

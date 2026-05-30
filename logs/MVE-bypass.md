# MVE Bypass Log

**Purpose:** Test the phone-first capture premise *before* buying the Mac mini and building the Hermes agent. One row per meeting / clinic visit / capture-worthy moment for 7 days. The hypothesis: if you reliably capture from your phone during the day, dropped balls go down. If you don't reach for it, no always-on agent will save you — and you've learned that for $0.

**Window reset 2026-05-20.** The original window (start 5/19) slipped with no data logged because the Telegram bot was never activated. Restarting clean: Day 0 = today (setup), Day 1 = tomorrow.

**Decision criteria (re-pointed at the current Hermes + Mac-mini plan):**
- Capture rate high (you reached for it) AND briefings read daily → **build the Hermes/Mac-mini agent** (the §9 Phase 0 plan in `docs/vps-audit.md`). The habit is proven; always-on + road-reach is worth the $599–799.
- Briefings read but capture flat → **keep briefing delivery only** (Notion mobile page + Telegram send), skip the full agent build. Big scope reduction, no hardware.
- Briefings ignored AND capture flat → **don't build.** The premise didn't hold; rethink before spending anything.

The whole point is to have real behavior data before committing a weekend and $599–799.

---

## Day 0 — 2026-05-20 (Wed) — SETUP, NOT MEASURED

Activation day. Skip the capture table. Goal: bot live and one test message round-tripped.

**Setup checklist:**
- [ ] Telegram bot created via @BotFather; privacy set to Disable
- [ ] `.secrets/telegram.env` filled in with token + chat ID (template already created)
- [ ] Smoke test send: `. .\.secrets\telegram.env; "test" | .\scripts\mve-telegram-send.ps1` lands on phone
- [ ] Smoke test receive: DM the bot, run `.\scripts\mve-telegram-receive.ps1`, see `[q-001]` + a "Queued" reply on phone
- [ ] Receiver left running for the day: `.\scripts\mve-telegram-receive.ps1 -Loop`

**Notes:**

---

## Day 1 — 2026-05-21 (Thu)

| # | Time | Context (meeting / clinic / between) | Should have captured? | Did capture? | Surface used | If no, why? |
|---|------|--------------------------------------|----------------------|--------------|--------------|-------------|
| 1 |      |                                      |                      |              |              |             |

**Briefing read on phone?** [ ] yes  [ ] no  [ ] partial
**Briefing useful?** [ ] yes  [ ] no
**Notes / what surprised me:**


---

## Day 2 — 2026-05-22 (Fri)

| # | Time | Context | Should have captured? | Did capture? | Surface | If no, why? |
|---|------|---------|----------------------|--------------|---------|-------------|

**Briefing read on phone?**
**Briefing useful?**
**Notes:**


---

## Day 3 — 2026-05-23 (Sat)

| # | Time | Context | Should have captured? | Did capture? | Surface | If no, why? |
|---|------|---------|----------------------|--------------|---------|-------------|

**Briefing read on phone?**
**Briefing useful?**
**Notes:**


---

## Day 4 — 2026-05-24 (Sun)

| # | Time | Context | Should have captured? | Did capture? | Surface | If no, why? |
|---|------|---------|----------------------|--------------|---------|-------------|

**Briefing read on phone?**
**Briefing useful?**
**Notes:**


---

## Day 5 — 2026-05-25 (Mon)

| # | Time | Context | Should have captured? | Did capture? | Surface | If no, why? |
|---|------|---------|----------------------|--------------|---------|-------------|

**Briefing read on phone?**
**Briefing useful?**
**Notes:**


---

## Day 6 — 2026-05-26 (Tue)

| # | Time | Context | Should have captured? | Did capture? | Surface | If no, why? |
|---|------|---------|----------------------|--------------|---------|-------------|

**Briefing read on phone?**
**Briefing useful?**
**Notes:**


---

## Day 7 — 2026-05-27 (Wed)

| # | Time | Context | Should have captured? | Did capture? | Surface | If no, why? |
|---|------|---------|----------------------|--------------|---------|-------------|

**Briefing read on phone?**
**Briefing useful?**
**Notes:**


---

## Week Summary (fill at end)

- Total capture-worthy moments: ___
- Captured: ___ (___%)
- Missed: ___ (___%)
- Of those captured: how many via Telegram? ___ / via Notes app? ___ / via Notion mobile? ___ / via laptop? ___
- Baseline bypass rate (pre-MVE estimate from memory): ___%
- MVE bypass rate: ___%
- **Delta:** ___
- Briefing read days: ___ / 7
- Verdict: **BUILD HERMES/MAC-MINI** / **BRIEFINGS-ONLY** / **DON'T BUILD**

**Decision rationale (one paragraph):**

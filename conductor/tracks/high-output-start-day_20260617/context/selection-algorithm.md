# Selection Algorithm — picking exactly 3 outputs (T1)

The single most valuable artifact in this track: given Calendar + Notion + Tasks +
vault, how `/start-day` chooses the **3 business outputs** that get the
`## Today — Ship These 3` lane. This is judgment, encoded as a deterministic
pipeline so the shadow ship can be eyeballed and, later, ported to a scorer in
`scripts/output_planning.py`. An output is a *shippable business result* with a
done-state — not a task. "Sent the Healthix proposal" is an output; "work on
Healthix" is not.

## Pipeline (run in order; each stage narrows the candidate pool)

### Stage 0 — Build the candidate pool
Pull every actionable item from the four sources and normalize each to a
`DailyOutput` candidate (title, owner = Workspace/department, `source_refs`,
status). Sources:
- **Notion Master Tasks** — overdue + in-progress + due-today (Workspace field is owner).
- **Google Tasks** — due-today / overdue quick-captures.
- **Calendar** — today's meetings become *meeting-conversion* candidates (see scoring).
- **vault inbox / priorities.yaml `carry_forward`** — yesterday's unshipped outputs.

Apply the standard COO Twin routing rules to set `owner` (never inherit department
from a parent task name — check each item's own Workspace field; infer only if null).

### Stage 1 — Portfolio Pulse (which business has the best leverage today)
Score each business (Nestmate, Dock Pro / Cardio Pro, United IPA, Lincoln Lab,
Other) for **leverage density today**: where does one action unblock the most
downstream value *right now*? Signals, highest first:
1. A constraint that, if removed today, unblocks a chain (a credentialing gate, a
   single approval blocking a launch, a provider waiting on one reply).
2. A revenue/relationship event with a today-shaped window (a deal that closes if
   touched today, a relationship that decays if not).
3. Density of overdue/at-risk items concentrated in one business.

The winning business is the **Portfolio Pulse** — surfaced as a 1-line note. It
does NOT force all 3 outputs into that business; it biases ties and guarantees the
top-leverage business is represented.

### Stage 2 — Score each candidate by leverage type
Rank candidates by leverage class (descending). Ties broken by Portfolio-Pulse
business first, then by Notion `Due` / overdue age.

| Rank | Leverage type | Why it wins |
|------|---------------|-------------|
| 1 | **Constraint-removal** | Unblocks other work / other people. Highest multiplier. |
| 2 | **Revenue / relationship** | Direct business value or a decaying relationship window. |
| 3 | **Delegation-as-shipped** | A clean `DelegationAsk` (delegatee + ask + date) *counts as shipped* — handing off the right thing is an output. |
| 4 | **Meeting-conversion** | A today meeting that must end in a decision / owner / next action (feeds `## Meetings That Must Convert`). |
| 5 | **Admin** | Necessary but low-leverage; only reaches the 3 if nothing higher exists. |

### Stage 3 — Day-type filter
Classify today from the calendar density:
- **Field day** (back-to-back meetings / travel): drop deep-work outputs that need
  an uninterrupted block; prefer meeting-conversion + delegation + quick
  constraint-removals. **No deep-work blocks proposed on a field day.**
- **Desk day** (open blocks): deep-work constraint-removal outputs are viable.

This only filters/re-ranks; it never invents candidates.

### Stage 4 — Starvation guard
If a business or a carry-forward output has gone **unshipped for N days** (tracked
via `priorities.yaml carry_forward` age), force-promote its top candidate into the
3 even if Stage 2 would rank it 4th. Prevents a chronically-starved business from
never surfacing. At most one starvation override per morning.

### Stage 5 — Output exactly 3
Take the top 3 after Stages 2–4. Enforce **1:1 grouping** (`group_outputs(...,
max_children=1)`): each output carries exactly one `SourceRef`, so its sync marker
renders on its own non-indented `- [ ]` line (contract #1). If fewer than 3 real
candidates exist, render fewer — never pad with admin filler.

Render: `render_output_plan_markdown()` for the daily-note shadow lane (phone-first,
no tables) and `render_log_top3()` for `logs/{DATE}.md` (`## Top 3 Outcomes`,
contract #2).

## Worked tie-break example
Two candidates rank as constraint-removal: a Nestmate provider waiting on one reply,
and a Lincoln Lab panel approval. Portfolio Pulse = Nestmate today (provider chain
unblocks three downstream accounts) → Nestmate wins the tie and takes slot 1; the
lab approval competes for slots 2–3 against the next leverage tier.

# MiroFish Simulation Prompt — Sovereign Phoenix IPA Acquisition

Companion to `sovereign-phoenix-reality-seed.md`. The seed is the *world*; the
text below is the **`--requirement`** — the plain-English prediction goal
MiroFish interprets to drive the agent swarm. Best-practice notes and the exact
run command follow.

---

## The simulation prompt (`--requirement`)

> Copy the block between the lines verbatim into `--requirement`.

---
Predict whether a four-cash-partner group (Aaron, Luis, DocPro, Ahmed Lewis;
Brian operating but not in cash split) should buy into Sovereign Phoenix IPA —
a ~750-provider, financially impaired New York IPA with a current 2.5-star
quality rating — for a $250,000 minimum buy-in (~$62,500 per cash partner)
for 51% control, with the ~$1.2M legacy 2020 loan staying OFF the 51% (debt
remains with existing ownership/entity, not assumed pro-rata). Determine
whether this acquisition and a quality push from 2.5 -> 4 stars would be
SUCCESSFUL, PROFITABLE, and DURABLE over a 24-month horizon. Return a single
bottom-line verdict — BUY, DON'T BUY, or BUY ONLY IF [conditions] — with an
overall probability of success, a confidence level, AND a separate judgment
on longevity (viable 5-10 years out, or short-lived?).

The value proposition has shifted: the PRIMARY engine is now the Aetna
Medicare shared-savings contract — Level 2 = 50% upside AND 50% downside,
with a Y1-only carve-out of NO downside (the honeymoon year), payouts in
~3 months. From Y2 onward downside is live, so stalled execution becomes a
real loss, not a break-even. At 4 stars, Aetna pays $12 PMPM admin fee.
NOTE: SP is NOT pursuing ACO REACH — the Aetna MA contract is the only
shared-savings engine in scope. Lincoln Lab's existing lab-data footprint is used to identify crucial
Aetna Medicare providers, onboard the high-value ones, and shift around
providers who are unchangeable. Generated shared-savings cash is then used to
self-fund buyout of additional equity from existing owners over time. The
HARD precondition is that the acquisition only proceeds IF contracts are
retained AND the group can show other health plans a turnaround using Aetna
as the proof point.

Center the simulation on (1) the insurers and regulators who must re-approve
the change of control — Aetna Medicare contracting (now the most important),
Health First, Fidelis, and NY State Department of Health under Public Health
Law §7a (statutory authority over change of control); (2) the existing Sovereign
Phoenix owners being bought out, including the ~10% minority owner expected to
flip. Also model provider behavior through multiple angles — especially a
private primary-care physician who has held the same contract for ~15 years
and does not want to change anything (the retention bellwether; note that this
physician is typically NOT actually inside the IPA but a contracted independent,
so retention is about not disturbing the existing contract), alongside
cost-pressured younger physicians more open to joining and infrastructure-driven
benefits.

Judge financial feasibility realistically: whether the group secures >=51%
ownership and removes existing management; whether Aetna, Health First, and
Fidelis approve the new owners WITHOUT terminating contracts; whether DocPro
(the architect of SAIPA's 4.8-star quality score) can credibly move Sovereign
Phoenix from 2.5 to 4 stars within the simulation horizon; whether the Aetna
Level-2 3-month-payout cash flow keeps Year-1 cash positive while shared
savings ramp; whether $12 PMPM at 4 stars plus 50% Aetna shared savings can
clear the $250K up-front commitment, fund the self-funded buyout of additional
equity, and turn a durable margin; and whether physician panels (especially
high-value Aetna Medicare prescribers) stay or are successfully onboarded via
Lincoln-lab-data targeting. Weigh this against New York's market structure —
the state is cutting independent-provider reimbursement and steering physicians
into IPAs to control cost — and assess whether that trend makes a scaled,
high-quality, Aetna-Medicare-anchored master IPA a durable franchise or whether
rate compression eventually squeezes it. Compare its prospects to other NY IPAs
(SAIPA at 4.8 stars as the high performer DocPro already runs, the Central
Queens no-margin specialist model as the failure mode). Surface key turning
points, the single most decisive risk to profitability and longevity, the most
pivotal actor, and the specific conditions under which the group should walk
away.
---

---

## Best-practice notes baked into this prompt

These follow how MiroFish actually works (GraphRAG knowledge graph → persona
agents → multi-round social simulation → ReportAgent verdict):

- **Names a clear prediction target + horizon** ("24-month horizon... whether...
  succeeds"). MiroFish wants a single, answerable forecast question, not an
  open-ended essay request.
- **Explicitly centers named stakeholder cohorts** so the persona generator
  grounds agents in the real entities from the seed (insurers/regulators +
  exiting owners), instead of inventing generic crowds.
- **Lists the concrete pressures/events** the agents should react to — these map
  one-to-one to the gates in the seed, giving the simulation a timeline to
  evolve along.
- **Asks for a structured, multi-part verdict (A–D) with probability +
  confidence** — this is what makes `verdict.json` useful rather than vague, and
  matches your four chosen success metrics.
- **Asks for turning points, the pivotal actor, and walk-away conditions** — the
  decision-useful outputs, not just a yes/no.

---

## Exact command to run it

From the `mirofish-cli` repo (after `cp .env.example .env`, `uv sync`, and
confirming `LLM_PROVIDER=claude-cli`):

```bash
mirofish run \
  --files "C:/Users/aaron/daily-automation/sovereign-phoenix-reality-seed.md" \
  --requirement "Predict whether a four-cash-partner group (Aaron, Luis, DocPro, Ahmed Lewis; Brian operating but not in cash split) should buy into Sovereign Phoenix IPA — a ~750-provider, financially impaired New York IPA currently at 2.5 stars — for a $250K minimum buy-in (~$62.5K per cash partner) for 51% control, with the ~$1.2M legacy 2020 loan staying OFF the 51% (shared savings later retire the legacy debt and fully buy out existing owners). Determine whether this acquisition and a quality push from 2.5 to 4 stars would be SUCCESSFUL, PROFITABLE, and DURABLE over a 24-month horizon. Return BUY, DON'T BUY, or BUY ONLY IF [conditions] with probability, confidence, and a separate longevity judgment (5-10 years). The primary value engine is the Aetna Medicare shared-savings contract — Level 2 = 50% upside AND 50% downside, with a Y1-only carve-out of NO downside (honeymoon), payouts in ~3 months. From Y2 onward downside is live so stalled execution is a real loss. SP is NOT pursuing ACO REACH. At 4 stars Aetna pays $12 PMPM admin. Lincoln Lab data identifies high-value Aetna Medicare providers to onboard and lets the team shift providers who are unchangeable. Shared-savings cash is then used to self-fund buyout of further equity from existing owners. Hard precondition: only proceed IF contracts are retained AND a turnaround can be demonstrated using Aetna as proof point to other plans. Center on (1) Aetna Medicare contracting, Health First, Fidelis, and NYSDOH under Public Health Law §7a; (2) existing owners being bought out plus the ~10% flipping minority owner. Model provider angles, especially the 15-year tenured private PCP (note: typically not actually in the IPA, so retention is don't-disturb-the-contract) and cost-pressured younger physicians more open to joining. Judge financial feasibility: securing >=51% + removing existing management; payer approvals of new owners without contract terminations; whether DocPro (architect of SAIPA's 4.8-star score) can move 2.5 to 4 stars in horizon; whether Aetna Level-2 3-month payouts keep Year-1 cash positive; whether $12 PMPM at 4 stars + 50% Aetna shared savings clears the $250K commitment, funds the self-funded buyout, and turns durable margin; whether physician panels stay or are successfully onboarded via Lincoln data targeting. Weigh NY's rate-cut + push-into-IPAs structure as tailwind or trap. Compare to SAIPA (4.8 high performer) and Central Queens (no-margin failure mode). Surface key turning points, single most decisive risk to profitability and longevity, most pivotal actor, and walk-away conditions." \
  --platform parallel \
  --max-rounds 12 \
  --json
```

Notes on the flags:
- `--platform parallel` runs both the Twitter- and Reddit-style channels (widest
  behavioral coverage). Use `twitter` or `reddit` alone for a cheaper, narrower
  run.
- `--max-rounds 12` is a deliberate, modest setting — the docs recommend keeping
  rounds low (well under 40) to control compute/token cost; 10–12 is plenty to
  see the dynamics emerge. Raise it only if turning points look truncated.
- `--json` emits the machine-readable result (including `verdict.json`) to
  stdout; drop it for the rich visual pipeline view.
- Outputs land in `uploads/runs/<run_id>/` — the decision-useful files are
  `report/report.md`, `report/verdict.json`, and `report/summary.json`.

---

## Honest caveat on what this will and won't tell you

MiroFish is a multi-agent *reaction* simulator, not a financial model. Each
"agent" is an LLM persona reacting in turns; the engine surfaces **how
stakeholders might behave and where the deal breaks socially/politically** —
incumbent obstruction, payer skepticism of new owners, provider flight. It will
**not** compute your IRR or validate the PMPM math. Treat the verdict as a
structured stress-test of the human/institutional dynamics, and pair it with a
real financial model (the $1.2M loan terms, renegotiated PMPM rates, and
shared-savings capture are where the actual go/no-go lives). The seed's §5
economics are there to ground the agents, not to serve as that model.

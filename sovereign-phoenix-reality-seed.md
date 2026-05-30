# Reality Seed — Acquisition & Consolidation of Sovereign Phoenix IPA

> **Purpose of this document.** This is a MiroFish *reality seed*. It is the
> grounded source material the engine uses to build its knowledge graph,
> generate stakeholder agent personas, and run the multi-agent simulation.
> Everything below is written as fact-rich, entity-dense, relationship-explicit
> context so GraphRAG can extract the players, their motives, the pressures
> between them, and the institutions involved. The *question* to simulate lives
> in the companion `--requirement` (see `sovereign-phoenix-simulation-prompt.md`).
>
> Compiled 2026-05-27 from Aaron's Obsidian vault (daily notes 2026-05-13 →
> 2026-05-26) plus deal context provided directly, and updated 2026-05-27 with
> additional operating detail (network size, team track record, member pools,
> payer cash-flow timing, and the New York regulatory environment). Figures
> marked *(est.)* are modeling assumptions, not verified contract values.

---

## 0. ADDENDUM 2026-05-27 (supersedes earlier figures where in conflict)

Revised deal structure after current-management discussions and an updated read
of the value proposition. The earlier sections remain context, but **where they
conflict with this addendum, this addendum governs.**

- **Discretion-first posture.** All discussion of the future purchase happens
  in discretion; the cap-table mechanics below are the current-management ask,
  not a public position.
- **Cost of control is now $250K, not $1.8M.** The current-management minimum
  buy-in for 51% control is **~$250,000 cash**, with the **~$1.2M legacy 2020
  loan staying OFF the 51%** — i.e., the debt remains with the existing
  ownership / the entity, not assumed pro-rata by the acquiring group. The
  acquiring group's goal is to put in **as little upfront cash as possible**.
- **Four-way cash split.** Up-front cashflow contributed by **Ahmed Lewis, Luis,
  Aaron, and DocPro** in an **even four-way split** ≈ **$62,500 per partner**.
  (Brian remains in the operating group but is not in the upfront cash split.)
- **Self-funded buyout thesis.** Generated shared-savings cash is intended to
  **buy out more of the IPA from existing owners over time**, reducing the
  need for further outside capital and progressively consolidating control.
- **Hard precondition.** The acquisition only proceeds **if the contracts are
  retained AND the group can show other health plans the turnaround work using
  Aetna as the proof point**. No contract retention → no deal.

### 0a. The value proposition has shifted — Aetna Medicare is now the engine

- The primary value lever **moves from Health First → Aetna Medicare** shared
  savings. The Aetna Medicare contract is **Level 2 (50% upside, NO downside)
  for this year** with **payouts ≈ 3 months** (not the Fidelis 2-year lag) —
  this **structurally fixes the Year-1 cash gap** that dominated earlier
  modeling.
- **Current panel: ~750 providers** (refined from the earlier ~400 figure;
  this larger number is the Aetna-Medicare-attributed network).
- **Current quality rating: 2.5 stars.** Target: **4 stars**.
- **At 4 stars, Aetna pays $12 PMPM admin fee** (vs. the $2–$3 PMPM Medicaid
  numbers earlier modeled) — a step-change in unit economics if quality moves.
- **Lincoln Lab data is the targeting weapon.** Lincoln's existing lab-data
  footprint is used to **identify crucial Aetna Medicare providers**, onboard
  the high-value ones, and **shift around providers who are unchangeable**.

### 0b. DocPro's credibility is more specific than "#2 in NY"

- DocPro is the **architect of SAIPA's 4.8-star quality score** — the
  highest-tier evidence the team can take a 2.5-star book to 4.0+. Replicating
  that here is the central success bet.

### 0c. Updated role allocation (current)

- **DocPro** — billing and data (the population-health platform; care-gap
  monitoring; risk stratification; coding accuracy).
- **Aaron + Ahmed Lewis** — provider engagement and enrollment; **changing
  doctor habits** to drive quality improvement to 4 stars.
- **Luis** — contract negotiation across Aetna, Health First, Fidelis.
- **Brian** — operating partner, not in upfront cash split.

### 0d. Cross-reference with MiroFish run (BUY ONLY IF, 68% / 89%)

The first-run MiroFish report was built on the pre-addendum framing
(Fidelis-centric, $1.8M cost of control, 400 docs). Its **structural insights
still apply** — Health First HEDIS validation is the cascade trigger; NYSDOH
§7a is the decisive statutory authority; the tenured PCP isn't actually "in"
the IPA so retention is "don't disturb, don't break contracts"; 5-year
longevity is structurally pressured by NY rate compression. But the **Year-1
financial unviability finding is substantially relaxed** by the Aetna Level-2
/ 3-month-payout pivot in this addendum. A re-run with the updated seed is
warranted before final commitment.

---

## 1. The scenario in one paragraph

A five-person partner group is attempting to acquire and take majority control
of **Sovereign Phoenix IPA**, a ~**400-physician**, financially impaired
independent physician association in New York State whose quality scores are
currently mediocre. The plan is to buy at least 51% of the equity, strip the
existing ownership of managerial control, clean up the Health-First-mandated
HEDIS quality measures so the IPA can onboard providers again, fold Sovereign
Phoenix together with other small IPAs into a single **master IPA**, migrate a
large Health First / Fidelis member base onto the most lucrative contracts, and
profit from the per-member-per-month (PMPM) administrative fee plus
shared-savings surplus. The deal is constrained by a legacy debt load, antiquated
low-value contracts, a payer-mandated quality cleanup, a ~3-month exclusivity
window, a **two-year lag on Fidelis shared-savings payments** (so year one is
unlikely to be profitable), and the fact that any change of control triggers
**payer review and re-approval of the new owners**. It plays out against a New
York market that is **cutting independent-provider reimbursement and steering
physicians into IPAs to control cost** — a structural tailwind for scaled,
high-quality IPAs and a squeeze on sub-scale, low-quality ones. The simulation
explores whether buying into this business is a sound, profitable, and *durable*
move over a 24-month horizon.

---

## 2. Organizations (entities)

### Sovereign Phoenix IPA (the acquisition target)
- Independent Physician Association based in **New York State**.
- **~400 physicians** in network. Quality is currently **"okay, not great"** —
  precisely why a HEDIS / quality cleanup is mandatory before growth.
- Financially impaired: carries a **~$1.2M loan** from operational failures in
  **2020**.
- Holds antiquated, low-value payer contracts (see §6).
- **Cannot onboard new providers** until it completes the Health-First-mandated
  **HEDIS quality-measure cleanup**.
- Once cleaned up, it can **incorporate ~25,000–30,000 Health First patients**.
- One existing owner holds a **~10% stake** and is expected to **flip to the
  acquirers**.
- Purchase economics: **~$600K equity** (**DocPro already $50K down**) plus the
  assumed **~$1.2M legacy loan** → **~$1.8M total cost of control** *(est.)*.

### The consolidation play — building one "master IPA"
The thesis is to roll several small IPAs into a single high-performing master
IPA, shift members to the most lucrative contract, and profit on PMPM admin fee +
shared-savings surplus *if* medical cost is well managed. Member pools in play:
- **Sovereign Phoenix** — ~25–30K Health First patients incorporable post-cleanup.
- **Lewis's separate IPA** — a second IPA that **Ahmed Lewis has access to**,
  which **on its own can bring ~25,000 Health First members**.
- **SPIPA** (~5K Health First) and **Starling** (~25K Health First) — small IPAs
  named in earlier planning; may overlap with the pools above (treat totals as a
  range, not additive certainty).
- **NY IPA (New York IPA)** — was in Health First contract talks; outcome
  **unresolved** in the source notes.
- **Consolidated target:** plausibly **~50,000+ Health First lives** if Sovereign
  Phoenix + Lewis's IPA combine, potentially higher with the smaller IPAs —
  *(est.; subject to overlap and payer approval)*.

### DocPro (the team's analytics / billing engine)
- DocPro *(also called "Doc Protein")* is the **"heat and billing engine"**: care-gap
  monitoring, risk stratification, coding, and a **purpose-built patient-population
  platform that tracks all the data** for the IPA.
- **Track record:** DocPro currently runs operations for **South Asian IPA
  (SAIPA)** — **the #2 IPA in New York** for health measures, care-gap quality,
  and cost-measurement performance. This is the single strongest evidence the
  team can actually execute a HEDIS cleanup and capture shared savings.
- Most financially committed partner ($50K down).

### Payers / health plans (institutional actors)
- **Health First** — pays a PMPM admin fee to IPAs; gatekeeper of the HEDIS
  cleanup; reviews new owners on change of control. Sovereign Phoenix's contract
  is **Level 1 = 25% shared savings, upside-only**. Rate to IPA ≈ **$2 PMPM**
  *(per deal context)*.
- **Fidelis** — pays a PMPM admin fee ≈ **$3 PMPM** *(est.)* on an antiquated
  contract. **Critically, Fidelis back-pays shared savings on a ~2-year lag**, so
  the shared-savings cash from a Fidelis book does not arrive until ~year 3 —
  **year one is essentially not profitable on this line.**
- **Aetna** — antiquated **Medicare** contract *(per deal context, unconfirmed)*;
  CMS-adjacent scrutiny on ownership change.
- **NY State Department of Health / regulators** — governs IPA change-of-control
  and is actively reshaping the market (see §7a).

### Contrast / benchmark entities (for graph context)
- **South Asian IPA (SAIPA)** — #2 in NY; the performance bar and DocPro's proof
  of competence. The master IPA aspires to this tier.
- **Central Queens IPA** — **counter-pattern to avoid**: takes specialists but
  earns no margin on them; profits only via an annual fee. The "how not to build
  it" model.

---

## 3. People & roles (agent personas)

> Each actor is given motive, incentive, leverage, and fear so the simulation
> can produce believable behavior.

### The acquiring partner group (the "five partners")
1. **Aaron** — protagonist / decision-maker; runs a reference lab, a
   specialty-pharmacy op (Nestmate), a cardiac-monitoring rollout (Cardio Pro),
   and this IPA initiative. Views the IPA as **"the next income bringer and exit
   strategy out of the lab."** Role: **provider onboarding + relationships**
   (with Ahmed Lewis, has **direct access to onboard Health First doctors and a
   Health First / Fidelis patient population**). Fear: sinking ~$1.8M and
   attention into an impaired asset that payers later refuse to approve, or that
   New York's rate cuts erode before it scales.
2. **Luis** — **contracts** lead; deep in Health First / Fidelis relationships;
   owns the **HEDIS / Health First standing cleanup** that gates the deal.
   (Plausibly the ~10% owner who flips — to confirm.)
3. **DocPro** *("Doc Protein")* — **billing, risk stratification, coding, and the
   population-health data platform**; proven at SAIPA (#2 in NY). $50K down →
   strongest push to close; competence determines whether shared-savings upside
   is actually captured.
4. **Ahmed Lewis** — **provider onboarding + relationships**; with Aaron, holds
   **provider access to onboard Health First doctors (HF + Fidelis population)**.
   **Also has access to a separate IPA that alone brings ~25,000 Health First
   members** — a major source of consolidation scale. *(Note: "Ahmed," "Lewis,"
   and "Ahmed Lewis" in the source notes are treated here as the same person.)*
5. **Brian** — **provider onboarding + relationships**; field-relationship role
   alongside Aaron and Ahmed Lewis.

Stated role allocation: *Luis on contracts; DocPro on billing/risk/coding and
the data platform; Ahmed Lewis + Aaron + Brian on onboarding providers and
maintaining relationships via runners between docs.*

### The other side of the table
6. **Existing Sovereign Phoenix ownership group** — incumbents to be **bought out
   and removed from management**. Carry the scars of the 2020 failure and the
   $1.2M loan. Motive: maximize exit value / retain some interest; fear: walking
   away with nothing if contracts lapse.
7. **The ~10% owner who flips** — pivotal swing actor; their defection changes
   the control math and the incumbents' leverage.

### Institutional decision-makers (payer / regulator personas)
8. **Health First contracting / compliance reviewer** — must accept the HEDIS
   cleanup as "done" AND approve the new owners. Motive: protect quality scores
   and network stability; fear: handing a Medicaid/MA book to unproven owners.
9. **Fidelis contracting reviewer** — same change-of-control lens; may use the
   trigger to renegotiate the antiquated $3 PMPM rate; controls the ~2-year
   shared-savings payment lag.
10. **Aetna Medicare contracting reviewer** — reviews the antiquated Medicare
    contract; CMS-adjacent scrutiny raises the bar.
11. **NY State health regulator** — sets the macro rules: cutting
    independent-provider reimbursement, steering physicians into IPAs (§7a).

### Provider personas (network behavior — the retention/onboarding question)
12. **The 15-year tenured private PCP** — an independent primary-care physician
    who has held the same contract for ~15 years, is comfortable, and **does not
    want to change anything**. Skeptical of joining/migrating, inertia-driven,
    distrustful of "consolidation." The hardest retention/onboarding case — and
    the bellwether for whether NY's rate cuts eventually force his hand.
13. **The cost-pressured younger PCP / group** — feeling NY's reimbursement cuts,
    more open to the protection and shared-savings upside an IPA offers; the
    easier onboarding win.
14. **The specialist** — relevant to the Central Queens trap: joins easily but
    may add no margin unless structured correctly.

### Flagged / excluded actor
15. **Kader** — flagged **"untrusted"**; **excluded from any acquisition step.**

---

## 4. Relationships (graph edges — state explicitly)

- Aaron, Luis, DocPro, Ahmed Lewis, Brian → **partners in** the acquiring group.
- DocPro → **runs / proven at** South Asian IPA (#2 in NY) → **competence signal**.
- DocPro → **builds the patient-population data platform for** the master IPA.
- DocPro → **has paid $50K toward** Sovereign Phoenix purchase.
- Ahmed Lewis + Aaron → **have provider access to onboard** Health First doctors
  (HF + Fidelis population).
- Ahmed Lewis → **has access to** a separate IPA (~25K Health First members).
- Acquiring group → **seeks ≥51% of + intends to remove management of** Sovereign
  Phoenix.
- ~10% owner → **expected to flip to** the acquiring group.
- Sovereign Phoenix → **owes ~$1.2M loan** (2020), **employs ~400 physicians**,
  **holds contracts with** Health First, Fidelis, Aetna.
- Health First → **requires HEDIS cleanup before** new onboarding; **reviews new
  owners on** change of control.
- Fidelis → **back-pays shared savings ~2 years late** → **year-1 unprofitability**.
- Change of control → **triggers review by** Health First, Fidelis, Aetna.
- Sovereign Phoenix + Lewis's IPA (+ SPIPA / Starling / NY IPA) → **merge into**
  one master IPA → **migrate members to** the most lucrative contract → **earn**
  PMPM + shared-savings surplus.
- NY State regulator → **cuts independent-provider pay + pushes physicians into
  IPAs** → **raises the value of** a scaled, high-quality master IPA.
- 15-year tenured PCP → **resists joining/migrating to** the IPA.
- Central Queens IPA → **negative exemplar**; SAIPA → **positive benchmark**.
- Kader → **excluded from** all acquisition activity.

---

## 5. Economic reality (grounding numbers for the agents)

> Order-of-magnitude grounding, blending the notes with stated terms. *(est.)*
> where assumed.

**Cost of control**
- Equity purchase: **~$600K** ($50K paid). Assumed legacy debt: **~$1.2M**.
- **Total cost of control ≈ $1.8M** *(est.)*.

**Member base (the revenue driver)**
- Sovereign Phoenix post-cleanup: **~25–30K Health First** patients.
- Lewis's separate IPA: **~25K Health First** members.
- Plus small IPAs (SPIPA ~5K, Starling ~25K) — possible overlap.
- **Consolidated target ≈ 50K+ Health First lives** *(est.)*.

**Recurring revenue — PMPM admin fee** (illustrative at 50K lives)
- Health First ≈ $2 PMPM: 50,000 × $2 = **$100K/mo ≈ $1.2M/yr**.
- Fidelis ≈ $3 PMPM: 50,000 × $3 = **$150K/mo ≈ $1.8M/yr**.
- Legacy PMPM rates ($2–$3) are **low/antiquated** — renegotiation post-control is
  a core value lever, but New York is cutting rates, not raising them (§7a), so
  the realistic lever is **scale + shared savings**, not rate hikes.

**Shared savings (the real margin) — and its timing problem**
- Health First Level 1 = **25% of savings, upside-only**; capture depends on
  HEDIS performance, coding/risk-adjustment (DocPro), and provider behavior.
- **Fidelis back-pays shared savings on a ~2-year lag.** Practical effect: the
  shared-savings cash that justifies the deal **does not arrive in year one**.
  **Year one is admin-fee-only and likely break-even-to-negative** after debt
  service and operating cost; the payoff is **back-loaded to years 2–3**.

**Rough feasibility intuition (for grounding, not a verdict)**
- Year 1: admin fee (~$1.2–1.8M gross) − opex (5 partners + runners + platform,
  *est.* $0.5–1.0M) − debt service on $1.2M → **thin or negative**; little/no
  shared savings yet.
- Years 2–3: shared-savings cash begins landing; if DocPro replicates SAIPA-level
  performance and the book scales to 50K+ lives, margin can turn meaningfully
  positive and the ~$1.8M is recoverable.
- **The deal is a back-loaded bet:** survive payer re-approval, fund a roughly
  unprofitable year one, then harvest shared savings at scale. Feasibility hinges
  on (a) cash runway through the lag, (b) execution to SAIPA quality, (c) scale,
  and (d) New York's market structure rewarding scaled IPAs rather than gutting
  their economics.

---

## 6. Contracts (the payer book)

| Payer | Line | Rate to IPA | Structure | Timing / note |
|-------|------|-------------|-----------|---------------|
| Health First | Medicaid/MA | ~$2 PMPM *(est.)* | **Level 1: 25% shared savings, upside-only** | Gatekeeper of HEDIS cleanup; reviews new owners |
| Fidelis | Medicaid | ~$3 PMPM *(est.)* | PMPM admin fee + shared savings | **Shared savings back-paid ~2 yrs late → year-1 not profitable** |
| Aetna | **Medicare** | unconfirmed | Antiquated Medicare contract | CMS-adjacent scrutiny on ownership change |

---

## 7. Pressures, constraints & gates

1. **HEDIS cleanup gate.** No new onboarding until Health First's quality cleanup
   is done (the ~400 docs are "okay, not great"). 60-day checkpoint ~2026-07-14.
2. **Change-of-control payer review.** Buying the IPA opens the new owners to
   Health First / Fidelis / Aetna review; payers may renegotiate or terminate the
   antiquated contracts. Largest binary risk.
3. **Year-1 cash-flow gap.** Fidelis shared savings lag ~2 years → the deal funds
   a roughly unprofitable first year before the margin arrives. Runway risk.
4. **≥51% control + manager removal**, with the flipping ~10% owner as foothold.
5. **Legacy debt** (~$1.2M, 2020) rolls into the deal → leverage magnifies both
   downside and the urgency of revenue capture.
6. **~3-month exclusivity** to **2026-08-14** (~79 days from 2026-05-27).
7. **Execution / trust risk** inside a group unproven together at this scale;
   deferred "DocPro nuance-lock" huddles; **Kader excluded as untrusted**.
8. **The Central Queens trap** — a no-margin specialist book.

### 7a. New York market structure (the longevity context)
- New York is **cutting independent-provider reimbursement per contract** —
  squeezing solo/independent physicians.
- The state appears to be **steering physicians into IPAs to control costs** —
  i.e., consolidating care under IPA risk arrangements.
- **Implication for longevity:** if NY pushes doctors into IPAs, a **scaled,
  high-quality, low-cost master IPA is a durable, strategically valuable
  position** — independents will need a home, and payers reward performance. But
  the same rate pressure means **margins come from quality/cost performance and
  scale, not from rich PMPM rates**. A sub-scale or low-quality IPA gets squeezed
  out. Sovereign Phoenix's survival therefore depends on reaching SAIPA-tier
  performance and real scale before the rate environment tightens further.

---

## 8. Timeline / sequence (memory for the agents)

- **2020** — Sovereign Phoenix failures; ~$1.2M loan incurred.
- **~2026-05-13** — Luis ↔ Health First meeting; acquisition path identified;
  consolidate small IPAs into a master IPA; DocPro's $50K-down / $600K-purchase
  surfaced; $1.2M loan flagged for diligence.
- **2026-05-18** — Full team meeting (Luis / Ahmed Lewis / Brian / DocPro):
  loan diligence, contract comparison, PMPM model, role lock-in, member migration.
- **Through May 2026** — Three diligence workstreams carried: $1.2M loan terms,
  IPA contract comparison, PMPM + shared-savings model. NY IPA's Health First
  talks unresolved.
- **~2026-07-14** — Planned 60-day HEDIS-cleanup checkpoint.
- **2026-08-14** — End of the ~3-month exclusivity window.
- **2026-05-27 → 2028-05 (24-month horizon)** — close, pass payer re-approval,
  clean HEDIS, fund a thin year one through the Fidelis lag, migrate members,
  reach SAIPA-tier quality, scale to 50K+ lives, and turn durable margin while
  retaining providers — judged against New York's tightening market.

---

## 9. Known unknowns (let the agents probe these)

- Is the all-in truly ~$1.8M, or does the "$1.3M" figure reflect a debt haircut?
- Will payers **approve the new owners**, or **kill the antiquated contracts**?
- Can the team **fund a roughly unprofitable year one** through the Fidelis lag?
- Will the HEDIS cleanup finish inside the exclusivity window, given ~400
  middling-quality docs?
- Does the member math truly reach ~50K lives, or do the pools overlap?
- Will the **15-year tenured PCP** and his peers **stay/join**, or resist until NY's
  cuts force them?
- Does New York's push-into-IPAs trend actually arrive on a timeline that helps
  this deal — and does it reward scale/quality or just compress everyone's rates?
- Can DocPro **replicate SAIPA-level performance** here?

---

## 10. Scenario branches worth simulating

- **Clean close + scale:** flip the 10% owner, hit 51%, clear HEDIS by July,
  payers re-approve, fund year one, DocPro hits SAIPA-tier quality, consolidate to
  50K+ lives, durable margin by month 18–24. NY's IPA push makes it strategically
  valuable.
- **Payer veto:** change-of-control review terminates/cuts the antiquated
  contracts, gutting the base.
- **Runway failure:** the Fidelis 2-year lag plus debt service starves year one;
  the group can't fund to the payoff and folds early.
- **Incumbent holdout:** existing owners obstruct / hold for more; exclusivity
  lapses before 51%.
- **Provider flight / inertia:** the tenured PCP cohort refuses to migrate, the
  network shrinks, and the book never reaches profitable scale.
- **Quality stall:** HEDIS cleanup drags; without SAIPA-tier performance, shared
  savings never materialize and NY's rate cuts squeeze the IPA out (the Central
  Queens fate).
- **Market-structure win:** NY's rate cuts + IPA consolidation accelerate;
  independents flood in for protection; the scaled master IPA becomes a durable,
  high-value franchise (the longevity case).

---

## 11. Glossary

- **IPA** — Independent Physician Association: contracts with health plans for a
  physician network; earns admin fees + shared savings.
- **PMPM** — Per Member Per Month recurring fee.
- **HEDIS** — standardized health-plan quality measures; gates network growth.
- **Shared savings** — IPA keeps a % of medical cost saved vs. benchmark.
  **Upside-only** = keeps savings, no losses. **Level 1** here = 25%, upside-only.
- **Change of control** — ownership change triggering payer review/re-approval.
- **Master IPA** — the consolidated entity built from several small IPAs.
- **SAIPA (South Asian IPA)** — #2 IPA in NY for quality/cost; DocPro's track
  record and the performance bar.
- **Care gap** — a missed recommended service (screening, follow-up) that hurts
  HEDIS scores; closing gaps drives both quality and shared savings.

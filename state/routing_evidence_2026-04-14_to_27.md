# Routing Evidence — 2026-04-14 to 2026-04-27

Source: 8 daily logs (2026-04-14, 2026-04-15, 2026-04-16, 2026-04-20, 2026-04-21, 2026-04-22, 2026-04-23, 2026-04-27) + state/priorities.yaml lines 376–382. Compiled 2026-04-27.
Purpose: clean evidence for the 2026-05-06 routing redesign (see state/routing-redesign-plan.md).

---

## Confirmed misroutes (system tagged X, actually Y)

| Date | Item | System tag | Actual dept | Signal that revealed it |
|------|------|-----------|-------------|-------------------------|
| 2026-04-22 | MSO meeting (11am Raymond/Abid/Ryan) | other/ipa | dock_pro | Aaron's EOD note: "Florida MSO → Piris Health → cardiac pipeline" |
| 2026-04-22 | Dr Andy visit + rates proposal | nestmate | ipa | Aaron's EOD note: "rate proposal + IPA NY letter" |
| 2026-04-22 | MDland 5343 My Care NP | ipa | lab | Aaron's annotation |
| 2026-04-22 | Dr. Alam | ipa | lab | Aaron's annotation |
| 2026-04-22 | Sheila (EMU Health) | other | nestmate | Aaron's annotation |
| 2026-04-22 | Touch base with Cyrus (accounts) | nestmate | ipa | Aaron's EOD note: "context-specific task" |

---

## Ambiguous people (span multiple depts)

| Person | Depts seen | Resolution signal |
|--------|-----------|-------------------|
| Cyrus | nestmate + ipa | Aaron notes task context determines routing (accounts touch-base → ipa; other nestmate contexts unclear) |
| Ilene | nestmate + unknown | Sit-down 2026-04-21 involved "GI client + Article 28 ABBA"; both stored on her side; context variable |
| Ryan | lab + nestmate | Two distinct Ryans: EMU dental supply (nestmate) vs Florida MSO (dock_pro/other) — confirmed separate persons, not ambiguous |

---

## Single-dept aliases (always one department — safe routing)

| Name/keyword | Always routes to | Evidence count |
|--------------|------------------|----------------|
| EMU (Nestmate EMU) | nestmate | 5 references (4/14, 4/15, 4/20, 4/21, 4/22, 4/23) all nestmate-tagged |
| MDland | lab | 1 confirmed (2026-04-22: "MDland for 5343 My Care NP initiated [lab]") |
| Dr Alam | lab | 1 confirmed (2026-04-22 correction, actual lab) |
| Sheila | nestmate | 1 corrected (2026-04-22 was tagged other, actual nestmate) |
| Dr Vamos | ipa | 3 references (4/15, 4/21 completed, 4/22 continuing) all ipa-tagged |
| Dr Adrianova (+ Husband variant) | ipa | 5 references (4/14, 4/15, 4/20, 4/21, 4/22) all ipa-tagged |
| Muhhaned Ali | ipa | 2 references (4/14, 4/15) all ipa-tagged |
| Kader | ipa | 4 references (4/15, 4/16, 4/20, 4/22, 4/23) all ipa-tagged (associated with HPV flyer, United IPA follow-ups) |
| Abid | dock_pro/mso | 3 references (2026-04-20, 2026-04-21, 2026-04-22) all dock_pro-adjacent (Florida MSO partner) |
| Raymond | dock_pro | 1 reference (2026-04-22 "Raymond/Abid/Ryan MSO meeting") dock_pro-tagged |
| Ahmed | lab | 2 references (2026-04-22, 2026-04-23) both lab-tagged (Peptide purity RJ, Derm Percy discussion) |
| Dayo | lab | 1 reference (2026-04-20 completed "Speak with Dayo re: accu") lab-tagged |
| Essen | lab | 2 references (2026-04-21 "Essen call", 2026-04-22 "Essen Apu for julie") lab-tagged |

---

## Parent-task → child-task department mismatches

| Notion parent | Child item | Parent's apparent dept | Child's true dept | Evidence |
|---------------|-----------|------------------------|-------------------|----------|
| DOCPRO clients (implied dock_pro parent) | Dr Remzy Meny outreach | dock_pro | nestmate | 2026-04-20 EOD: "Nestmate outreach: assign dues + owners for 6 carried providers" lists "Remzy Meny" as unassigned; 2026-04-23: "Speak to Anju — Remzy Meny routing [nestmate]" |

---

## Routing decisions Aaron made manually (high-signal)

- **2026-04-22 (morning briefing)**: MSO meeting tagged `[other/ipa]` in briefing, then corrected in EOD to `[dock_pro]` — "Florida MSO → Piris Health → cardiac pipeline"
- **2026-04-22 (EOD)**: Dr Andy visit tagged `[nestmate]` in briefing, corrected to `[ipa]` in EOD — "rate proposal + IPA NY letter"
- **2026-04-22 (EOD)**: Created inline annotations for 5 confirmed misroutes (MDland, Dr Alam, Sheila, Cyrus) without modifying the briefing tags; retained evidence for phase-2 analysis
- **2026-04-20 (EOD)**: Moved "Call Abid and Ryan regarding Florida MSO" from 14:00 to 14:15 after external context (call did not materialize); rescheduled to 2026-04-21 14:15 after confirmed completion
- **2026-04-21 (EOD)**: Completed 3/3 Top 3 outcomes including sit-down with Ilene (context: "GI client + Article 28 ABBA both on her side now")

---

## Open routing questions to resolve on 2026-05-06

- **Cyrus accounts task**: Is "Touch base with Cyrus" a persistent nestmate alias, or does context determine department? If context-driven, what keywords/signals distinguish ipa vs nestmate Cyrus work?
- **Ilene**: Primary department for Ilene sit-downs? GI/pharmacy aspects suggest nestmate-primary, but Article 28 ABBA could indicate ipa adjacency.
- **Two Ryans**: Confirmed separate (EMU dental = nestmate, Florida MSO = dock_pro), but are there naming collisions in calendar/tasks that could auto-tag one incorrectly when referenced without full context?
- **MSO/Piris Health pipeline**: Is "Florida MSO" a dock_pro project that was previously cached as "other/ipa"? Why was it initially tagged other?
- **Dr Andy**: Initial nestmate tag — is this a legacy provider CRM classification that doesn't reflect his actual involvement in IPA rate negotiation?
- **Remzy Meny**: Listed as "Nestmate outreach" in 4/20, but stored under "DOCPRO clients" parent structure. Is the parent misclassified, or is Remzy dual-dept?
- **Parent task classification inheritance**: When a Notion page is nested under a parent department folder (e.g., DOCPRO clients), should child items auto-inherit the parent's department tag, or should they be independently routed? (Current evidence suggests independent routing preferred.)

---

## Summary of routing artifacts by type

### Misroute Density
- **Single day peak**: 2026-04-22 logged 6 misroute observations in one EOD note
- **Frequency over period**: 6 unique misroutes + 1 ambiguous person (Cyrus context-dependent) = **7 routing anomalies** in 8 days
- **Detection method**: All misroutes revealed by Aaron's EOD annotations (daily log **Today's Misroute Evidence** section or inline `[dept]` corrections), not by system alerts

### Safe routing (high confidence)
- **12 single-department aliases** confirmed with 1–5 references each
- **Zero conflicts** among the safe aliases (each name/keyword consistently routed to the same dept across all logs)

### Data quality notes
- **Logs missing**: 2026-04-17, 2026-04-18, 2026-04-19, 2026-04-24, 2026-04-25, 2026-04-26 (no logs written; gaps in daily log sequence)
- **Misroute logging practice**: Aaron manually annotated misroutes in EOD sections without retroactively correcting the briefing-stage tags. This preserves evidence but creates temporary inconsistency in the daily log.
- **Memory drift**: 2026-04-22 EOD notes "CardioPro back-burner memory is partially stale" — indicates memory/cached context can lag behind actual task routing.


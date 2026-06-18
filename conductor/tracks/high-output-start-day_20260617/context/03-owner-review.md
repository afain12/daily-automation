# Gary Tan-Level Owner Review — High Output Start-Day Replacement

## One-line verdict

The proposed replacement is directionally right: it upgrades `/start-day` from a task organizer into a CEO operating system. But to make it truly useful for a multi-business owner, it must become a daily capital-allocation and leverage system, not just a prettier priority list.

## The core upgrade

Current system:

> What tasks exist across Calendar, Notion, Google Tasks, and Obsidian?

Better system:

> Which 3 outputs move enterprise value today, who owns each one, what proof counts as shipped, and what block/delegation action creates movement?

That is the correct shift.

## Multi-business owner framing

Aaron is not managing one team with one roadmap. He is running a portfolio:

- Lincoln Reference Laboratory
- United IPA
- Nestmate
- Dock Pro / Cardio Pro
- plus LabAide / AI ops as leverage infrastructure

So `/start-day` should not act like a personal productivity app. It should act like a daily board meeting with yourself.

Each morning it should answer:

1. Which business has the highest leverage constraint today?
2. Which output would unlock revenue, relationship movement, or execution velocity?
3. What can be delegated or converted into owner/accountability today?
4. What meeting must become a decision or next action?
5. What should deliberately not be worked on?

## What is strong in the current revamp plan

### 1. Moving from tasks to outputs

This is the biggest win.

A task is “call GI Medical.”

An output is:

> GI Medical relationship moved to a clear next operating step with owner/date.

That distinction matters because relationship businesses do not move only through checkboxes. They move through trust, next steps, and commitment.

### 2. Counting delegated field movement

This is essential.

If Ilene/Eileen or another runner visits an office and gets the account one step closer, that is not “not done because Aaron didn’t do it.” That is management output.

Grove lens:

> Aaron’s output = output of Aaron + output of people Aaron influences.

So delegated movement must count as shipped if it moves the client timeline.

### 3. Phone-first 3-output view

Correct.

A multi-business owner cannot wake up to 40 equal-looking items. The first viewport should show exactly 3 primary outputs, then everything else below.

### 4. Shadow-mode rollout

Correct.

Calendar writes are high-risk. First prove the new output layer improves judgment and end-day scoring. Then add calendar blocks.

## Where the plan should be sharpened

### 1. Add a business-portfolio dashboard above the daily output list

Before showing 3 outputs, `/start-day` should show a tiny portfolio status line:

```markdown
## Portfolio Pulse
- Lincoln Lab: revenue/service ops — constraint: dispatch/supply/provider follow-up
- United IPA: growth/network — constraint: provider movement / payer ops
- Nestmate: account buildout — constraint: clinic conversion / follow-up
- Dock/Cardio Pro: rollout — constraint: reps / physician activation

Today's capital allocation: 60% United IPA, 25% Lincoln, 15% admin/follow-up
```

Why: without a portfolio lens, the system may pick the loudest tasks instead of allocating Aaron’s time to the business with the best current return.

### 2. Add “constraint” to every output

Each top output should say what bottleneck it removes.

Example:

```markdown
1. Starling IPA loop closed
   Constraint removed: external decision ambiguity
   Done when: proceed/reschedule/drop decision captured
   Owner: Aaron
   Proof: calendar/task/confirmed outcome
```

This forces the system to think like an owner/operator, not a task assistant.

### 3. Separate operating modes by day type

Aaron has different days:

- Field day
- Office/deep work day
- Meeting-heavy day
- Firefighting day
- Admin catch-up day

`/start-day` should classify the day before selecting outputs.

Example:

```markdown
Day mode: Field / Relationship Movement
Primary success metric: account/provider timeline movement
Calendar strategy: capture blocks after field visits, not deep-work blocks
```

This prevents the system from suggesting unrealistic deep work on a field day.

### 4. Add a “kill / defer / delegate” lane

Gary Tan-style operator thinking is not just “what should I do?” It is also “what should I stop doing?”

Every morning should include:

```markdown
## Kill / Defer / Delegate
- Kill: stale item that no longer matters
- Defer: not this week, no active constraint
- Delegate: runner can move this without Aaron
```

This is where 10x management happens: freeing Aaron from the wrong work.

### 5. Treat meetings as conversion events

Meetings should be measured by conversion:

- no decision → weak meeting
- decision made → good
- owner/date assigned → better
- delegated follow-up created → best
- revenue/account relationship moved → highest value

`/end-day` should ask:

```markdown
Which meetings converted into decisions, delegated work, or revenue/account movement?
```

### 6. Add weekly learning loop later

Daily output scoring is useful, but weekly review should identify patterns:

- Which business consumed the most time?
- Which business produced movement?
- Which meetings repeatedly fail to convert?
- Which runner creates most delegated movement?
- Which outputs get carried 3+ days and should be killed/delegated?

This turns COO Twin into an operating system, not a daily checklist.

## Recommended `/start-day` top section

```markdown
# Daily Command Brief — YYYY-MM-DD

## Portfolio Pulse
- Day mode: Field / Deep Work / Meeting-heavy / Firefight / Admin
- Highest leverage business today: United IPA
- Main constraint: provider/account decision ambiguity
- Time allocation: 60% IPA, 25% Lincoln, 15% admin

## Today — Ship These 3
1. **Output A**
   Business: United IPA
   Constraint removed: external decision ambiguity
   Done when: agreement/proceed/drop captured
   Owner: Aaron / Runner / External
   Proof: Aaron confirmed / CRM note / task done
   Next block: 9:20–9:45 Command Review

2. **Output B**
   Business: Lincoln
   Constraint removed: dispatch/supply loop owner unclear
   Done when: owner/date assigned and message/task created
   Proof: sent/task/status update
   Next block: 10:30–10:50 Delegation Pass

3. **Output C**
   Business: Nestmate / Dock Pro
   Constraint removed: account timeline stuck
   Done when: runner outcome captured or next visit set
   Proof: runner note / task / CRM update
   Next block: field window + capture block

## Kill / Defer / Delegate
- Kill:
- Defer:
- Delegate:

## Meetings That Must Convert
- Meeting X → required output: decision / owner / next action
```

## Recommended scoring model

Do not score only by due date.

Score by owner leverage:

| Signal | Points |
|---|---:|
| Removes a constraint in a priority business | +5 |
| Moves revenue/account/provider relationship | +4 |
| Delegates work that can move without Aaron | +4 |
| Converts meeting into decision/owner/date | +3 |
| Creates reusable system/SOP/integration | +3 |
| Due today / overdue | +2 |
| Prevents stream starvation | +1 |
| Admin/personal | cap at 3 unless urgent |

## Recommendation on implementation

Keep the current safe rollout plan, but add one more artifact first:

`portfolio_pulse` helper.

First build slice should become:

1. `scripts/output_planning.py`
2. `tests/test_output_planning.py`
3. `PortfolioPulse` object
4. `DailyOutput` object
5. shadow-only rendering
6. old Top 3 preserved exactly
7. no calendar writes

## What success should feel like

A successful morning brief should make Aaron think:

> “I know the 3 things that move the businesses today, who owns them, and what counts as movement. Everything else is below the line.”

A successful end-day should answer:

> “Did enterprise value move today, or did we just organize tasks?”

## Final verdict

The revamp is strong. The next improvement is to make it more owner-level:

- portfolio pulse first,
- 3 outputs only,
- constraint removed per output,
- delegation counted as real output,
- meetings measured by conversion,
- kill/defer/delegate as a daily lane,
- calendar blocks only after shadow mode proves the judgment layer.

This is the difference between a task system and a CEO operating cadence.

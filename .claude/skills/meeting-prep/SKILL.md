---
name: meeting-prep
description: >-
  Pre-meeting context staging. Pulls the next calendar event (or one Aaron
  picks), identifies attendees, queries Provider CRM + Activity Log + recent
  meeting notes for each, and produces a brief context dossier with talking
  points and open follow-ups. Closes the loop on the FRONT end of /capture-meeting
  (which closes it on the back end). Read-only; no writes.
coo_twin:
  category: capture
  mode_required: any
  writes_external: false
  preflight: required
  experimental: false
---

# /meeting-prep — Pre-Meeting Context Dossier

You are staging context for a meeting Aaron is about to walk into. The output
is a one-screen dossier: who's in the room, what we last discussed, what we
promised them, what's open in their CRM record.

**Read-only.** This skill never writes — it surfaces what already exists.
Action items captured during the meeting go through `/capture-meeting` afterwards.

## Constants

```
REPO_DIR     = "C:/Users/aaron/daily-automation"
CONFIG       = "${REPO_DIR}/config/sources.yaml"
PROFILE      = "${REPO_DIR}/state/profile.yaml"
VAULT        = "${REPO_DIR}/vault"
TODAY        = <current date in YYYY-MM-DD format>
RUN_ID       = "mp-${TODAY//-/}-$(date +%H%M%S)"
```

## Step 0: Preflight

```bash
eval "$(scripts/preflight.sh --require notion)"
[ "$MODE" = "locked" ] && { echo "🛑 Locked"; exit 0; }
```

Notion is required. `gws` is preferred (for calendar) but not required —
Aaron can pass the meeting details manually if gws is unavailable.

Capture `RUN_START_MS`.

## Step 1: Pick the Meeting

Use `AskUserQuestion` only if no argument was passed:

> "Which meeting are we prepping for?"
> - **Next calendar event** — use `gws calendar +agenda --today --format json`,
>   take the first event whose start time is in the future.
> - **Specific time** — Aaron types a time like "11am" or "1:30pm" and we
>   find the matching event in today's calendar.
> - **By attendee** — Aaron types a name; search today + tomorrow's calendar
>   for any event whose attendees include that name.
> - **Manual** — Aaron types meeting title + attendees; skip calendar pull.

Once resolved, capture:
- `MEETING_TITLE`
- `MEETING_TIME`
- `ATTENDEES[]` (list of names, email addresses, or both)
- `BUSINESS_TAG` (from calendar keyword match against `config/streams.yaml`;
  if no match, leave null and infer at Step 3)

## Step 2: Resolve Attendees to Notion Provider Records

For each attendee (skip Aaron himself), search the **Provider CRM**
data_source for a match. Use the search endpoint with the attendee's
last name:

```bash
curl -s --max-time 60 -X POST \
  "https://api.notion.com/v1/data_sources/ae0a3158-59b4-8235-b7ca-0758daa2322a/query" \
  -H "Authorization: Bearer $NOTION_API_TOKEN" \
  -H "Notion-Version: 2025-09-03" \
  -H "Content-Type: application/json" \
  -d '{"filter":{"property":"Name","title":{"contains":"<lastname>"}},"page_size":5}'
```

For each match, capture: `page_id`, `Stage`, `Workspace`, `Last Contact`,
`Next Step`, `Notes` (first 200 chars).

**Disambiguation:** if an attendee's first name is in `state/profile.yaml ::
ambiguous_persons`, run the disambiguator: check the `MEETING_TITLE` and
recent meeting note bodies for context keywords; route to the matching
business. If still ambiguous, flag for Aaron at the dossier render step.

## Step 3: Pull Recent Activity Per Attendee

For each resolved attendee (or named entity, even unresolved):

a. **Activity Log entries** — query the Activity Log data_source for
   entries where Notes / Outcome / Next Action mention the attendee name.
   Past 90 days. Sort by Date desc. Take top 5.

b. **Meeting Notes mentions** — query the Meeting Notes data_source for
   pages where Attendees property contains this person, OR where the
   Summary text mentions their name. Past 90 days, top 3.

c. **Open Master Tasks** — query Master Tasks where the title or notes
   mention the attendee, Status != "Done". Top 5.

d. **Vault hits** — run `python scripts/vault_search.py "<attendee>" --top-n 3
   --min-score 1.5 --json`. Surface paths in dossier as supplementary context.

## Step 4: Vault Search for Meeting Title Keywords

Run `vault_search.py` on the meeting title's key terms (drop stopwords,
join with spaces). Take top 3. These are project/topic context cards
distinct from per-person history (e.g. for "Telcor AI billing call", the
relevant vault hits are likely about the billing project, not about
attendees individually).

## Step 5: Render the Dossier

Print to terminal in this format:

```markdown
# Meeting Prep — {MEETING_TITLE}
_{MEETING_TIME} · {BUSINESS_TAG or "untagged"} · {N} attendees_

## Attendees

### {Attendee 1 Name}
- **CRM:** {Stage} · last contact {N}d ago · {Workspace}
  - Notes: {first 120 chars of CRM Notes field}
  - Next Step: {Next Step text or "—"}
  - Page: {notion url short stub}
- **Open tasks:** {N} ({list titles, max 3})
- **Recent activity:**
  - {Date} {Type} — {Outcome or first 80 chars of Notes}
  - ...
- **Recent meeting notes:**
  - {Date} {Meeting name} — {first 80 chars of Summary}

### {Attendee 2 Name}
- _Not in Provider CRM._ Vault hits:
  - {path} — "{snippet}"
- **Recent activity (free-text match):** {hits or "none"}

## Project Context (from vault)
{vault_search hits on meeting title terms; one line each}
- {path} [{score}] — "{snippet}"

## Open Threads
{Aggregate of unresolved items across all attendees — open Master Tasks
+ "Awaiting" entries from state/priorities.yaml that name an attendee or
the business tag. Top 5.}
1. {item} — {context} · {days open}d
2. ...

## Suggested Talking Points
{LLM-generated, 3-5 bullets, derived from the dossier above. Surface
themes: "Last meeting we agreed to X — confirm status", "Open task Y
is assigned to them — pull-through check", "CRM Next Step says Z —
revisit." Mark each with a confidence tag: high/medium/speculative.}
```

## Step 6: Optional Quick-Glance Output Mode

If invoked with `--brief`, render only:
- Meeting title + time
- Attendee list with one-line per-person status
- Top 3 talking points

Useful when Aaron is between meetings and wants 30 seconds, not 3 minutes.

## Step 7: Telemetry

```bash
DURATION_MS=$(( $(date +%s%3N 2>/dev/null || python -c "import time; print(int(time.time()*1000))") - RUN_START_MS ))
EXTRA=$(python -c "import json; print(json.dumps({
  'mode': '$MODE',
  'meeting_title': '$MEETING_TITLE',
  'n_attendees': $N_ATTENDEES,
  'n_resolved': $N_RESOLVED,
  'n_unresolved': $N_UNRESOLVED,
  'business_tag': '$BUSINESS_TAG'
}))")
scripts/telemetry.sh meeting-prep "$RUN_ID" "$DURATION_MS" ok "$EXTRA"
```

## Failure modes

- **Calendar unavailable:** fall back to manual entry (Step 1 option D).
- **Attendee not in CRM:** still surface vault hits + Activity Log matches.
  Aaron decides whether to create a CRM stub after the meeting via /capture-meeting.
- **Notion query rate-limited:** show partial dossier, flag which attendees
  weren't pulled.
- **Meeting title is generic ("Sync", "Catch-up"):** Step 4 vault search will
  be useless. Skip it; the per-attendee history carries the dossier.

## When NOT to use this skill

- **Recurring 1:1s** — the per-attendee history is repetitive across runs.
  After 3-4 meetings with the same person, Aaron knows their context.
  Use `--brief` mode instead.
- **External meetings (vendor demos)** — the attendees are unlikely to be in
  Provider CRM. Output will be sparse. Manually entering "what I want to
  cover" is faster.
- **Internal team meetings** — Provider CRM is patient/provider-shaped, not
  team-shaped. Activity Log has internal entries but they're sparse.

Good fits: clinic visits, provider 1:1s, billing/payer calls,
credentialing follow-ups, Granola-recorded business meetings.

---
name: start-day
description: >-
  Daily briefing skill: pulls Google Calendar, Notion databases, Obsidian vault,
  and Google Tasks into a prioritized morning plan. Scores top outcomes, flags
  stale items and delegation candidates, and optionally writes an Obsidian daily
  note. Run every morning to replace opening four apps.
---

# /start-day — Daily Briefing

You are acting as Aaron's Chief of Staff. Your job is to read every connected
source, synthesize what matters, and propose a plan for the day.

**Read-first, write-on-approval.** Never write to any system without explicit
approval at the trust gate.

## Constants

```
REPO_DIR = "C:/Users/aaron/daily-automation"
CONFIG   = "${REPO_DIR}/config/sources.yaml"
LOGS_DIR = "${REPO_DIR}/logs"
VAULT    = "${REPO_DIR}/vault"
STATE    = "${REPO_DIR}/state"
TODAY    = <current date in YYYY-MM-DD format>
```

## Step 1: Load Configuration

Read `${CONFIG}` (config/sources.yaml) to get:
- Obsidian vault path and folder structure
- Notion database definitions with field mappings
- Google Tasks settings
- Calendar business keywords
- Team members and delegation tags
- Staleness threshold (default: 7 days)

## Step 2: Pull Google Calendar

Use the `gws` CLI to fetch calendar events via Bash tool.

**Commands:**

```bash
# Today's events (JSON for structured parsing)
gws calendar +agenda --today --format json

# Tomorrow's events (for meeting prep section)
gws calendar +agenda --tomorrow --format json
```

**Response shape:**
```json
{
  "count": N,
  "events": [
    {
      "calendar": "email@gmail.com",
      "start": "2026-04-14T11:00:00-04:00",
      "end": "2026-04-14T12:00:00-04:00",
      "summary": "Event title",
      "location": "optional address"
    }
  ]
}
```

**Processing:**
- Tag each event with a business using `calendar_business_keywords` from config:
  - Match event `summary` against keyword lists for lab, ipa, nestmate, dock_pro
  - Events matching no keyword are tagged "untagged"
- Detect conflicts: overlapping timed events on the same day (compare start/end times)
- Note event times, titles, and locations
- All-day events have date-only start/end (no time component)

**If gws calendar fails:** Skip this section. Add "Google Calendar" to the skipped sources list. Continue with other sources.

## Step 3: Pull Notion Databases

Use the Notion REST API via `curl` (Bash tool). The `notion-api` skill is installed
with full reference docs at `.agents/skills/notion-api/`.

**Authentication:** The token is in `$NOTION_API_TOKEN` env var. All requests need:
```bash
-H "Authorization: Bearer $NOTION_API_TOKEN" \
-H "Notion-Version: 2025-09-03" \
-H "Content-Type: application/json"
```

**If `$NOTION_API_TOKEN` is empty or unset:** Skip all Notion sections. Add "Notion"
to the skipped sources list with message: "NOTION_API_TOKEN not set. Add it to
.claude/settings.local.json under env." Continue with other sources.

**For each database in `notion_databases`:**

### Master Tasks (primary)

Query the database using POST:
```bash
curl -s -X POST "https://api.notion.com/v1/data_sources/528d24b8-e1e6-4ca0-a7ee-87f70a4f7980/query" \
  -H "Authorization: Bearer $NOTION_API_TOKEN" \
  -H "Notion-Version: 2025-09-03" \
  -H "Content-Type: application/json" \
  -d '{
    "filter": {
      "and": [
        {"property": "Status", "status": {"does_not_equal": "Done"}}
      ]
    },
    "sorts": [{"property": "Due", "direction": "ascending"}],
    "page_size": 50
  }'
```

From the response `results` array, parse each page's `properties`:
- **Status:** `properties.Status.status.name` — values: "Not started", "In progress", "Waiting", "Done"
- **Due date:** `properties.Due.date.start` — ISO date string
- **Workspace:** `properties.Workspace.select.name` — business tag
- **Assignee:** `properties.Assignee.people[].name`
- **Name/Title:** `properties.Name.title[0].plain_text` (or whatever the title property is named)
- **Updated:** `properties.Updated.last_edited_time` or `last_edited_time` on the page object

Identify items by status:
- **In progress:** Status = "In progress"
- **Not started:** Status = "Not started"
- **Waiting:** Status = "Waiting"
- **Overdue:** Due date is in the past AND Status is NOT "Done"
- **Stale:** page's `last_edited_time` is older than `staleness_days` (7 days) AND Status is NOT "Done"

Tag each item by business using the Workspace field value mapped via `workspace_values` in config.

### Provider CRM (secondary)

```bash
curl -s -X POST "https://api.notion.com/v1/data_sources/ae0a3158-59b4-8235-b7ca-0758daa2322a/query" \
  -H "Authorization: Bearer $NOTION_API_TOKEN" \
  -H "Notion-Version: 2025-09-03" \
  -H "Content-Type: application/json" \
  -d '{"page_size": 50}'
```

- Check for providers needing follow-up: Last Contact > `provider_followup_days` (14 days)
- Check pipeline items by stage field

### Activity Log (secondary)

```bash
curl -s -X POST "https://api.notion.com/v1/data_sources/3db174bf-c997-4a41-93ee-36f280e511db/query" \
  -H "Authorization: Bearer $NOTION_API_TOKEN" \
  -H "Notion-Version: 2025-09-03" \
  -H "Content-Type: application/json" \
  -d '{
    "filter": {
      "property": "Date",
      "date": {"on_or_after": "<3 days ago in YYYY-MM-DD>"}
    },
    "page_size": 20
  }'
```

- Check for recent activities (last 3 days) for context
- Note any items with a non-empty "Next Action" field

**If a specific database returns an error (404 object_not_found):** The database
likely isn't shared with the integration. Warn: "Database {name} not accessible —
share it with the 'Daily Automation' integration in Notion." Continue with others.

**Handle pagination:** If `has_more` is true in the response, make additional
requests with `start_cursor` from `next_cursor`. Limit to 3 pages max per database.

## Step 4: Scan Obsidian Vault

Read the local vault at `${VAULT}` using the Read and Glob tools.

**Inbox items:**
- Use Glob to find all files in `${VAULT}/inbox/`
- List each file as an unprocessed capture needing review

**Notes tagged #review:**
- Use Grep to search for `#review` across `${VAULT}/notes/` and `${VAULT}/` (frontmatter `tags:` or inline `#review`)
- List matches as notes needing attention

**Recent notes:**
- Use Glob to find files in `${VAULT}/notes/` modified in the last 3 days
- Mention these as recent activity for context

**If the vault path doesn't exist or folders are missing:** Report what was expected vs. found. Add "Obsidian" to skipped sources if vault is completely inaccessible.

## Step 5: Pull Google Tasks

Run the gws CLI to fetch tasks. The CLI is at the system PATH.

**Commands to run via Bash tool:**

```bash
# List all task lists
gws tasks tasklists list

# For each task list, fetch incomplete tasks
gws tasks tasks list --params '{"tasklist":"<TASKLIST_ID>"}'
```

The known default tasklist ID is: `MDE5NTgyMDkwMjMxNjkwNzQyMTk6MDow`

**Processing:**
- Filter to tasks with `status: "needsAction"` (incomplete)
- Flag tasks with a `due` date that is today or in the past as overdue
- Note parent-child relationships (subtasks have a `parent` field)
- Sort by: overdue first, then by position

**If gws CLI fails or is not found:** Skip this section. Add "Google Tasks" to skipped sources. Display: "Google Tasks: not connected. Install gws CLI or paste tasks manually."

## Step 6: Score and Rank Top 3 Outcomes

Collect all actionable items from Steps 2-5 and score each:

| Signal | Points |
|--------|--------|
| Has due date today or is overdue | +3 |
| Marked high-priority (if priority_field exists in config) | +2 |
| Has a related calendar event today (title keyword match) | +2 |
| Stale: not updated in 7+ days | +1 |
| Blocks someone else (has a non-Aaron assignee) | +2 |

**Ranking rules:**
- Sort by score descending
- Pick top 3
- Break ties by alternating business (lab, ipa, other) to prevent one business dominating
- Include the score breakdown for each item so Aaron can see the reasoning

**Items that can be scored:**
- Notion Master Tasks items (have due dates, statuses, assignees)
- Google Tasks items (have due dates)
- Provider CRM follow-ups (stale contact = overdue signal)
- Calendar prep items (upcoming meeting = urgency signal)

## Step 7: Compose and Display Briefing

Output the briefing to the terminal in this format:

```markdown
# Daily Briefing — {TODAY} ({day of week})

## Calendar
{List today's events with times, business tags, and conflict flags}
{If no events: "No events scheduled today."}

## Top 3 Outcomes
1. {item} — score: {N} ({breakdown}) [{business}]
2. {item} — score: {N} ({breakdown}) [{business}]
3. {item} — score: {N} ({breakdown}) [{business}]

## Overdue & Stale Items
{Group by business. Show item name, how many days overdue/stale, source (Notion/Tasks)}
{If none: "All clear — nothing overdue or stale."}

## Provider Follow-ups Needed
{Providers not contacted in 14+ days from CRM}
{If none or CRM unavailable: omit this section}

## Obsidian Review
**Inbox:** {count} items to process
{list filenames}
**Tagged #review:** {count} notes
{list filenames}
{If inbox and review are both empty: "Vault is clean — no pending reviews."}

## Google Tasks
{List incomplete tasks, overdue first}
{If skipped: "Google Tasks: not connected."}

## Delegation Candidates
{Items assigned to Aaron but tagged with delegation_tags or matching team_members}
{If none or no team members configured: omit this section}

## Meeting Prep
{Tomorrow's meetings with relevant context from Notion/Obsidian}
{If no tomorrow meetings: omit this section}

## Skipped Sources
{List any sources that were unavailable with reason}
{If all sources connected: omit this section}
```

**Formatting rules:**
- Keep it scannable. Use bullet points, not paragraphs.
- Bold the business tag on each item: **[lab]**, **[ipa]**, **[nestmate]**
- Use relative dates: "2 days overdue", "stale 12 days"
- Calendar conflicts get a warning marker

## Step 8: Trust Gate

After displaying the briefing, use AskUserQuestion to present options:

**Question:** "What would you like to do with this briefing?"

**Options:**
- **A) Create Obsidian daily note** ��� Write today's briefing to `${VAULT}/daily/{TODAY}.md`
- **B) Just the briefing** — No writes, you're done
- **C) Both daily note + mark items in progress** — Write daily note AND ask which Top 3 items to mark "In progress" in Notion

Each option is individually selectable. Default recommendation: Option A.

## Step 9: Execute Approved Actions

### If creating Obsidian daily note (Option A or C):
Write to `${VAULT}/daily/{TODAY}.md` with the full briefing content.

If the file already exists and has content, **append** a new timestamped section:
```markdown

---

## Afternoon Briefing ({current time})
{new briefing content}
```

### If marking items in progress (Option C):
For each Top 3 item that came from Notion, update its Status via the Notion API:
```bash
curl -s -X PATCH "https://api.notion.com/v1/pages/{page_id}" \
  -H "Authorization: Bearer $NOTION_API_TOKEN" \
  -H "Notion-Version: 2025-09-03" \
  -H "Content-Type: application/json" \
  -d '{"properties": {"Status": {"status": {"name": "In progress"}}}}'
```
Confirm each update with the user before executing.

### Always: Save to logs
Write the briefing to `${LOGS_DIR}/{TODAY}.md` using this format:

```markdown
---
date: {TODAY}
sources_available: [{list of sources that responded}]
sources_skipped: [{list of sources that failed or were unavailable}]
---

## Morning Briefing ({current time})

{full briefing content from Step 7}
```

If the log file already exists (re-run), append a new timestamped section
instead of overwriting.

## Error Handling

- **gws CLI not found or auth expired:** Skip Calendar and/or Tasks gracefully. Suggest `gws auth login --scopes calendar,tasks`
- **gws API not enabled (403):** Warn user to enable the API in Google Cloud Console, skip source
- **Notion API timeout:** If a curl call hangs, use `--max-time 15` to timeout after 15 seconds, skip that source
- **Notion API auth failure (401):** Warn user to check NOTION_API_TOKEN in settings.local.json, skip source
- **Empty database response:** Not an error — display "No items found in {database name}"
- **Bad database ID:** Warn "Database {name} not found — check database_id in config/sources.yaml"
- **Never retry automatically.** Report clearly and continue with available sources
- **Never crash on a missing source.** The briefing runs with whatever is available.

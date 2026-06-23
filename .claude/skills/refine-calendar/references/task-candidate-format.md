# Refine Calendar task-candidate file format

Use this optional JSON input when `/refine-calendar` should fill large open gaps with high-value tasks beyond the daily note's `Ship These 3`.

The file is preview-only input. It does not write to Notion, Google Tasks, or Calendar by itself.

## CLI usage

```bash
python3 scripts/refine_calendar.py \
  --date "$(date +%F)" \
  --mode "$MODE" \
  --task-candidates-json .context/preview/task-candidates-$(date +%F).json
```

With a calendar fixture for tests:

```bash
python3 scripts/refine_calendar.py \
  --date 2026-06-22 \
  --mode draft \
  --calendar-json /tmp/calendar.json \
  --task-candidates-json /tmp/task-candidates.json
```

## JSON schema

```json
{
  "intent": "refine-calendar-task-candidates",
  "date": "2026-06-22",
  "generated_at": "2026-06-22T08:30:00-04:00",
  "source": "notion-attention-subsets",
  "tasks": [
    {
      "title": "High-value provider subset follow-up",
      "workspace": "Lincoln Lab",
      "subset": "provider-followups",
      "attention_pct": 45,
      "value_score": 90,
      "status": "Not started",
      "due": "2026-06-22",
      "done_when": "provider next step is scheduled",
      "source_refs": [{"system": "notion", "id": "task-high"}]
    }
  ]
}
```

## Field rules

Required per task:
- `title`: task title to show in the calendar block.

Recommended:
- `workspace`: Lincoln Lab, United IPA, Nestmate, Dock Pro, Other.
- `subset`: small high-value bucket, e.g. `provider-followups`, `dispatch-risk`, `sales-replies`, `waiting-on-aaron`, `today-overdue`.
- `attention_pct`: how much attention this subset should get today. Higher wins.
- `value_score`: tie-breaker inside similar attention percentages. Higher wins.
- `done_when`: concrete finish condition.
- `source_refs`: grounding refs; prefer `[{"system":"notion","id":"..."}]` or `[{"system":"gtask","id":"..."}]`.

Fallback refs:
- `notion_id` becomes a Notion source ref.
- `gtask_id` becomes a Google Tasks source ref.
- If no source exists, the task is marked `[derived]`.

## Sorting behavior

`refine_calendar.py` keeps daily-note `Ship These 3` first, then appends candidate tasks sorted by:

1. `attention_pct` descending
2. `value_score` descending

Duplicate titles are skipped. The merged output list is capped at 12 candidates before scheduling.

## Scheduling behavior

- Deep-work days can schedule these as normal `FOCUS` blocks.
- Field days only use them when there is a massive gap, controlled by `field_focus_min_window_min` in `config/calendar.yaml`.
- Calendar remains a commitment layer, not a task mirror: only tasks that fit protected output time become blocks.

## Suggested Notion subset scoring

Use small, high-signal subsets rather than dumping the whole Master Tasks database:

- `today-overdue`: due today/overdue, not Done.
- `waiting-on-aaron`: tasks blocked on Aaron response/decision.
- `provider-followups`: Provider CRM / Lincoln follow-ups likely to move revenue.
- `dispatch-risk`: pickup/supply/ops tasks that affect customer timelines.
- `relationship-next-step`: tasks attached to lunches/dinners/meetings happening today.
- `sales-replies`: inbound replies that can convert or unblock.

A practical first scoring formula:

```text
attention_pct = normalized daily strategic attention for the subset
value_score = urgency + revenue/leverage + unblock count + due-date pressure
```

Then only pass the top 5–12 rows into `/refine-calendar`.

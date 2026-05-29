"""Derive canonical field mappings from a probed Notion data source.

Input: a single data source schema (the same shape `notion_probe_score.py`
ingests) + a role assignment. Output: a YAML-friendly dict matching the
shape used in `config/sources.yaml`.

Standalone helper — call from `/notion-map` once a role candidate has been
picked by the probe.
"""
import json
import sys
from typing import Any

DONE = {"done", "complete", "completed", "closed"}
INPROGRESS = {"in progress", "doing", "working"}
WAITING = {"waiting", "blocked", "on hold"}
NOTSTARTED = {"not started", "to do", "todo", "new", "backlog"}


def find_prop(props, want_types=None, name_contains=None):
    """First property matching type set and name substring (case-insensitive).

    `name_contains` is treated as a priority-ordered list: the first keyword
    that matches ANY property wins, scanning all props for that keyword before
    moving to the next. This matters when a DB has both "Workspace" and
    "Category" selects — "workspace" listed first should win regardless of
    Notion's property iteration order.
    """
    if want_types:
        typed = [p for p in props if p["type"] in want_types]
    else:
        typed = list(props)
    if not name_contains:
        return typed[0] if typed else None
    for kw in name_contains:
        for p in typed:
            if kw in p["name"].lower():
                return p
    return None


def find_all_props(props, want_types=None, name_contains=None):
    out = []
    for p in props:
        if want_types and p["type"] not in want_types:
            continue
        if name_contains:
            n = p["name"].lower()
            if not any(w in n for w in name_contains):
                continue
        out.append(p)
    return out


def options_matching(prop, word_set):
    if not prop:
        return []
    return [o for o in prop.get("options", []) if o.lower() in word_set]


def map_master_tasks(ds):
    props = ds["properties"]
    out = {
        "name": ds["title"],
        "data_source": f"collection://{ds['id']}",
    }
    status = find_prop(props, ["status"]) or find_prop(props, ["select"], None)
    # If we picked a generic select, only keep it if its options look task-like.
    if status and status["type"] == "select":
        opts_lower = {o.lower() for o in status.get("options", [])}
        if not (opts_lower & (DONE | INPROGRESS | NOTSTARTED)):
            status = None
    if status:
        out["status_field"] = status["name"]
        out["status_done_values"] = options_matching(status, DONE) or None
        out["status_in_progress_values"] = options_matching(status, INPROGRESS) or None
        out["status_waiting_values"] = options_matching(status, WAITING) or None
        out["status_not_started_values"] = options_matching(status, NOTSTARTED) or None

    due = find_prop(props, ["date"], ["due", "deadline", " by ", "target"])
    if not due:
        due = find_prop(props, ["date"])  # fallback to first date
    if due:
        out["date_field"] = due["name"]

    assignee = find_prop(props, ["people"], ["assignee", "owner", "responsible"])
    if not assignee:
        assignee = find_prop(props, ["people"])
    if assignee:
        out["assignee_field"] = assignee["name"]

    ws = find_prop(props, ["select", "multi_select"],
                   ["workspace", "project", "category", "area", "department"])
    if ws:
        out["workspace_field"] = ws["name"]
        # Surface the option list — /setup uses this to ask "which option maps to which stream?"
        out["workspace_values_raw"] = ws.get("options", [])

    last_activity = find_prop(props, ["rich_text", "last_edited_time"],
                              ["last activity", "activity", "last touched"])
    if last_activity:
        out["last_activity_field"] = last_activity["name"]

    updated = find_prop(props, ["last_edited_time"])
    if updated:
        out["updated_field"] = updated["name"]

    return _strip_none(out)


def map_provider_crm(ds):
    props = ds["properties"]
    out = {
        "name": ds["title"],
        "data_source": f"collection://{ds['id']}",
    }
    stage = find_prop(props, ["select", "status"], ["stage", "pipeline"])
    if not stage:
        stage = find_prop(props, ["select", "status"], ["status"])
    if stage:
        out["stage_field"] = stage["name"]
        out["stage_options_raw"] = stage.get("options", [])

    last_contact = find_prop(props, ["date"], ["last contact", "contact", "last touch", "last activity"])
    if last_contact:
        out["last_contact_field"] = last_contact["name"]

    next_step = find_prop(props, ["rich_text"], ["next", "step", "action", "todo"])
    if next_step:
        out["next_step_field"] = next_step["name"]

    ws = find_prop(props, ["select", "multi_select"],
                   ["workspace", "project", "category", "area", "department"])
    if ws:
        out["workspace_field"] = ws["name"]
        out["workspace_values_raw"] = ws.get("options", [])

    return _strip_none(out)


def map_activity_log(ds):
    props = ds["properties"]
    out = {
        "name": ds["title"],
        "data_source": f"collection://{ds['id']}",
    }
    type_field = find_prop(props, ["select", "multi_select"],
                           ["type", "kind", "channel"])
    if type_field:
        out["type_field"] = type_field["name"]
        out["type_values_raw"] = type_field.get("options", [])

    date_field = find_prop(props, ["date"])
    if date_field:
        out["date_field"] = date_field["name"]

    outcome = find_prop(props, ["rich_text"], ["outcome", "result"])
    if outcome:
        out["outcome_field"] = outcome["name"]

    next_action = find_prop(props, ["rich_text"], ["next", "action", "follow"])
    if next_action:
        out["next_action_field"] = next_action["name"]

    ws = find_prop(props, ["select", "multi_select"],
                   ["workspace", "project", "category", "area", "department"])
    if ws:
        out["workspace_field"] = ws["name"]
        out["workspace_values_raw"] = ws.get("options", [])

    return _strip_none(out)


def map_meeting_notes(ds, master_tasks_ds_id=None):
    props = ds["properties"]
    out = {
        "name": ds["title"],
        "data_source": f"collection://{ds['id']}",
    }
    title = find_prop(props, ["title"])
    if title:
        out["title_field"] = title["name"]

    date_field = find_prop(props, ["date"])
    if date_field:
        out["date_field"] = date_field["name"]

    summary = find_prop(props, ["rich_text", "formula"],
                        ["summary", "recap", "transcript"])
    if summary:
        out["summary_field"] = summary["name"]

    attendees = find_prop(props, ["people"], ["attendee", "participant", "with"])
    if not attendees:
        attendees = find_prop(props, ["people"])
    if attendees:
        out["attendees_field"] = attendees["name"]

    ws = find_prop(props, ["select", "multi_select"],
                   ["workspace", "project", "category", "area", "department"])
    if ws:
        out["workspace_field"] = ws["name"]
        out["workspace_values_raw"] = ws.get("options", [])

    # Find relation -> master tasks if known
    if master_tasks_ds_id:
        for p in props:
            if p["type"] == "relation" and p.get("relation_data_source_id") == master_tasks_ds_id:
                out["related_tasks_field"] = p["name"]
                break

    return _strip_none(out)


def _strip_none(d):
    return {k: v for k, v in d.items() if v is not None}


ROLE_MAPPERS = {
    "master_tasks": map_master_tasks,
    "provider_crm": map_provider_crm,
    "activity_log": map_activity_log,
    "meeting_notes": map_meeting_notes,
}


def map_role(ds: dict, role: str, master_tasks_ds_id: str | None = None) -> dict:
    if role not in ROLE_MAPPERS:
        raise ValueError(f"unknown role: {role}")
    if role == "meeting_notes":
        return map_meeting_notes(ds, master_tasks_ds_id=master_tasks_ds_id)
    return ROLE_MAPPERS[role](ds)


def main():
    """CLI: --schemas <jsonl> --assignments role=ds_id ...

    Example:
      python notion_field_map.py --schemas state/tmp/np-...-schemas.jsonl \\
        master_tasks=528d24b8-... provider_crm=ae0a3158-...
    """
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--schemas", required=True, help="JSONL of normalized data source schemas")
    ap.add_argument("assignments", nargs="+",
                    help="role=ds_id pairs (master_tasks, provider_crm, activity_log, meeting_notes)")
    args = ap.parse_args()

    schemas = {}
    with open(args.schemas, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            ds = json.loads(line)
            schemas[ds["id"]] = ds

    assignments = {}
    for pair in args.assignments:
        role, ds_id = pair.split("=", 1)
        assignments[role] = ds_id

    master_tasks_ds_id = assignments.get("master_tasks")
    output = {}
    for role, ds_id in assignments.items():
        if ds_id not in schemas:
            print(f"WARNING: ds_id {ds_id} not found in schemas (role {role})", file=sys.stderr)
            continue
        output[role] = map_role(schemas[ds_id], role, master_tasks_ds_id=master_tasks_ds_id)

    json.dump(output, sys.stdout, indent=2, ensure_ascii=False)


if __name__ == "__main__":
    main()

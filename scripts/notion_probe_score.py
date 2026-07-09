"""Score data sources against canonical roles per notion-probe SKILL.md rubric.

Reads schemas JSONL on stdin, writes scored report JSON on stdout.
"""
import json, sys, datetime

DONE_WORDS = {"done", "complete", "completed", "closed"}
INPROGRESS_WORDS = {"in progress", "doing", "working"}
NOTSTARTED_WORDS = {"not started", "to do", "todo", "new"}

def title_contains(title, words):
    t = title.lower()
    return any(w in t for w in words)

def prop_name_contains(props, types_filter, words):
    for p in props:
        if types_filter and p["type"] not in types_filter:
            continue
        if any(w in p["name"].lower() for w in words):
            return True
    return False

def has_type(props, t):
    return any(p["type"] == t for p in props)

def has_select_with_options(props, opts):
    opt_set = {o.lower() for o in opts}
    for p in props:
        if p["type"] in ("select", "status", "multi_select"):
            for o in p.get("options", []):
                if o.lower() in opt_set:
                    return True
    return False

def days_since(iso):
    if not iso: return 999
    try:
        dt = datetime.datetime.fromisoformat(iso.replace("Z", "+00:00"))
        return (datetime.datetime.now(datetime.timezone.utc) - dt).days
    except Exception:
        return 999

def score_master_tasks(ds):
    props = ds["properties"]
    title = ds["title"]
    fired, score = [], 0
    if has_type(props, "status"):
        score += 30; fired.append("status property")
    elif has_select_with_options(props, DONE_WORDS | INPROGRESS_WORDS | NOTSTARTED_WORDS):
        score += 20; fired.append("select with task-like options")
    if prop_name_contains(props, ["date"], ["due", "deadline", " by ", "target"]):
        score += 20; fired.append("due-date property")
    if prop_name_contains(props, ["people"], ["assignee", "owner", "responsible"]):
        score += 15; fired.append("assignee people property")
    if prop_name_contains(props, ["select", "multi_select"],
                         ["workspace", "project", "category", "area", "department"]):
        score += 10; fired.append("workspace/category select")
    if title_contains(title, ["task", "todo", "to-do", "action", "work"]):
        score += 15; fired.append(f"title contains task-word")
    # >1 entry: assume true (we don't query rows in this MVP)
    score += 10; fired.append("active (assumed)")
    return score / 100.0, fired

def score_crm(ds):
    props = ds["properties"]
    title = ds["title"]
    fired, score = [], 0
    if any(p["type"] == "relation" for p in props):
        score += 20; fired.append("has relation property")
    if has_type(props, "email"):
        score += 20; fired.append("email property")
    if has_type(props, "phone_number"):
        score += 15; fired.append("phone_number property")
    if prop_name_contains(props, ["select", "status"], ["stage", "status", "pipeline"]):
        score += 15; fired.append("stage/status select")
    if title_contains(title, ["crm", "contact", "contact", "client",
                              "customer", "lead", "account", "vendor", "partner"]):
        score += 30; fired.append("title contains CRM-word")
    return score / 100.0, fired

def score_activity_log(ds):
    props = ds["properties"]
    title = ds["title"]
    fired, score = [], 0
    if title_contains(title, ["log", "activity", "journal", "history", "events"]):
        score += 35; fired.append("title contains log-word")
    if has_type(props, "date"):
        score += 20; fired.append("date property")
    if prop_name_contains(props, ["select", "multi_select"],
                         ["type", "kind", "channel", "outcome"]):
        score += 20; fired.append("type/outcome select")
    if prop_name_contains(props, ["rich_text"],
                         ["outcome", "next", "action", "result"]):
        score += 10; fired.append("outcome/next rich_text")
    if days_since(ds.get("last_edited_time")) <= 14:
        score += 15; fired.append("recently edited (<=14d)")
    return score / 100.0, fired

def score_meeting_notes(ds, master_tasks_ds_id):
    props = ds["properties"]
    title = ds["title"]
    fired, score = [], 0
    has_date = has_type(props, "date")
    has_people = any(p["type"] == "people" for p in props)
    if title_contains(title, ["meeting", "1:1", "standup", "huddle", "call"]) or \
       (title_contains(title, ["notes"]) and (has_date or has_people)):
        score += 30; fired.append("title contains meeting-word")
    if has_date:
        score += 20; fired.append("date property")
    if has_people:
        score += 20; fired.append("people property (attendees)")
    if prop_name_contains(props, ["rich_text", "formula"],
                         ["summary", "recap", "outcome", "transcript"]):
        score += 15; fired.append("summary/recap property")
    if master_tasks_ds_id:
        for p in props:
            if p["type"] == "relation" and p.get("relation_data_source_id") == master_tasks_ds_id:
                score += 15; fired.append("relation -> master tasks"); break
    return score / 100.0, fired

def band(score):
    if score >= 0.80: return "high"
    if score >= 0.50: return "medium"
    if score >= 0.30: return "low"
    return "none"

def main():
    schemas = [json.loads(line) for line in sys.stdin if line.strip()]
    results = []
    # First pass: score master tasks to find best candidate for meeting-notes relation hint
    mt_scores = [(ds, score_master_tasks(ds)[0]) for ds in schemas]
    mt_top = max(mt_scores, key=lambda x: x[1]) if mt_scores else (None, 0)
    master_tasks_id = mt_top[0]["id"] if mt_top[1] >= 0.5 else None

    for ds in schemas:
        scored = {
            "id": ds["id"],
            "title": ds["title"],
            "url": ds.get("url", ""),
            "n_props": len(ds["properties"]),
            "prop_summary": ", ".join(f'{p["name"]} ({p["type"]})' for p in ds["properties"][:8]),
            "scores": {
                "master_tasks": dict(zip(["score", "evidence"], score_master_tasks(ds))),
                "contact_crm": dict(zip(["score", "evidence"], score_crm(ds))),
                "activity_log": dict(zip(["score", "evidence"], score_activity_log(ds))),
                "meeting_notes": dict(zip(["score", "evidence"], score_meeting_notes(ds, master_tasks_id))),
            }
        }
        for role, s in scored["scores"].items():
            s["band"] = band(s["score"])
        results.append(scored)

    json.dump(results, sys.stdout, indent=2)

if __name__ == "__main__":
    main()

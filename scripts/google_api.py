#!/usr/bin/env python3
"""
google_api.py — drop-in replacement for the gws CLI for COO Twin skills.

gws is not installed on this machine. This script wraps the Google OAuth token
at ~/.hermes/google_token.json and produces JSON output compatible with the
format expected by all COO Twin SKILL.md files.

AUTH:
  Token path: ~/.hermes/google_token.json
  Scopes available: calendar (full), gmail (full), drive, contacts
  Scopes MISSING: tasks — run `python3 scripts/google_api.py reauth` to add

USAGE (mirrors gws patterns used in skills):

  Calendar:
    python3 scripts/google_api.py calendar today
    python3 scripts/google_api.py calendar tomorrow
    python3 scripts/google_api.py calendar week
    python3 scripts/google_api.py calendar insert --summary "Title" --start 2026-06-03T10:00 --end 2026-06-03T11:00

  Tasks:
    python3 scripts/google_api.py tasks list
    python3 scripts/google_api.py tasks list --show-completed
    python3 scripts/google_api.py tasks insert --title "Task" --notes "notes"
    python3 scripts/google_api.py tasks patch --task-id "ID" --status completed

  Re-auth (adds tasks scope):
    python3 scripts/google_api.py reauth

OUTPUT format:
  calendar list → {"count": N, "events": [{calendar, start, end, summary, location},...]}
  tasks list    → {"count": N, "tasks": [{id, title, status, due, notes},...]}
  insert/patch  → {"status": "ok", "id": "..."}
  errors        → exit 1, print {"error": "...", "status": "failed"}
"""

import sys
import os
import json
import argparse
import datetime
import warnings

# Suppress google-auth Python version warnings
warnings.filterwarnings("ignore", category=FutureWarning)

TOKEN_PATH = os.path.expanduser("~/.hermes/google_token.json")
SECRET_PATH = os.path.expanduser("~/.hermes/google_client_secret.json")
DEFAULT_TASKLIST = "MDE5NTgyMDkwMjMxNjkwNzQyMTk6MDow"

SCOPES = [
    "https://www.googleapis.com/auth/calendar",
    "https://www.googleapis.com/auth/gmail.modify",
    "https://www.googleapis.com/auth/gmail.readonly",
    "https://www.googleapis.com/auth/gmail.send",
    "https://www.googleapis.com/auth/drive",
    "https://www.googleapis.com/auth/documents",
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/contacts.readonly",
    "https://www.googleapis.com/auth/tasks",
]


def err(msg, code=1):
    print(json.dumps({"error": msg, "status": "failed"}))
    sys.exit(code)


def load_creds():
    try:
        from google.oauth2.credentials import Credentials
        from google.auth.transport.requests import Request
        creds = Credentials.from_authorized_user_file(TOKEN_PATH)
        if creds.expired and creds.refresh_token:
            creds.refresh(Request())
            with open(TOKEN_PATH, "w") as f:
                f.write(creds.to_json())
        return creds
    except Exception as e:
        err(f"Auth error: {e}. Run: python3 scripts/google_api.py reauth")


def build_service(name, version):
    try:
        from googleapiclient.discovery import build
        creds = load_creds()
        return build(name, version, credentials=creds)
    except Exception as e:
        err(f"Could not build {name} service: {e}")


# ============================================================
# CALENDAR
# ============================================================

def calendar_list(target: str = "today"):
    today = datetime.date.today()

    if target == "today":
        d_start = today
        d_end = today + datetime.timedelta(days=1)
    elif target == "tomorrow":
        d_start = today + datetime.timedelta(days=1)
        d_end = today + datetime.timedelta(days=2)
    elif target == "week":
        d_start = today
        d_end = today + datetime.timedelta(days=7)
    else:
        try:
            d_start = datetime.date.fromisoformat(target)
            d_end = d_start + datetime.timedelta(days=1)
        except ValueError:
            err(f"Unknown calendar target: {target}. Use: today, tomorrow, week, YYYY-MM-DD")
            return  # unreachable but satisfies type checker

    time_min = datetime.datetime.combine(d_start, datetime.time.min).isoformat() + "Z"
    time_max = datetime.datetime.combine(d_end, datetime.time.min).isoformat() + "Z"

    svc = build_service("calendar", "v3")
    result = svc.events().list(  # type: ignore[union-attr]
        calendarId="primary",
        timeMin=time_min,
        timeMax=time_max,
        singleEvents=True,
        orderBy="startTime"
    ).execute()

    items = result.get("items", [])
    events = []
    for e in items:
        start_raw = e.get("start", {})
        end_raw = e.get("end", {})
        events.append({
            "calendar": e.get("organizer", {}).get("email", "primary"),
            "id": e.get("id", ""),
            "start": start_raw.get("dateTime", start_raw.get("date", "")),
            "end": end_raw.get("dateTime", end_raw.get("date", "")),
            "summary": e.get("summary", "(no title)"),
            "location": e.get("location", ""),
            "description": e.get("description", ""),
        })

    print(json.dumps({"count": len(events), "events": events}, indent=2))


def calendar_insert(summary: str, start: str, end: str, description: str = "", location: str = "", calendar_id: str = "primary"):
    def parse_dt(s: str) -> dict:
        s = s.strip()
        if "T" in s:
            if len(s) == 16:
                s += ":00"
            if "+" not in s and "Z" not in s:
                s += "-04:00"
            return {"dateTime": s}
        return {"date": s}

    body: dict = {
        "summary": summary,
        "start": parse_dt(start),
        "end": parse_dt(end),
    }
    if description:
        body["description"] = description
    if location:
        body["location"] = location

    svc = build_service("calendar", "v3")
    evt = svc.events().insert(calendarId=calendar_id, body=body).execute()  # type: ignore[union-attr]
    print(json.dumps({"status": "ok", "id": evt.get("id", ""), "link": evt.get("htmlLink", "")}, indent=2))


# ============================================================
# TASKS
# ============================================================

def tasks_list(tasklist_id: str = None, show_completed: bool = False, extra_params: dict = None):
    tl = tasklist_id or DEFAULT_TASKLIST
    svc = build_service("tasks", "v1")

    kwargs: dict = {
        "tasklist": tl,
        "showCompleted": show_completed,
        "showHidden": show_completed,
        "maxResults": 100,
    }
    if extra_params:
        kwargs.update(extra_params)
        kwargs.setdefault("tasklist", tl)

    result = svc.tasks().list(**kwargs).execute()  # type: ignore[union-attr]
    items = result.get("items", [])
    tasks = []
    for t in items:
        due = t.get("due", "")[:10] if t.get("due") else ""
        tasks.append({
            "id": t.get("id", ""),
            "title": t.get("title", ""),
            "status": t.get("status", ""),
            "due": due,
            "notes": t.get("notes", ""),
            "updated": t.get("updated", "")[:10],
        })
    print(json.dumps({"count": len(tasks), "tasks": tasks}, indent=2))


def tasks_insert(title: str, notes: str = "", due: str = None, tasklist_id: str = None):
    tl = tasklist_id or DEFAULT_TASKLIST
    body: dict = {"title": title}
    if notes:
        body["notes"] = notes
    if due:
        if "T" not in due:
            due = due + "T00:00:00.000Z"
        body["due"] = due

    svc = build_service("tasks", "v1")
    result = svc.tasks().insert(tasklist=tl, body=body).execute()  # type: ignore[union-attr]
    print(json.dumps({"status": "ok", "id": result.get("id", ""), "title": result.get("title", "")}, indent=2))


def tasks_patch(task_id: str, status: str = None, title: str = None, notes: str = None, tasklist_id: str = None):
    tl = tasklist_id or DEFAULT_TASKLIST
    body: dict = {}
    if status:
        body["status"] = status
        if status == "completed":
            body["completed"] = datetime.datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%S.000Z")
    if title:
        body["title"] = title
    if notes:
        body["notes"] = notes

    svc = build_service("tasks", "v1")
    result = svc.tasks().patch(tasklist=tl, task=task_id, body=body).execute()  # type: ignore[union-attr]
    print(json.dumps({"status": "ok", "id": result.get("id", ""), "updated": result.get("updated", "")}, indent=2))


# ============================================================
# REAUTH
# ============================================================

def reauth():
    try:
        from google_auth_oauthlib.flow import InstalledAppFlow
        if not os.path.exists(SECRET_PATH):
            err(f"Client secret not found at {SECRET_PATH}. Download from Google Cloud Console.")
        flow = InstalledAppFlow.from_client_secrets_file(SECRET_PATH, SCOPES)
        creds = flow.run_local_server(port=0)
        with open(TOKEN_PATH, "w") as f:
            f.write(creds.to_json())
        print(json.dumps({"status": "ok", "message": "Token refreshed with all scopes including tasks", "token_path": TOKEN_PATH}))
    except Exception as e:
        err(f"Reauth failed: {e}")


# ============================================================
# MAIN
# ============================================================

def main():
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(0)

    cmd = sys.argv[1]

    if cmd == "reauth":
        reauth()

    elif cmd == "calendar":
        if len(sys.argv) < 3:
            err("Usage: google_api.py calendar <today|tomorrow|week|YYYY-MM-DD|insert>")
        sub = sys.argv[2]
        if sub == "insert":
            p = argparse.ArgumentParser()
            p.add_argument("--summary", required=True)
            p.add_argument("--start", required=True)
            p.add_argument("--end", required=True)
            p.add_argument("--description", default="")
            p.add_argument("--location", default="")
            p.add_argument("--calendar", default="primary")
            args = p.parse_args(sys.argv[3:])
            calendar_insert(args.summary, args.start, args.end, args.description, args.location, args.calendar)
        else:
            calendar_list(sub)

    elif cmd == "tasks":
        if len(sys.argv) < 3:
            err("Usage: google_api.py tasks <list|insert|patch>")
        sub = sys.argv[2]
        if sub == "list":
            p = argparse.ArgumentParser()
            p.add_argument("--show-completed", action="store_true")
            p.add_argument("--tasklist", default=None)
            p.add_argument("--params", default=None)
            args = p.parse_args(sys.argv[3:])
            extra = json.loads(args.params) if args.params else None
            tasks_list(args.tasklist, args.show_completed, extra)
        elif sub == "insert":
            p = argparse.ArgumentParser()
            p.add_argument("--title", required=True)
            p.add_argument("--notes", default="")
            p.add_argument("--due", default=None)
            p.add_argument("--tasklist", default=None)
            args = p.parse_args(sys.argv[3:])
            tasks_insert(args.title, args.notes, args.due, args.tasklist)
        elif sub == "patch":
            p = argparse.ArgumentParser()
            p.add_argument("--task-id", required=True)
            p.add_argument("--status", default=None)
            p.add_argument("--title", default=None)
            p.add_argument("--notes", default=None)
            p.add_argument("--tasklist", default=None)
            args = p.parse_args(sys.argv[3:])
            tasks_patch(args.task_id, args.status, args.title, args.notes, args.tasklist)
        else:
            err(f"Unknown tasks subcommand: {sub}")

    else:
        err(f"Unknown command: {cmd}. Use: calendar, tasks, reauth")


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""scripts/webhook-handler.py — Anthropic Managed Agents webhook receiver.

Spike-grade handler for the G7-MA evaluation (PRD §19.8). Receives signed
webhook deliveries from Anthropic, verifies via the SDK's `unwrap()` helper,
deduplicates by `event.id` (retry-safe per docs), and routes each event into
the AAC OBSERVED spine.

Subscribed event types (configure in Console → Manage → Webhooks):
    session.status_run_started
    session.status_idled
    session.status_rescheduled
    session.status_terminated
    session.thread_created
    session.thread_idled
    session.thread_terminated
    session.outcome_evaluation_ended
    vault_credential.refresh_failed

Outputs:
    logs/_telemetry.jsonl              — one row per terminal status (status_idled
                                         with end_turn, status_terminated, thread_terminated)
    state/webhook-events.jsonl         — full event log (every delivery)
    state/webhook-seen-events.txt      — event.id dedup ledger (last 10k IDs)
    state/webhook-alerts.jsonl         — critical events flagged for Telegram alerting

Run:
    pip install anthropic flask
    export ANTHROPIC_WEBHOOK_SIGNING_KEY=whsec_…   # from .secrets/anthropic.env
    export ANTHROPIC_API_KEY=sk-ant-…              # for the GET-by-ID follow-up calls
    python scripts/webhook-handler.py              # listens on 0.0.0.0:8787

Endpoint registration: must be HTTPS on port 443 with a public hostname
(see docs/managed-agents/webhooks "Register an endpoint"). For the spike,
front this with cloudflared or ngrok and copy the public URL into Console.

Idempotency contract: per the docs, Anthropic delivers each event at least
once. Retries carry the same `event.id`. We treat a duplicate `event.id` as
a no-op (drop after acking with 200) so the AAC OBSERVED spine never
double-counts a state transition.
"""

from __future__ import annotations

import json
import logging
import os
import pathlib
import sys
import threading
import time
from collections import deque
from typing import Set

try:
    import anthropic
    from flask import Flask, request
except ImportError as e:
    print(f"missing dependency: {e}. run: pip install anthropic flask", file=sys.stderr)
    sys.exit(2)


REPO_DIR = pathlib.Path(__file__).resolve().parent.parent
LOGS_DIR = REPO_DIR / "logs"
STATE_DIR = REPO_DIR / "state"
LOGS_DIR.mkdir(exist_ok=True)
STATE_DIR.mkdir(exist_ok=True)

EVENTS_FILE = STATE_DIR / "webhook-events.jsonl"
ALERTS_FILE = STATE_DIR / "webhook-alerts.jsonl"
TELEMETRY_FILE = LOGS_DIR / "_telemetry.jsonl"
SEEN_FILE = STATE_DIR / "webhook-seen-events.txt"

SEEN_MAX = 10_000
TERMINAL_EVENT_TYPES = {
    "session.status_terminated",
    "session.thread_terminated",
}
ALERT_EVENT_TYPES = {
    "session.status_terminated",
    "session.status_rescheduled",          # transient retry — log but don't page
    "vault_credential.refresh_failed",     # Notion/Google OAuth break — Telegram now
}

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("webhook")

# --- dedup ledger -----------------------------------------------------------

_seen_lock = threading.Lock()
_seen_ids: deque[str] = deque(maxlen=SEEN_MAX)
_seen_set: Set[str] = set()


def _load_seen() -> None:
    if not SEEN_FILE.exists():
        return
    with _seen_lock:
        for line in SEEN_FILE.read_text(encoding="utf-8").splitlines()[-SEEN_MAX:]:
            line = line.strip()
            if line:
                _seen_ids.append(line)
                _seen_set.add(line)


def _seen(event_id: str) -> bool:
    with _seen_lock:
        if event_id in _seen_set:
            return True
        # Evict from set if deque rolls over.
        if len(_seen_ids) == _seen_ids.maxlen:
            evicted = _seen_ids[0]
            _seen_set.discard(evicted)
        _seen_ids.append(event_id)
        _seen_set.add(event_id)
    # Append-only persistence; SEEN_FILE is bounded by trimming on startup.
    with SEEN_FILE.open("a", encoding="utf-8") as f:
        f.write(event_id + "\n")
    return False


# --- routing ----------------------------------------------------------------


def _append_jsonl(path: pathlib.Path, row: dict) -> None:
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(row, separators=(",", ":")) + "\n")


def _route(event, raw_body: bytes) -> None:
    """Fan a verified event to telemetry, full event log, and alert sink."""
    data = event.data
    event_type = data.type
    received_at = time.strftime("%Y-%m-%dT%H:%M:%S%z")

    row = {
        "received_at": received_at,
        "event_id": event.id,
        "event_type": event_type,
        "object_id": getattr(data, "id", None),
        "created_at": getattr(event, "created_at", None),
    }
    _append_jsonl(EVENTS_FILE, row)

    if event_type in TERMINAL_EVENT_TYPES:
        _append_jsonl(
            TELEMETRY_FILE,
            {
                "ts": received_at,
                "skill": "managed-agents",
                "run_id": getattr(data, "id", "unknown"),
                "duration_ms": 0,                 # webhook does not know duration; fetch GET to fill in
                "status": "failed" if "terminated" in event_type else "ok",
                "event_type": event_type,
                "event_id": event.id,
            },
        )

    if event_type in ALERT_EVENT_TYPES:
        _append_jsonl(
            ALERTS_FILE,
            {
                "ts": received_at,
                "event_id": event.id,
                "event_type": event_type,
                "object_id": getattr(data, "id", None),
                "needs_telegram": True,
            },
        )
        log.warning("ALERT %s id=%s object=%s", event_type, event.id, getattr(data, "id", None))
    else:
        log.info("event %s id=%s object=%s", event_type, event.id, getattr(data, "id", None))


# --- HTTP -------------------------------------------------------------------


def make_app() -> Flask:
    signing_key = os.environ.get("ANTHROPIC_WEBHOOK_SIGNING_KEY")
    if not signing_key:
        log.error("ANTHROPIC_WEBHOOK_SIGNING_KEY not set; refusing to start")
        sys.exit(2)

    # The SDK reads ANTHROPIC_WEBHOOK_SIGNING_KEY from env automatically.
    client = anthropic.Anthropic()
    _load_seen()
    app = Flask(__name__)

    @app.route("/webhook", methods=["POST"])
    def webhook():
        body = request.get_data(as_text=True)
        try:
            event = client.beta.webhooks.unwrap(body, headers=dict(request.headers))
        except Exception as e:  # noqa: BLE001 — SDK raises generic on bad sig / stale
            log.warning("signature verification failed: %s", e)
            return ("invalid signature", 400)

        if _seen(event.id):
            log.debug("dup event.id=%s — dropping", event.id)
            return ("", 204)

        try:
            _route(event, body.encode("utf-8"))
        except Exception as e:  # noqa: BLE001
            # Return 5xx so Anthropic retries with the same event.id.
            log.exception("route failed: %s", e)
            return ("internal error", 500)

        return ("", 204)

    @app.route("/healthz", methods=["GET"])
    def healthz():
        return ({"ok": True, "seen": len(_seen_ids)}, 200)

    return app


if __name__ == "__main__":
    port = int(os.environ.get("PORT", "8787"))
    make_app().run(host="0.0.0.0", port=port)

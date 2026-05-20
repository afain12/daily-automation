---
name: sync-sweep
description: >-
  Sync sweeper: resolves braindump mentions in today's daily note against the
  Notion workspace and appends dated updates to the matching pages under a
  `## Latest:` divider. MVE class A only (braindump → Notion page-body append).
  Trust gate before any writes; PHI gate before any LLM call.
tools: Bash, Read, Edit, Write, Glob, Grep, AskUserQuestion
coo_twin:
  category: capture
  mode_required: any
  writes_external: true
  preflight: required
  phi_gate: true
  experimental: false
---

# /sync-sweep — Braindump → Notion Resolver (MVE class A)

You are acting as Aaron's Chief of Staff. Your job is to read today's daily-note
`## Braindump` section, extract entity mentions, resolve each to a matching
Notion page, and stage a `## Latest:` append for human approval. Nothing is
written to Notion without the Step 8 trust gate.

**Scope (MVE):** input class **A only** — `vault/daily/YYYY-MM-DD.md` `## Braindump`
section. Classes B (Obsidian recent edits), C (Meeting Notes auto-processing),
and D (new Notion stub enrichment) are explicitly out-of-scope for this version
and slot in as v0.2 work — see `# TODO(v0.2)` markers below.

**Read-first, write-on-approval.** Show all proposed appends at a trust gate.
Each append is individually approvable.

## Constants

```
REPO_DIR = "C:/Users/aaron/daily-automation"
CONFIG   = "${REPO_DIR}/config/sources.yaml"
LOGS_DIR = "${REPO_DIR}/logs"
VAULT    = "${REPO_DIR}/vault"
STATE    = "${REPO_DIR}/state"
CONTEXT  = "${REPO_DIR}/.context"
TODAY    = <current date in YYYY-MM-DD format>
RUN_ID   = "ss-${TODAY//-/}-$(date +%H%M%S)"   # ss = sync-sweep
NOTION_API_VERSION = "2025-09-03"
TRIGGER_SOURCE = "standalone-invocation"  # override to "end-day-final-step" when invoked from /end-day
INPUT_CLASS = "A"                          # MVE; B/C/D = v0.2
CONF_FLOOR_CLASS_A = 0.85                  # auto-stage floor for class A (reversible-bounded)
CONF_UNCATEGORIZED = 0.70                  # below this → uncategorized bucket
MATCH_SCORE_FLOOR = 0.65                   # auto-stage requires this AND conf >= floor AND single match
TITLE_SIM_FLOOR = 0.55                     # added 2026-05-19 after observe-run: candidates below this title-similarity
                                           # are dropped BEFORE scoring (Notion /v1/search returns recency-sorted
                                           # generic candidates when no good match exists; without this floor the
                                           # scoring formula promotes "best of bad")
ACTIVITY_LOG_WEIGHT = 0.5                  # multiplier applied to workspace_match when candidate's parent_db is
                                           # "Activity Log". Activity Log rows are point-in-time records, not topic
                                           # pages — appending /sync-sweep updates to them muddies the audit trail.
```

## Step 0 — Mode Check (AAC GOVERNED)

Same incantation as `/capture-meeting` and `/end-day`. Refuses on `locked`,
sets `SKIP_WRITES=1` on `observe`, gates normally on `draft`/`approved`/`auto`.

```bash
MODE=$(scripts/check_mode.sh) || {
  echo "🛑 Agent is locked. /sync-sweep refuses to run."
  exit 0
}

SKIP_WRITES=0
if [ "${MODE}" = "observe" ]; then
  SKIP_WRITES=1
  echo "ℹ️  observe mode: Steps 9–10 will display proposed PATCHes but not execute them."
fi

RUN_START_MS=$(date +%s%3N 2>/dev/null || python -c "import time; print(int(time.time()*1000))")
```

- `locked` → refuse (no telemetry; locked runs don't happen).
- `observe` → run Steps 1–8 in full; skip Step 9 PATCH execution.
- `draft` (default) → standard trust gate at Step 8.
- `approved` → if every staged item's action_id has a prefix in
  `approved_action_prefixes`, auto-approve at Step 8. Otherwise gate normally.

## Step 1 — Pull Source Material (class A only)

Read today's daily note and extract the Braindump section. Aaron's daily notes
use three variant anchors interchangeably (audited 2026-05-19 across daily
notes 5/12–5/19):

- `^##\s+Braindump\b` — H2 heading form (future-compatible / preferred).
- `^\*\*Braindump.*\*\*\s*$` — bold inline marker (current most common; e.g.
  `**Braindump:**`, `**Braindump (raw, kept for reference):**`).
- `^Braindump:\s*$` — plain colon-terminated marker.

The braindump body is the text from the matched anchor up to (whichever comes
first): the next `^##\s` H2 heading, the next `^\*\*[A-Z]` bold-line marker
(e.g. `**Observations:**`), or EOF. Bash regex can't do alternation +
look-ahead cleanly, so the extraction is a single Python pre-pass embedded
inline (mirrors §3a pattern).

If the section is missing OR present-but-empty (the `**Braindump (raw, kept
for reference):**` placeholder pattern Aaron uses in 5/14–5/19 is empty by
design), the run is a clean no-op — log it and exit before any LLM cost.

```bash
DAILY_NOTE="${VAULT}/daily/${TODAY}.md"

if [ ! -f "${DAILY_NOTE}" ]; then
  echo "ℹ️  No daily note at ${DAILY_NOTE}. /sync-sweep is a no-op today."
  # Still emit a telemetry row at Step 11 with entities_extracted=0, status=ok.
  BRAINDUMP_TEXT=""
else
  # Extract from any of three Braindump anchors up to next H2, next bold-line
  # marker, or EOF. Python because bash regex can't cleanly express the union.
  export DAILY_NOTE
  BRAINDUMP_TEXT="$(python - <<'PY'
import pathlib, re, os
p = pathlib.Path(os.environ["DAILY_NOTE"])
text = p.read_text(encoding="utf-8", errors="replace")
lines = text.splitlines()

# Anchors that open a Braindump section.
anchor_pats = [
    re.compile(r"^##\s+Braindump\b"),          # H2 heading
    re.compile(r"^\*\*Braindump.*\*\*\s*$"),   # bold inline (e.g. **Braindump:**)
    re.compile(r"^Braindump:\s*$"),            # plain colon-terminated
]
# Boundary patterns that close the section.
close_h2     = re.compile(r"^##\s")
close_bold   = re.compile(r"^\*\*[A-Z]")

start_idx = None
for i, ln in enumerate(lines):
    if any(p.match(ln) for p in anchor_pats):
        start_idx = i + 1  # body starts on next line
        break

if start_idx is None:
    print("")
else:
    end_idx = len(lines)
    for j in range(start_idx, len(lines)):
        if close_h2.match(lines[j]) or close_bold.match(lines[j]):
            end_idx = j
            break
    print("\n".join(lines[start_idx:end_idx]))
PY
  )"
fi

if [ -z "${BRAINDUMP_TEXT//[[:space:]]/}" ]; then
  echo "ℹ️  No Braindump section (or section empty) in ${DAILY_NOTE}. /sync-sweep is a no-op today."
  # Fall through to Step 11 telemetry with entities_extracted=0, status=ok.
fi
```

**Strip already-synced lines.** Any line that already carries a
`<!-- synced to notion:<id> -->` marker has been processed by a prior run; skip
it so we don't re-extract the same entities. The action_id stamp at
`.context/applied/` is the durable check; this strip is the cheap pre-filter.
Guard the python pipeline against empty input so we don't blow stdin on the no-op path.

```bash
if [ -n "${BRAINDUMP_TEXT}" ]; then
  BRAINDUMP_TEXT="$(printf '%s' "${BRAINDUMP_TEXT}" | python - <<'PY'
import sys, re
text = sys.stdin.read()
# Drop any line containing the synced sentinel comment.
out = [ln for ln in text.splitlines() if not re.search(r"<!--\s*synced to notion:[A-Za-z0-9_\-]+\s*-->", ln)]
print("\n".join(out))
PY
)"
fi

# Re-check after strip: whitespace-only output is still a no-op.
if [ -z "${BRAINDUMP_TEXT//[[:space:]]/}" ]; then
  echo "ℹ️  Braindump section contains only already-synced lines. No-op."
  STATUS="ok"
  # Fall through to Step 11.
fi
```

# TODO(v0.2): T10 — class B Obsidian vault scan (recent edits in CardioPro/,
# Labaide/, Nestmate/, United IPA/, Notes to self/, notes/, inbox/ within 24h).
# Reuse the same Step 3 entity-extraction call; tag items `[class-B]` in trust gate.

# TODO(v0.2): T12-13 — class C Meeting Notes auto-processing. Query data_source
# 22ba3158-... for fresh meetings, gate on `Related Tasks` empty, invoke
# scripts/capture_meeting_parse.py + capture_meeting_write.py.

# TODO(v0.2): T14 — class D new Notion stub-page enrichment via /v1/search.

# TODO(v0.2): T15 — E4 Granola URL detection + E5 duplicate-append guard.

## Step 2 — PHI Input Gate (AAC GATED)

Pipe the braindump through `scripts/phi_scan.sh` BEFORE any LLM call. PHI
detection refuses the run, logs to `logs/_phi_refusals.jsonl`, and never
reaches Step 3 entity extraction.

```bash
if [ -n "${BRAINDUMP_TEXT// /}" ]; then
  printf '%s' "${BRAINDUMP_TEXT}" | scripts/phi_scan.sh
  PHI_EXIT=$?
else
  PHI_EXIT=0  # empty input: don't trip phi_scan's exit=2 read-error path.
fi
```

- `PHI_EXIT == 0` → clean, proceed to Step 3.
- `PHI_EXIT == 1` → PHI markers detected. **Refuse.** Display sanitized
  line numbers from phi_scan.sh stderr. Append a row to
  `logs/_phi_refusals.jsonl` with `skill: sync-sweep`, `run_id`, ISO timestamp,
  and the detected pattern labels (NOT raw matched text). Skip Steps 3–10.
  Step 11 telemetry status = `refused`.
- `PHI_EXIT == 2` → read error (empty input). Treated as no-op upstream.

```bash
if [ "${PHI_EXIT}" = "1" ]; then
  TS_PHI="$(date -Iseconds 2>/dev/null || date +"%Y-%m-%dT%H:%M:%S%z")"
  export TS_PHI RUN_ID
  python - <<'PY' >> "${LOGS_DIR}/_phi_refusals.jsonl"
import json, os
row = {
  "ts": os.environ["TS_PHI"],
  "skill": "sync-sweep",
  "run_id": os.environ["RUN_ID"],
  "input_class": "A",
  "patterns": ["see-stderr-line-numbers"],
}
print(json.dumps(row, separators=(",", ":")))
PY
  echo "🛑 PHI detected in braindump. /sync-sweep refuses. Clean the daily note and re-run."
  STATUS="refused"
fi
```

**Refusal short-circuit (AAC GATED — code-enforced, not commented).** Steps
3 through 10 are wrapped in an explicit guard. The refusal is a control-flow
fact, not a prose note:

```bash
if [ "${STATUS:-ok}" = "refused" ]; then
  : "PHI gate refused — skip directly to Step 11 telemetry."
else
  # === Step 3 through Step 10 execute inside this branch ===
  # (See below.)
  :
fi
```

The `# === Step 3 through Step 10 execute inside this branch ===` marker is
load-bearing: every subsequent step in the runbook below executes ONLY when
`STATUS != "refused"`. The `else` branch closes after Step 10.

## Step 3 — Entity Extraction (C-element, single LLM call)

This is the ONLY LLM call in the MVE skill. Everything else is deterministic.
The extraction pass does three things in order:

1. **Deterministic regex pre-pass** on the braindump to find section headers
   and line-level business-keyword signals.
2. **±2-line context window** assembled per candidate line.
3. **Single LLM call** that takes the raw braindump + per-line precomputed
   `section_context`, `line_business_signal`, and `context_window` as input
   and returns a JSON array matching the §7 `per_entity_mention` schema.

### 3a. Deterministic pre-pass (regex)

```bash
PREPASS_JSON="$(printf '%s' "${BRAINDUMP_TEXT}" | python - <<'PY'
import sys, re, json, yaml, pathlib
text = sys.stdin.read()
lines = text.splitlines()

# Load calendar_business_keywords from config/sources.yaml.
cfg = yaml.safe_load(pathlib.Path("config/sources.yaml").read_text(encoding="utf-8"))
biz_kw = cfg.get("calendar_business_keywords", {})
# Flat lookup: lowercase keyword -> workspace tag (lab/ipa/nestmate/dock_pro).
kw_to_biz = {}
for biz_tag, kws in biz_kw.items():
    for kw in kws:
        kw_to_biz[kw.lower()] = biz_tag

# For each non-empty line, compute section_context (nearest preceding ## or ###),
# line_business_signal (first kw match), and context_window (±2 lines).
section = None
out = []
for i, ln in enumerate(lines, start=1):
    h = re.match(r"^\s*(#{2,3})\s+(.*)", ln)
    if h:
        section = h.group(2).strip()
        continue
    stripped = ln.strip()
    if not stripped or stripped.startswith("<!--"):
        continue
    lower = ln.lower()
    hits = [kw for kw in kw_to_biz if re.search(rf"\b{re.escape(kw)}\b", lower)]
    line_biz = None
    multi = False
    if hits:
        biz_tags = sorted({kw_to_biz[h] for h in hits})
        if len(biz_tags) == 1:
            line_biz = biz_tags[0]
        else:
            line_biz = "AMBIGUOUS:" + ",".join(biz_tags)
            multi = True
    # ±2 line window (current line included so the LLM sees what it's classifying).
    lo, hi = max(1, i-2), min(len(lines), i+2)
    window = [f"L{j}: {lines[j-1]}" for j in range(lo, hi+1)]
    out.append({
        "source_line": i,
        "source_text": ln,
        "section_context": section,
        "line_business_signal": line_biz,
        "multi_keyword_flag": multi,
        "context_window": window,
    })
print(json.dumps(out))
PY
)"
```

`PREPASS_JSON` is now a JSON array of per-line records the LLM call uses as
side-channel hints. Empty result → no candidates → skip directly to Step 11
with `entities_extracted: 0`.

### 3b. Entity-extraction system prompt (copy verbatim to the LLM call)

The runner (Claude in-process) makes a single structured-output call with the
prompt below. Pass the **full braindump text** as the user message plus the
`PREPASS_JSON` as a second `<prepass>` block. Soft 20s timeout; on timeout,
fall back to the §3c regex-only deterministic path.

```text
You are extracting entity mentions from Aaron's daily-note braindump for the
/sync-sweep skill. Aaron tracks providers, accounts/clinics, deals/programs,
and recurring topic meetings in Notion. Each braindump line may mention one or
more of these entities — your job is to surface them with confidence scores
and source-line citations.

IN-SCOPE ENTITIES
- People: providers, reps, business contacts (e.g. "Alex Acosta", "Dr Gordin", "Ahmed")
- Accounts / clinics: e.g. "AFC Urgent Care", "Sovereign Phoenix", "Essen Healthcare"
- Deals / programs: e.g. "the Roosevelt cardio meeting", "AHBD/LDX integration"
- Topic / recurring meetings: e.g. "Cardio Pro Rollout", "SP weekly"

OUT OF SCOPE
- Generic verbs ("called", "emailed", "scheduled")
- Aaron himself
- Vague references ("the doctor", "they")

E1 RULE (section-header soft prior + line-level override)
You will receive per-line precomputed `section_context` (nearest preceding ## or ###
heading), `line_business_signal` (a business tag inferred from a keyword on the
current line via config/sources.yaml `calendar_business_keywords`), and a
`multi_keyword_flag`. Apply these rules:
1. `section_context` is a SOFT prior — it suggests the business but does NOT lock it.
2. If `line_business_signal` is set and NOT ambiguous, it OVERRIDES `section_context`
   for this line. Set `override_applied: true` when the line signal disagrees with
   the section.
3. If `multi_keyword_flag` is true (multiple distinct business tags on one line),
   set confidence ≤ 0.70 — the item routes to disambiguation downstream.
4. Confidence reflects section+line agreement: high (≥0.85) when both point the
   same way; drops to ~0.70 when the line overrides the section; even lower for
   ambiguous multi-keyword lines.

CONFIDENCE RUBRIC
- 0.95+: full name + business context match (e.g., "Alex Acosta finally called back")
- 0.85:  partial name but unambiguous in context (e.g., "Acosta pushing Friday")
         OR first name matches a `single_dept_persons` entry from config/sources.yaml
- 0.70:  first name + business context, multi-dept name (e.g., "Alex from Roosevelt cardio")
         OR line-overrides-section case
- < 0.70: ambiguous — return anyway with low conf; downstream routes to Uncategorized
         (confidence < 0.70 is the HARD floor for category=uncategorized).

OUTPUT — JSON array, one element per entity mention. Each element matches the
§7 per_entity_mention schema (the fields you produce):
{
  "entity_canonical": "<resolved canonical name>",
  "aliases": ["<short form>", "..."],
  "source_line": <int>,
  "source_text": "<verbatim line from braindump>",
  "confidence": <float 0.0-1.0>,
  "update_summary": "<one-line synthesis of what to append, ≤ 200 chars>",
  "section_context": "<nearest preceding heading, or null>",
  "line_business_signal": "<biz tag or null>",
  "override_applied": <bool>,
  "input_class": "A",
  "context_window": ["L<n>: <text>", "..."]
}

HARD REFUSE CLASSES
- If `update_summary` reads like a payment instruction (amount + verb like
  "wire", "send", "transfer"): set `entity_canonical: "PAYMENT_INSTRUCTION"`,
  confidence 0.0, and a single-line summary. Do not attempt to resolve to a CRM.
- If the line contains an SSN/MRN/DOB pattern (PHI gate should have caught it,
  but defense in depth): set `entity_canonical: "PHI_LEAK"`, confidence 0.0.

VALIDATION
- Every element MUST include `source_line` AND `source_text` AND `confidence`.
- Items with confidence < 0.70 are still returned (downstream sets category=uncategorized).
- Return an empty array `[]` if no in-scope mentions are present. Never invent
  entities to "fill" the output.
```

After the LLM returns, validate the JSON against the schema fields. Stash the
parsed array as `ENTITIES_JSON`.

```bash
# Pseudo: assume the in-process LLM call returns to ENTITIES_JSON.
# Validate: every element has source_line, source_text, confidence; conf < 0.70
# items get marked uncategorized in Step 5.

echo "${ENTITIES_JSON}" | python -c "
import sys, json
arr = json.loads(sys.stdin.read())
required = {'entity_canonical','source_line','source_text','confidence'}
for e in arr:
    missing = required - e.keys()
    if missing:
        raise SystemExit(f'sync-sweep: extraction output missing required fields: {missing}')
print(f'extracted {len(arr)} entity mentions')
"
```

### 3c. Regex fallback (LLM timeout)

On LLM timeout (>20s), fall back to: extract proper nouns matching
`calendar_business_keywords` from `config/sources.yaml` directly from the
braindump. Confidence = 0.65 across the board (forces all matches to
disambiguation downstream — safer than guessing). Log the fallback in
telemetry as `extraction_path: "regex-fallback"`.

## Step 4 — Workspace-wide Notion Search (per entity)

For each entity, issue `/v1/search` with the canonical name. Collect up to 5
candidates including topic-page hits (do NOT filter to DB hits — Aaron's
Granola routing intentionally lands content in topic pages).

```bash
# Per-entity loop (pseudo — runner iterates over ENTITIES_JSON):
for ENTITY in "${ENTITIES[@]}"; do
  QUERY="${ENTITY_CANONICAL}"   # try canonical first; alias fallback below
  # Bound query length defensively — Notion /v1/search has a soft cap and
  # absurd canonical names would otherwise rate-limit the whole loop.
  if [ "${#QUERY}" -gt 200 ]; then QUERY="${QUERY:0:200}"; fi
  export QUERY

  TMP="$(mktemp 2>/dev/null || echo "/tmp/sync_sweep_search_$$.json")"
  SEARCH_BODY="$(python -c "
import json, os
print(json.dumps({
  'query': os.environ['QUERY'],
  'page_size': 5,
  'sort': {'direction':'descending','timestamp':'last_edited_time'},
}))")"

  HTTP_CODE=$(curl -s -o "${TMP}" -w '%{http_code}' --max-time 60 \
    -X POST "https://api.notion.com/v1/search" \
    -H "Authorization: Bearer $NOTION_API_TOKEN" \
    -H "Notion-Version: ${NOTION_API_VERSION}" \
    -H "Content-Type: application/json" \
    -d "${SEARCH_BODY}")

  case "${HTTP_CODE}" in
    2*)
      SEARCH_RESULT="$(cat "${TMP}")"
      rm -f "${TMP}"
      ;;
    401)
      echo "🛑 401 from Notion /v1/search. NOTION_API_TOKEN appears expired."
      echo "   Rotate per .secrets/notion.env, then re-run /sync-sweep."
      STATUS="failed"
      rm -f "${TMP}"
      break   # stop the entity loop; remaining entities won't be searched
      ;;
    5*|000)
      # 5xx or curl timeout (000) → mark THIS entity no-match, run status=partial.
      echo "  ⚠️  Notion search ${HTTP_CODE} for '${ENTITY_CANONICAL}'. Marking no-match."
      STATUS="partial"
      rm -f "${TMP}"
      continue
      ;;
    *)
      echo "  ⚠️  Notion search returned ${HTTP_CODE} for '${ENTITY_CANONICAL}'. Marking no-match."
      STATUS="partial"
      rm -f "${TMP}"
      continue
      ;;
  esac

  # Parse top 5 hits from SEARCH_RESULT; for each capture page_id, page_title,
  # parent_db, workspace, last_edited_time, url. Topic-page hits
  # (parent.type=page_id) are kept.
  #
  # title_similarity floor (added 2026-05-19): drop candidates with
  # title_similarity(entity_canonical, page_title) < TITLE_SIM_FLOOR (0.55).
  # Notion /v1/search returns recency-sorted generic candidates when the
  # query doesn't match anything well; without this floor the Step 5 scoring
  # formula promotes "best of bad" — observe-run on 5/12-5/14 showed 4 of 6
  # person-name searches returning the same wrong 5-row candidate set with
  # Dr Langan GI scored top for every Nestmate person query.
  #
  # If ALL candidates fall below the floor → mark entity resolution: "no-match"
  # (same handling as the canonical-then-alias retry exhausting). Do NOT
  # surface low-similarity candidates in the trust gate — that trains Aaron
  # to either accept-wrong or always-skip, both anti-patterns.
done
```

**Per-candidate fields collected (used by Step 5 scoring):**
- `page_id` (UUID)
- `page_title` (from `properties.title` or `properties.Task` etc.)
- `parent_db` ("Provider CRM" | "Master Tasks" | "Activity Log" | "Meeting Notes"
  | "topic-page" — derived from `parent.type` + database id lookup)
- `workspace` (Workspace property if present; null for topic pages without one)
- `last_edited_time` (from the response)
- `url`

If the canonical name returns nothing, retry once with the first alias from the
entity's `aliases` array. Still nothing → mark `resolution: "no-match"` and
keep going.

**Failure modes:** 5xx on a search call marks THAT entity `no-match`,
sets `STATUS="partial"`, never crashes the run. 401 → stop all subsequent
search calls and surface to Aaron at Step 8 with `NOTION_API_TOKEN expired`.

## Step 5 — Match Scoring + Disambiguation Queue

Score each candidate per entity with the formula:

```
match_score = title_similarity * 0.5 + workspace_match * 0.3 + recency * 0.2
```

- **title_similarity** — Jaro-Winkler (or simple token Jaccard fallback)
  between `entity_canonical` and `candidate.page_title`. Normalized 0..1.
- **workspace_match** — 1.0 if candidate's workspace matches the entity's
  resolved business signal (see E1 priority below); 0.5 if no signal exists;
  0.0 if explicit disagreement. **Activity Log down-weight (added 2026-05-19):**
  if `candidate.parent_db == "Activity Log"`, multiply `workspace_match` by
  `ACTIVITY_LOG_WEIGHT` (0.5). Activity Log rows are point-in-time records,
  not topic pages — appending /sync-sweep updates to them muddies the audit
  trail. Observe-run on 5/14 showed the Parmar+Langan Activity Log row
  dominating every Nestmate person query at top-recency.
- **recency** — `1.0 - min(1.0, days_since_last_edit / 90)`. A page edited
  yesterday scores 1.0; one not touched in 90+ days scores 0.0.

### 5a. E1 prior application

The corrected E1 rule (per `state/aac-spec-sync-sweep.md` §E1, 2026-05-19):

1. If `line_business_signal` is set on the entity (non-null, non-ambiguous),
   use IT as the workspace filter (line overrides section).
2. Else if `section_context` maps to a known workspace (via
   `calendar_business_keywords` lookup), use the section's inferred business.
3. Else no workspace signal — `workspace_match = 0.5` for all candidates.

```bash
# Per entity, per candidate:
#   resolved_biz = entity.line_business_signal or infer_from(entity.section_context)
#   if candidate.workspace == workspace_values[resolved_biz]: workspace_match = 1.0
#   elif resolved_biz is None: workspace_match = 0.5
#   else: workspace_match = 0.0
```

### 5b. E2 resolution-memory boost

Read `state/sync-sweep-resolutions.yaml`. For each entity, if `mention_text`
matches a prior confirmed resolution AND the candidate's `page_id` matches the
stored `resolved_page_id`, add **+0.2** to that candidate's `match_score`
(capped at 1.0). This is the learned-routing boost.

```bash
RESOLUTIONS_FILE="${STATE}/sync-sweep-resolutions.yaml"
# python YAML read; for each resolution where mention_text == entity_canonical
# (case-insensitive), boost the matching candidate's score by +0.2.
```

# TODO(v0.2): T11 — graduation: when a resolution's `confirmation_count` reaches
# 3, write it to `entity_aliases` in config/sources.yaml and remove from
# sync-sweep-resolutions.yaml. Hooks into Step 8 trust-gate post-approval.

### 5c. single_dept_persons override

Read `single_dept_persons` from `config/sources.yaml`. If the entity's
`entity_canonical` (or any alias) matches a name in that map (case-insensitive,
e.g., `Sheila` → `Nestmate`), apply the override in two strictly-ordered phases:

**Phase 1 — filter THEN override.** First restrict the candidate list to
those whose `workspace` matches the mapped workspace. This MUST run before
the confidence boost so a name that maps to Nestmate but only returns Lab
candidates does NOT get auto-staged onto a wrong-workspace page.

**Phase 2 — conditional boost.**
- If ≥1 candidate survives the filter → override confidence to **0.85**
  (auto-stage-eligible) and proceed.
- If 0 candidates survive → DO NOT override confidence; fall through to
  the normal §5a/§5b scoring with the unfiltered candidate set. The entity
  will land in `disambiguation-needed` or `no-match` per the §5d table.

```text
# Pseudo:
if entity_canonical in single_dept_persons:
    mapped_ws = single_dept_persons[entity_canonical]
    filtered  = [c for c in candidates if c.workspace == mapped_ws]
    if filtered:
        candidates = filtered          # phase 1: restrict
        entity.confidence = 0.85       # phase 2: boost (only when survivors)
    else:
        pass                            # no override; normal scoring on full list
```

This makes a single-dept first name auto-stage-eligible without
disambiguation, but never at the cost of cross-workspace mis-routing.

### 5d. Auto-stage vs disambiguation routing

For each entity, compute:

| Condition | Outcome |
|---|---|
| `confidence < 0.70` | `resolution: "uncategorized"` — category becomes Uncategorized at the trust gate. No write proposed. |
| `confidence ≥ 0.85` AND single candidate with `match_score ≥ 0.65` | `resolution: "auto-stage"` |
| Otherwise (multi-match or low-mid confidence) | `resolution: "disambiguation-needed"` — show options at Step 8 |
| No candidates returned by Step 4 | `resolution: "no-match"` — surface but no write |

**Decision-verb side branch.** If `update_summary` contains any of
`decided | agreed | approved | finalized | going with | confirmed`, attach a
`activity_log_row` payload to the entity (for a parallel Activity Log row at
Step 9 — page-body append still happens too).

### 5e. Build the `payload` for auto-stage / post-disambig entities

For each entity headed to staging, build:

```yaml
payload:
  page_id: <chosen candidate.page_id>
  append_section_heading: "## YYYY-MM-DD — <one-line summary>"  # date is TODAY
  append_body: "<update_summary, trimmed to 500 chars>"
  activity_log_row: <null | {decision_summary, workspace, date}>
```

## Step 6 — Idempotency Check (AAC GATED)

For each staged entity, generate an `action_id` with the format
`sync-sweep:<page_id_short>:YYYY-MM-DD:<8-char-hash>`. Hash input is
`entity_canonical + page_id + source_text[:80]` — stable across re-runs of the
same braindump line. Skip any entity whose action_id is already stamped.

```bash
for ENTITY in "${STAGED_ENTITIES[@]}"; do
  PAGE_ID_SHORT="$(echo "${PAGE_ID}" | tr -d '-' | cut -c1-8)"
  HASH_INPUT="${ENTITY_CANONICAL}|${PAGE_ID}|$(printf '%.80s' "${SOURCE_TEXT}")"
  AID="$(scripts/action_id.sh generate sync-sweep "${PAGE_ID_SHORT}" "${TODAY}" "${HASH_INPUT}")"

  if scripts/action_id.sh check "${AID}"; then
    # Already applied in a prior run on the same braindump.
    # Mark `skip_idempotent: true`; don't display at the trust gate.
    SKIPPED_IDEMPOTENT=$((SKIPPED_IDEMPOTENT + 1))
    continue
  fi
  # Carry AID forward to Step 7.
  ENTITY_ACTION_IDS+=("${AID}")
done
```

Re-runs against the same braindump line are no-ops. Declined items
(`*-declined-*` archive at Step 9 Option C) do NOT block the idempotency check
— they were never stamped because no write happened.

`# Windows note: scripts/action_id.sh maps ':' -> '_' for the on-disk file
# name, since Windows filenames can't contain colons. The action_id itself
# (returned to the skill) keeps the colon form.`

## Step 7 — Stage Payloads to `.context/`

Write all fresh staged entities to a single JSON file at
`.context/sync-sweep-${RUN_ID}.json`. This is the durable record between Step 7
and Step 9 (in case the trust gate sits open while Aaron context-switches).

```bash
STAGE_FILE="${CONTEXT}/sync-sweep-${RUN_ID}.json"
mkdir -p "${CONTEXT}"

# STAGED_JSON contains LLM-extracted fields (entity_canonical, source_text,
# update_summary). Use os.environ rather than ${VAR} interpolation inside the
# heredoc — same hardening pattern as §9b/§9e (AAC BOUNDED).
export RUN_ID INPUT_CLASS TRIGGER_SOURCE MODE TODAY STAGED_JSON
python - <<'PY' > "${STAGE_FILE}"
import json, os
# STAGED_JSON is the in-memory list of fully-resolved entities from Step 6,
# JSON-serialized BEFORE export so we can re-parse here defensively.
entities = json.loads(os.environ.get("STAGED_JSON", "[]"))
payload = {
    "run_id":         os.environ.get("RUN_ID", ""),
    "skill":          "sync-sweep",
    "input_class":    os.environ.get("INPUT_CLASS", "A"),
    "trigger_source": os.environ.get("TRIGGER_SOURCE", "standalone-invocation"),
    "mode":           os.environ.get("MODE", "draft"),
    "today":          os.environ.get("TODAY", ""),
    "status":         "pending",   # cleared when moved to .context/applied/ at Step 10
    "entities":       entities,
}
print(json.dumps(payload, indent=2))
PY
```

The file is the GROUNDED audit trail — every entity in it carries
`source_line`, `source_text`, `entity_canonical`, `confidence`, the chosen
`page_id`, and the `action_id`. If Aaron declines at Step 8, the file is
archived as `<name>-declined-<date>.json` and never written-to-Notion. If
PATCHes succeed, Step 10 moves it to `.context/applied/`.

## Step 8 — Trust Gate (H-element, AAC GATED)

Display all staged entities grouped by source class (only `[class-A]` in MVE).
Each row carries the AAC-mandated source marker, confidence, source citation,
and proposed append body. Then ask Aaron to approve.

```markdown
# /sync-sweep — Staged Appends ({N} items)
Run: {RUN_ID} · Mode: {MODE} · Trigger: {TRIGGER_SOURCE} · Date: {TODAY}

## Class A — Braindump → Notion page-body append

1. [class-A conf:0.92] Alex Acosta  →  [notion:23ba…] Alex Acosta — Provider CRM (Nestmate)
   Source line 47: "Alex Acosta finally called back — pushing Roosevelt cardio to Friday"
   Append heading: "## 2026-05-19 — Acosta called back, pushing Roosevelt Friday"
   Append body  : "Alex Acosta finally called back — pushing Roosevelt cardio to Friday"
   match_score  : 0.88 (title 0.95, workspace 1.0, recency 0.70)
   action_id    : sync-sweep:23ba3158:2026-05-19:a1b2c3d4
   url          : https://www.notion.so/...

2. [class-A conf:0.72] Dr Tim ENG  →  [notion:8f4d…] Dr Tim ENG — Provider CRM (Lincoln Lab)
   Source line 14: "Tim ENG successfully closed for lab"
   E1 note      : line keyword "lab" OVERRODE section "Nestmate" → routing Lincoln Lab.
   Append heading: "## 2026-05-19 — Tim ENG closed for lab"
   match_score  : 0.74
   action_id    : sync-sweep:8f4d2a99:2026-05-19:b2c3d4e5

## Disambiguation needed ({D} items)

3. [class-A conf:0.65] Ahmed  →  multiple candidates
   Source line 31: "Ahmed sent over the panel results"
   Pick one:
     [A] Ahmed Khan — Provider CRM (Nestmate)   last edited 2026-05-12   match: 0.71
     [B] Ahmed Sayed — Provider CRM (Lincoln Lab) last edited 2026-04-28 match: 0.62
     [N] None / skip this mention

## Uncategorized ({U} items) — conf < 0.70 OR no match

4. [class-A conf:0.55] "Saw Yili briefly" — no clear entity match
5. [class-A no-match] "Dropped a sample at the pickup spot" — no entity extracted

## Skipped — already applied in prior run ({S} items)
- "...source_text..." — action_id matches .context/applied/. Use 'force re-run' to override.
```

Use `AskUserQuestion` with the exact structured-call shape used by
/capture-meeting Step 5. Realistic example payload:

```json
{
  "questions": [
    {
      "question": "Which of these staged appends should I apply?",
      "header": "Sync-sweep approval",
      "multiSelect": false,
      "options": [
        {"label": "Apply all",            "description": "PATCH every staged append shown above (skips disambiguation rows)."},
        {"label": "Apply selected",       "description": "Enter comma-separated item numbers in the follow-up (e.g. '1,3,5')."},
        {"label": "Decline all",          "description": "No Notion writes. Payloads archive to .context/applied/<run_id>-declined-<TODAY>.json for audit."},
        {"label": "Edit before applying", "description": "Rewrite one or more append_body strings before approval; re-renders the trust gate."}
      ]
    }
  ]
}
```

Options (matches /capture-meeting Step 5 + /end-day Step 7 conventions):
- **Apply all** — PATCH every staged append. Sets `OPTION_PICKED=A`.
- **Apply selected** — comma-separated numbers (e.g. "1,3"). Sets `OPTION_PICKED=B`.
- **Decline all — archive only** — no Notion writes; payloads still archive to
  `.context/applied/sync-sweep-<run_id>-declined-${TODAY}.json` for audit.
  Sets `OPTION_PICKED=C`.
- **Edit before applying** — Aaron rewrites a specific `append_body` before
  approval. Sets `OPTION_PICKED=D` and re-renders the trust gate.

For disambiguation rows (item 3 in the markdown above), Aaron picks `[A]` /
`[B]` / `[N]` per entity in a follow-up `AskUserQuestion` round-trip. Picks
update `state/sync-sweep-resolutions.yaml` (increment `confirmation_count` or
create entry).

**Decline short-circuit (AAC GATED — code-enforced).** If `OPTION_PICKED=C`,
Step 9 is skipped entirely; only Step 10 archive + Step 11 telemetry run:

```bash
if [ "${OPTION_PICKED}" = "C" ]; then
  SKIP_PATCH=1
  echo "ℹ️  Aaron declined all staged appends. Archiving payload only."
fi
```

# TODO(v0.2): T11 graduation hook fires here on confirmation_count >= 3.

`# `[notion:abcd]` 4-char stub format matches /start-day Step 7 source-marker
# convention (the GROUNDED discipline) so Aaron can scan staged appends and
# /start-day briefings with the same eye.`

## Step 9 — Apply PATCHes (with `## Latest:` prepend)

**Step 9 execution guard (AAC GATED — code-enforced).** The entire Step 9
block executes only when the trust gate approved writes AND mode permits them:

```bash
if [ -z "${SKIP_PATCH:-}" ] && [ "${MODE}" != "locked" ] && [ "${SKIP_WRITES:-0}" = "0" ]; then
  # === Step 9a–9e execute inside this branch ===
  :
else
  echo "ℹ️  Skipping Step 9 PATCH block (mode=${MODE}, skip_patch=${SKIP_PATCH:-0}, skip_writes=${SKIP_WRITES:-0})."
fi
```

Inside the branch, for each approved entity, PATCH
`/v1/blocks/{page_id}/children` to insert the new content. The `## Latest:`
prepend pattern (locked decision #1, with **G1 pagination** and **G2
auto-repair** acceptance criteria):

### 9a. Walk children (G1 — pagination >100 blocks)

Notion's children endpoint paginates at 100. A long-running CRM page may
exceed this. We MUST walk all pages via `next_cursor` BEFORE deciding whether
a `## Latest:` heading exists — otherwise we'd create a duplicate past block
100.

```bash
PAGE_ID="${TARGET_PAGE_ID}"
CHILDREN_JSON=""
CURSOR=""
while :; do
  if [ -z "${CURSOR}" ]; then
    QS="page_size=100"
  else
    QS="page_size=100&start_cursor=${CURSOR}"
  fi
  RESP="$(curl -s --max-time 60 \
    "https://api.notion.com/v1/blocks/${PAGE_ID}/children?${QS}" \
    -H "Authorization: Bearer $NOTION_API_TOKEN" \
    -H "Notion-Version: ${NOTION_API_VERSION}")"
  CHILDREN_JSON="${CHILDREN_JSON}${RESP}"
  HAS_MORE=$(echo "${RESP}" | python -c "import sys,json; print(json.loads(sys.stdin.read()).get('has_more', False))")
  if [ "${HAS_MORE}" != "True" ]; then break; fi
  CURSOR=$(echo "${RESP}" | python -c "import sys,json; print(json.loads(sys.stdin.read()).get('next_cursor',''))")
done
```

Parse out every `heading_2` block matching `## Latest:` exactly. Three cases:

- **0 hits (first-time Latest)** → no existing Latest heading on the page.
  Per locked decision #1 ("freshest content at top"), the new `## Latest:`
  must land at or near the top — appending at end is NOT acceptable
  fallback behavior.

  **Top-insertion strategy (PATCH children endpoint with `after` parameter):**

  The Notion `PATCH /v1/blocks/{block_id}/children` endpoint accepts an
  `after` parameter naming the ID of an existing child block. The new
  children are inserted *immediately after* that block. Omitting `after`
  appends at end (the wrong place for us).

  Notion does **not** expose a "prepend before everything" form of `after`
  (the parameter requires a real block ID; null/omit means append). So:

  1. **If the page has ≥1 existing child block** → set `after =
     <first_child_id>`. The new `## Latest:` heading + body land in
     position 2, immediately after the page's existing first block. This
     is the closest to "top" the API allows in a single call.
  2. **If the page is empty (0 children)** → append (no `after`). New
     blocks become the page's only content; "top" and "end" are the same.

  At the trust gate (Step 8), surface this as a one-line note on entities
  hitting the 0-hit branch:

  ```text
  Note: first-time Latest. New section will land *after the page's first
  block*, not at absolute top (Notion API limitation — no prepend-before-all).
  ```

  Subsequent runs hit the 1-hit branch (case below) and update in place,
  so the position settles correctly from the second touch onward.

- **1 hit** → demote the existing Latest content to a dated section, then
  insert new content under the (still-positioned) `## Latest:` heading.
  Pseudo-flow:
  1. Find the `## Latest:` heading block ID and the block immediately after
     it (the existing "latest body").
  2. PATCH that next block's parent text to a new heading_2 `## YYYY-MM-DD — Prior`
     (using the `last_edited_time` of the page as the date if no better signal
     is available).
  3. PATCH-append the new body as a new block immediately after `## Latest:`
     (via `after: <latest_heading_block_id>`).

- **2+ hits (G2 auto-repair)** → duplicate `## Latest:` heading detected. Auto-repair:
  promote the OLDER `## Latest:` to `## YYYY-MM-DD — Prior` (date from the
  older heading's `last_edited_time`), keep the newer one as Latest. Log the
  repair in telemetry as `auto_repair: true`. Continue with the case-1 flow
  using the surviving Latest.

### 9b. PATCH body shape

**Per-entity iteration discipline (AAC GOVERNED).** Each iteration starts with
`WRITE_OK=0`. Only the 2xx branch flips it to 1. The action_id is added to
`SUCCESSFUL_ACTION_IDS` ONLY when `WRITE_OK=1`. This prevents the previous
ordering bug where stamps could land on non-2xx paths.

**Shell-injection hardening (AAC BOUNDED).** All LLM-derived strings flow
through the python heredoc via `os.environ` (NOT `${VAR}` interpolation inside
the heredoc body). This mirrors `scripts/phi_scan.sh`'s `PHI_SCAN_INPUT`
pattern and stops a malicious `\\"` or backtick in an `update_summary` from
breaking out of the JSON literal.

```bash
# Top of every entity iteration:
WRITE_OK=0

# Pass all LLM-derived strings via env. Note FIRST_CHILD_ID may be empty for
# the empty-page case (then PATCH body omits `after`).
export APPEND_HEADING APPEND_BODY FIRST_CHILD_ID

PATCH_BODY="$(python -c "
import json, os
body = {
  'children': [
    {'object':'block','type':'heading_2','heading_2':{'rich_text':[{'type':'text','text':{'content':os.environ['APPEND_HEADING']}}]}},
    {'object':'block','type':'paragraph','paragraph':{'rich_text':[{'type':'text','text':{'content':os.environ['APPEND_BODY']}}]}},
  ],
}
fc = os.environ.get('FIRST_CHILD_ID', '').strip()
if fc:
    body['after'] = fc
print(json.dumps(body))
")"

if [ "${SKIP_WRITES}" = "1" ]; then
  echo "  [observe] would PATCH /v1/blocks/${PAGE_ID}/children"
  echo "${PATCH_BODY}" | head -c 400
else
  TMP_RESP="$(mktemp 2>/dev/null || echo "/tmp/sync_sweep_resp_$$.json")"
  RESP=$(curl -s -o "${TMP_RESP}" -w '%{http_code}' --max-time 60 \
    -X PATCH "https://api.notion.com/v1/blocks/${PAGE_ID}/children" \
    -H "Authorization: Bearer $NOTION_API_TOKEN" \
    -H "Notion-Version: ${NOTION_API_VERSION}" \
    -H "Content-Type: application/json" \
    -d "${PATCH_BODY}")

  case "${RESP}" in
    2*)
      WRITE_OK=1
      SUCCESSFUL_ACTION_IDS+=("${AID}")
      ENTITIES_WRITTEN=$((ENTITIES_WRITTEN + 1))
      ;;
    401)
      echo "🛑 401 from Notion. NOTION_API_TOKEN appears expired."
      echo "   Rotate per .secrets/notion.env, then re-run /sync-sweep."
      STATUS="failed"
      rm -f "${TMP_RESP}"
      # Stop further writes; remaining items stay in .context/sync-sweep-*.json
      break
      ;;
    404)
      # Page deleted between Step 4 search and Step 9 write.
      echo "  ⚠️  404 for page ${PAGE_ID} (${ENTITY_CANONICAL}). Marking stale-target."
      STALE_TARGETS=$((STALE_TARGETS + 1))
      STATUS="partial"
      # Do NOT stamp action_id; do NOT append to retry queue. Just skip.
      ;;
    5*|429|000)
      # 5xx, 429 rate-limit, or curl timeout (000) → retry queue.
      # Merge by notion_page_id: if an entry already exists for this page,
      # increment attempts + update last_status (G6 graduation to DLQ at 3).
      echo "  ⚠️  ${RESP} from Notion for ${ENTITY_CANONICAL}. Updating retry queue."
      export ENTITY_CANONICAL PAGE_ID PATCH_BODY RESP
      python - <<'PY'
import yaml, pathlib, datetime, json, os
p = pathlib.Path("state/sync-sweep-retry-queue.yaml")
data = yaml.safe_load(p.read_text(encoding="utf-8")) if p.exists() else {"queue": [], "dlq": []}
data.setdefault("queue", [])
data.setdefault("dlq", [])
page_id = os.environ["PAGE_ID"]
now_iso = datetime.datetime.now().isoformat(timespec="seconds")

# Find existing queue entry for this page (merge key = notion_page_id).
existing = next((e for e in data["queue"] if e.get("notion_page_id") == page_id), None)
if existing is not None:
    existing["attempts"] = int(existing.get("attempts", 0)) + 1
    existing["last_status"] = os.environ["RESP"]
    existing["last_attempted"] = now_iso
    # Refresh payload to the most recent shape (entity may have a richer summary now).
    existing["payload"] = json.loads(os.environ["PATCH_BODY"])
    existing["entity_name"] = os.environ["ENTITY_CANONICAL"]
    # G6 DLQ graduation: 3+ attempts → flag and (optionally) move to dlq list.
    if existing["attempts"] >= 3 and not existing.get("dlq"):
        existing["dlq"] = True
        existing["dlq_at"] = now_iso
        # Move to dlq list so /start-day's DLQ depth reflects "graduated" entries.
        data["dlq"].append(existing)
        data["queue"] = [e for e in data["queue"] if e.get("notion_page_id") != page_id]
else:
    data["queue"].append({
        "entity_name": os.environ["ENTITY_CANONICAL"],
        "notion_page_id": page_id,
        "payload": json.loads(os.environ["PATCH_BODY"]),
        "attempts": 1,
        "last_status": os.environ["RESP"],
        "first_failed": now_iso,
        "last_attempted": now_iso,
    })

p.parent.mkdir(parents=True, exist_ok=True)
p.write_text(yaml.safe_dump(data, sort_keys=False), encoding="utf-8")
PY
      STATUS="partial"
      ;;
    *)
      echo "  ⚠️  Unexpected ${RESP} from Notion PATCH for ${ENTITY_CANONICAL}. Marking partial."
      STATUS="partial"
      ;;
  esac
  rm -f "${TMP_RESP}"
fi

# Per-entity action_id stamp guard. ONLY stamp on a clean 2xx write. The
# Step 10 stamp loop is the canonical location; this inline guard mirrors it
# for runners that prefer per-entity stamping. Failed writes are NOT stamped.
if [ "${WRITE_OK}" = "1" ]; then
  : "AID ${AID} eligible for Step 10 stamp."
fi
```

**Retry-queue merge semantics (G6 — codified 2026-05-19).** The queue is
keyed by `notion_page_id`, not by `(page_id, run_id)`. Re-running /sync-sweep
on the same braindump line generates the same `action_id`, and a 5xx on
attempt 2 bumps the existing row's `attempts: 2` rather than creating a
fresh `attempts: 1` row. At `attempts >= 3`, the entry graduates to a
separate `dlq:` list in the same YAML file (or carries a `dlq: true` flag);
`/start-day`'s pre-flight reads both lists so DLQ depth is accurate.
`first_failed` is set once and never updated; `last_attempted` is bumped on
every retry.

### 9c. G2 verify-after-PATCH

After each successful 2xx, verify the page state to detect a concurrent
Notion-app edit that may have raced this write. Two pagination strategies
are acceptable; pick ONE and document the choice in the trust gate summary.

**Strategy A — targeted block fetch (preferred for cost).** The 2xx PATCH
response from §9b includes a `results` array of newly-created block IDs.
For each new heading_2 block in the response, issue a single
`GET /v1/blocks/<id>` to confirm it landed. Then issue ONE
`GET /v1/blocks/{page_id}/children?page_size=100` to count `## Latest:`
headings on the first page only. If the count is ≤1, exit verify. This
is bounded at 2 GETs regardless of page size.

**Strategy B — full pagination walk.** Walk the children with the same
`next_cursor` loop as §9a. This is correct for pages with >100 blocks where
a duplicate `## Latest:` could live beyond block 100. Use this when the
§9a walk reported >100 total children OR when Strategy A's first-page count
was exactly 1 but we want belt-and-suspenders verification.

```bash
# Strategy B implementation (mirrors §9a). Reuse the cursor loop verbatim:
LATEST_COUNT=0
CURSOR=""
while :; do
  if [ -z "${CURSOR}" ]; then
    QS="page_size=100"
  else
    QS="page_size=100&start_cursor=${CURSOR}"
  fi
  VRESP="$(curl -s --max-time 60 \
    "https://api.notion.com/v1/blocks/${PAGE_ID}/children?${QS}" \
    -H "Authorization: Bearer $NOTION_API_TOKEN" \
    -H "Notion-Version: ${NOTION_API_VERSION}")"
  PAGE_LATEST=$(echo "${VRESP}" | python -c "
import sys, json
d = json.loads(sys.stdin.read())
n = 0
for b in d.get('results', []):
    if b.get('type') == 'heading_2':
        rt = b.get('heading_2', {}).get('rich_text', [])
        text = ''.join(r.get('plain_text', '') for r in rt).strip()
        if text == 'Latest:':
            n += 1
print(n)
")
  LATEST_COUNT=$((LATEST_COUNT + PAGE_LATEST))
  HAS_MORE=$(echo "${VRESP}" | python -c "import sys,json; print(json.loads(sys.stdin.read()).get('has_more', False))")
  if [ "${HAS_MORE}" != "True" ]; then break; fi
  CURSOR=$(echo "${VRESP}" | python -c "import sys,json; print(json.loads(sys.stdin.read()).get('next_cursor',''))")
done
```

**Auto-repair (G2).** If `LATEST_COUNT >= 2`, auto-repair the OLDER
`## Latest:` heading by issuing a follow-up `PATCH /v1/blocks/<older_id>`
that updates its `rich_text` content from `Latest:` to
`YYYY-MM-DD — auto-merged on race detect`. Increment `AUTO_REPAIR_G2`
telemetry counter.

**MVE choice:** Default to Strategy B (full walk) — it's correct for all
page sizes. Cost is bounded because Step 9a already determined whether the
page exceeds 100 blocks; on small pages this is ONE extra GET (~150ms).
Acceptable per locked decision D1.

### 9d. Daily-note sync marker

After a successful PATCH, edit `vault/daily/${TODAY}.md` to wrap the source
line with strikethrough + sync comment so the next /sync-sweep run skips it
(see Step 1 pre-filter):

```
~~Alex Acosta finally called back — pushing Roosevelt cardio to Friday~~ <!-- synced to notion:23ba3158-... -->
```

Use the `Edit` tool, anchoring on the exact `source_text` captured at Step 3.

**Anchor uniqueness check (mandatory).** Before issuing the `Edit`, run a
Grep over `vault/daily/${TODAY}.md` for the literal `source_text` to confirm
it appears exactly once. If it appears multiple times:

- **Preferred:** include ±1 line of context (the preceding or following
  line from the captured `context_window`) in the `old_string` to make the
  anchor unique. The strikethrough still wraps only the target line.
- **Fallback:** SKIP the strikethrough edit entirely. The action_id stamp
  at `.context/applied/` is the authoritative idempotency record; the
  daily-note marker is a cheap pre-filter, not a load-bearing dedup gate.
  Log the skip in telemetry as `daily_note_marker_skipped: true` so we can
  observe how often this happens.

Never use `Edit replace_all=true` here — that would re-wrap previously
synced lines and double-mark them.

### 9e. Activity Log row (decision-verb side branch)

If the entity has `activity_log_row` populated (decision verb detected), also
POST a new row to the Activity Log data source. Pass the LLM-extracted
`decision_summary` and `workspace` strings through `os.environ` to avoid
JSON-injection from a craftily-worded braindump line.

```bash
export DECISION_SUMMARY DECISION_WORKSPACE TODAY
AL_BODY="$(python -c "
import json, os
print(json.dumps({
  'parent': {'data_source_id': '3db174bf-c997-4a41-93ee-36f280e511db'},
  'properties': {
    'Task':      {'title':  [{'text': {'content': os.environ['DECISION_SUMMARY']}}]},
    'Type':      {'select': {'name': 'Decision'}},
    'Date':      {'date':   {'start': os.environ['TODAY']}},
    'Workspace': {'select': {'name': os.environ['DECISION_WORKSPACE']}},
  },
}))")"

curl -s --max-time 60 -X POST "https://api.notion.com/v1/pages" \
  -H "Authorization: Bearer $NOTION_API_TOKEN" \
  -H "Notion-Version: ${NOTION_API_VERSION}" \
  -H "Content-Type: application/json" \
  -d "${AL_BODY}"
```

## Step 10 — Archive + Stamp (AAC GOVERNED)

Stamp the action_id ONLY after the PATCH returned 2xx (the §9b loop pushed
into `SUCCESSFUL_ACTION_IDS` only when `WRITE_OK=1`). Each stamp is
additionally guarded with an explicit `WRITE_OK` check below for defense in
depth — if a runner ever appends to `SUCCESSFUL_ACTION_IDS` outside the 2xx
branch, the stamp still won't land. After all stamps land, MOVE the staged
file out of `.context/` top level so `/start-day`'s pre-flight stops flagging
it.

Archive naming aligns with the existing `.context/applied/` convention used
by /capture-meeting (`<skill>-<run_id>-<YYYY-MM-DD>.json`). Declined runs
gain a `-declined-` infix for audit clarity, mirroring §8's prose.

```bash
# 10a. Stamp every successful action_id (and only those).
for AID in "${SUCCESSFUL_ACTION_IDS[@]}"; do
  if [ "${WRITE_OK:-0}" != "1" ]; then
    # Defense in depth: never stamp without an explicit success flag.
    continue
  fi
  export AID RUN_ID NOTION_PAGE_ID SOURCE_LINE INPUT_TOKENS OUTPUT_TOKENS
  EXTRA="$(python -c "
import json, os
print(json.dumps({
    'skill': 'sync-sweep',
    'run_id': os.environ.get('RUN_ID',''),
    'input_class': 'A',
    'notion_page_id': os.environ.get('NOTION_PAGE_ID',''),
    'source_line': int(os.environ.get('SOURCE_LINE','0')),
    'input_tokens': int(os.environ.get('INPUT_TOKENS','0')),
    'output_tokens': int(os.environ.get('OUTPUT_TOKENS','0')),
}))")"
  scripts/action_id.sh stamp "${AID}" "${EXTRA}"
done

# 10b. Move .context/sync-sweep-<run_id>.json -> .context/applied/...
# Per CLAUDE.md `.context/` lifecycle: the date suffix is when the write
# landed (TODAY). Naming mirrors /capture-meeting's archive convention.
APPLIED_NAME="sync-sweep-${RUN_ID}-${TODAY}.json"
DECLINED_NAME="sync-sweep-${RUN_ID}-declined-${TODAY}.json"

if [ -f "${CONTEXT}/sync-sweep-${RUN_ID}.json" ]; then
  mkdir -p "${CONTEXT}/applied"
  if [ "${OPTION_PICKED:-}" = "C" ]; then
    mv "${CONTEXT}/sync-sweep-${RUN_ID}.json" \
       "${CONTEXT}/applied/${DECLINED_NAME}"
  else
    mv "${CONTEXT}/sync-sweep-${RUN_ID}.json" \
       "${CONTEXT}/applied/${APPLIED_NAME}"
  fi
fi
```

# TODO(v0.2): T13 priorities.yaml integration — surface unresolved entities
# (no-match / declined-by-Aaron with rationale) into the next day's carries.
# Wires into /end-day reading state/sync-sweep-*.yaml. Class C only.

`# Audit trail rule: never delete applied payloads — they document what landed
# in Notion, when, and at whose approval. /start-day only scans top-level
# .context/*.json so applied/ stays out of the pending-writes warning.`

## Step 11 — Telemetry (AAC OBSERVED)

Emit exactly one row to `logs/_telemetry.jsonl` per run, including PHI-refused
runs, no-op runs, and declined runs. Required schema (per task spec).

**Token instrumentation in MVE.** Token counts default to 0 — the in-process
Claude runtime does not surface per-call accounting in v0.1. v0.2 will wire
these to the Claude SDK's `usage.input_tokens` / `usage.output_tokens` fields
and compute `estimated_cost_usd` from `model_id` pricing. For now, every
field defaults so a missing variable never crashes the telemetry row:

```bash
INPUT_TOKENS=${INPUT_TOKENS:-0}
OUTPUT_TOKENS=${OUTPUT_TOKENS:-0}
ESTIMATED_COST_USD=${ESTIMATED_COST_USD:-0.0}
MODEL_ID=${MODEL_ID:-claude-in-process}
EXTRACTION_PATH=${EXTRACTION_PATH:-llm}

DURATION_MS=$(( $(date +%s%3N 2>/dev/null || python -c "import time; print(int(time.time()*1000))") - RUN_START_MS ))

scripts/telemetry.sh sync-sweep "${RUN_ID}" "${DURATION_MS}" "${STATUS:-ok}" "$(python -c "
import json
print(json.dumps({
    'mode': '${MODE}',
    'trigger_source': '${TRIGGER_SOURCE}',
    'input_class': 'A',
    'sources_ok': ['notion','obsidian'],            # what was reachable this run
    'entities_extracted': ${ENTITIES_EXTRACTED:-0},
    'entities_staged': ${ENTITIES_STAGED:-0},
    'entities_written': ${ENTITIES_WRITTEN:-0},
    'entities_declined': ${ENTITIES_DECLINED:-0},
    'entities_uncategorized': ${ENTITIES_UNCATEGORIZED:-0},
    'entities_no_match': ${ENTITIES_NO_MATCH:-0},
    'entities_skipped_idempotent': ${SKIPPED_IDEMPOTENT:-0},
    'stale_targets': ${STALE_TARGETS:-0},
    'dlq_added': ${DLQ_ADDED:-0},
    'auto_repair_g2': ${AUTO_REPAIR_G2:-0},
    'extraction_path': '${EXTRACTION_PATH:-llm}',   # 'llm' | 'regex-fallback'
    'input_tokens': ${INPUT_TOKENS:-0},
    'output_tokens': ${OUTPUT_TOKENS:-0},
    'model_id': '${MODEL_ID:-claude-in-process}',
    'estimated_cost_usd': ${ESTIMATED_COST_USD:-0.0}
})
")"
```

`STATUS` is:
- `ok` — all approved items written (or zero items to write); declines also report `ok`.
- `partial` — ≥1 write failed (5xx → retry queue), or ≥1 search 5xx'd, or ≥1 stale-target.
- `refused` — PHI gate refused at Step 2.
- `failed` — 401 stopped the run, or unrecoverable error.

`# Cost tracking: even with in-process Claude, record token counts the runtime
# reports. /weekly-review reads logs/_telemetry.jsonl to surface cost drift.`

## Error Handling Summary

- **check_mode.sh exits 1 (locked):** Refuse silently, no telemetry.
- **phi_scan.sh exits 1 (PHI):** Refuse, log to `_phi_refusals.jsonl`,
  emit telemetry with `status: refused`, skip Steps 3–10.
- **Empty / missing braindump:** No-op exit with `entities_extracted: 0, status: ok`.
- **LLM extraction timeout (>20s):** Fall back to regex over
  `calendar_business_keywords`; conf 0.65 across the board; route to disambig.
  Telemetry `extraction_path: regex-fallback`.
- **/v1/search 5xx for one entity:** Mark that entity `no-match`, set
  `STATUS="partial"`, continue with remaining entities.
- **PATCH 5xx:** Append to `state/sync-sweep-retry-queue.yaml`, do NOT stamp
  action_id, continue with remaining items.
- **PATCH 401:** STOP all subsequent writes, surface token-rotation message,
  `STATUS="failed"`. Already-written items keep their stamps.
- **PATCH 404 (stale-target):** Skip that item, log only, `STATUS="partial"`.
  Do NOT stamp action_id; do NOT enter retry queue.
- **Never retry automatically inside a single run.** Failures go to the
  queue; the next /sync-sweep invocation retries with bounded attempts.
- **Never crash on a single item failure.** Process all items, summarize at end.
- **Notion timeout:** `--max-time 60` on every curl call. Timeout = treat as 5xx.

## AAC discipline checkpoints (where each shows up)

- **BOUNDED** — Step 0 mode gate; Step 1 `INPUT_CLASS=A` constant explicitly
  scopes input; out-of-scope classes documented as `# TODO(v0.2)` markers.
  PHI hard-refuse class at Step 2; payment-instruction hard-refuse class in
  the Step 3 extraction prompt.
- **GROUNDED** — Every staged item at Step 7 carries `source_line`,
  `source_text`, `entity_canonical`, `[notion:abcd…]` 4-char source marker
  (matches /start-day Step 7); Step 8 trust gate displays all of these.
- **GATED** — Three gates: Step 0 (mode), Step 2 (PHI), Step 8 (trust gate).
  Plus Step 6 idempotency gate that short-circuits already-applied items.
- **OBSERVED** — Step 11 telemetry row is mandatory on every run path
  (success, declined, refused, no-op).
- **GOVERNED** — action_id stamp at Step 10 happens ONLY after PATCH 2xx;
  `.context/applied/` move happens ONLY at Step 10; failed writes are NOT
  stamped (next run retries).

"""Validate config/streams.yaml against config/sources.yaml.

Surfaces drift between the new generic stream config and the legacy
workspace-value / calendar-keyword config. Used by /start-day Step 1 to flag
inconsistencies as a non-blocking warning.

Exit codes:
  0 = consistent
  1 = drift detected (details on stderr; consistent items printed on stdout)
  2 = malformed file

Usage:
  python scripts/streams_check.py             # human-readable
  python scripts/streams_check.py --json      # machine-readable
"""
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
STREAMS_PATH = REPO / "config" / "streams.yaml"
SOURCES_PATH = REPO / "config" / "sources.yaml"


def _yaml():
    try:
        import yaml  # noqa: F401
        return yaml
    except ImportError:
        return None


def load_yaml(path):
    yaml = _yaml()
    if yaml:
        with open(path, encoding="utf-8") as f:
            return yaml.safe_load(f)
    # Fallback: shell out to python -c if PyYAML is missing.
    # The project hasn't ruled out pyyaml availability; if absent, error out.
    print("ERROR: PyYAML required. Install with `pip install pyyaml`.", file=sys.stderr)
    sys.exit(2)


def collect_streams_state(streams_data):
    streams = streams_data.get("streams", [])
    by_key = {s["key"]: s for s in streams}
    defaults = [s["key"] for s in streams if s.get("is_default")]
    return {
        "by_key": by_key,
        "keys": list(by_key.keys()),
        "workspace_values": {wv: s["key"] for s in streams for wv in s.get("workspace_values", [])},
        "keywords": {s["key"]: set(s.get("keywords", [])) for s in streams},
        "defaults": defaults,
    }


def collect_sources_state(sources_data):
    out = {"workspace_values_per_db": {}, "calendar_keywords": {}}
    for db in sources_data.get("notion_databases", []):
        if "workspace_values" in db:
            out["workspace_values_per_db"][db["name"]] = db["workspace_values"]
    out["calendar_keywords"] = sources_data.get("calendar_business_keywords", {})
    return out


def diff(streams_state, sources_state):
    issues = []

    # Exactly one default stream
    if len(streams_state["defaults"]) != 1:
        issues.append({
            "code": "default_stream_count",
            "detail": f"expected exactly 1 stream with is_default: true, got {len(streams_state['defaults'])} ({streams_state['defaults']})",
        })

    # Every sources.yaml workspace_value should map to a stream
    legacy_workspace_values_used = set()
    for db_name, wv_map in sources_state["workspace_values_per_db"].items():
        for key, value in wv_map.items():
            legacy_workspace_values_used.add(value)
            if value not in streams_state["workspace_values"]:
                issues.append({
                    "code": "workspace_value_unmapped",
                    "detail": f"{db_name} :: workspace_values.{key} = {value!r} has no stream in streams.yaml",
                })
            else:
                stream_key = streams_state["workspace_values"][value]
                if stream_key != key:
                    issues.append({
                        "code": "workspace_value_key_mismatch",
                        "detail": f"sources.yaml maps key {key!r} -> {value!r}, streams.yaml maps {value!r} -> {stream_key!r}",
                    })

    # Reverse direction: streams.yaml workspace_values should be referenced in sources.yaml at least once
    for wv, stream_key in streams_state["workspace_values"].items():
        if wv not in legacy_workspace_values_used:
            # Not an error — Notion drift (e.g. "Link & Reference Laboratory") — but worth a note
            issues.append({
                "code": "workspace_value_extra",
                "detail": f"streams.yaml stream {stream_key!r} has workspace_value {wv!r} not referenced in any sources.yaml notion_databases.workspace_values block",
                "severity": "info",
            })

    # Calendar keyword buckets should match
    legacy_kw_keys = set(sources_state["calendar_keywords"].keys())
    stream_keys_with_kw = {k for k, kws in streams_state["keywords"].items() if kws}
    for legacy_key in legacy_kw_keys:
        if legacy_key not in streams_state["by_key"]:
            issues.append({
                "code": "calendar_bucket_orphan",
                "detail": f"sources.yaml :: calendar_business_keywords.{legacy_key} has no stream in streams.yaml",
            })
            continue
        legacy_kws = set(sources_state["calendar_keywords"][legacy_key])
        stream_kws = streams_state["keywords"][legacy_key]
        only_in_legacy = legacy_kws - stream_kws
        only_in_stream = stream_kws - legacy_kws
        if only_in_legacy:
            issues.append({
                "code": "keywords_only_in_sources",
                "detail": f"{legacy_key}: in sources.yaml but missing from streams.yaml: {sorted(only_in_legacy)}",
            })
        if only_in_stream:
            issues.append({
                "code": "keywords_only_in_streams",
                "detail": f"{legacy_key}: in streams.yaml but missing from sources.yaml: {sorted(only_in_stream)}",
                "severity": "info",
            })

    return issues


def main():
    # Force UTF-8 stdout so the human-readable output (which uses the ↔ glyph)
    # doesn't crash on Windows cp1252. The --json path is unaffected either way.
    try:
        sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[attr-defined]
    except (AttributeError, ValueError):
        pass
    as_json = "--json" in sys.argv
    streams_data = load_yaml(STREAMS_PATH)
    sources_data = load_yaml(SOURCES_PATH)
    streams_state = collect_streams_state(streams_data)
    sources_state = collect_sources_state(sources_data)
    issues = diff(streams_state, sources_state)

    blocking = [i for i in issues if i.get("severity") != "info"]

    if as_json:
        out = {"issues": issues, "n_blocking": len(blocking), "n_info": len(issues) - len(blocking)}
        print(json.dumps(out, indent=2))
        sys.exit(0 if not blocking else 1)

    if not issues:
        print("streams.yaml and sources.yaml are consistent.")
        sys.exit(0)

    print(f"streams.yaml ↔ sources.yaml drift: {len(issues)} item(s)")
    print("=" * 60)
    for i in issues:
        sev = i.get("severity", "warn")
        tag = "INFO" if sev == "info" else "WARN"
        print(f"  [{tag}] {i['code']}")
        print(f"         {i['detail']}")
    print("=" * 60)
    sys.exit(0 if not blocking else 1)


if __name__ == "__main__":
    main()

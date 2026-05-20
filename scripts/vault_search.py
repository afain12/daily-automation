#!/usr/bin/env python3
"""
scripts/vault_search.py — BM25-lite search over the Obsidian vault + logs.

Wave 2 of the enhancement plan. Addresses: /start-day can't surface relevant
past decisions / prior meetings from vault/ when planning today. Pure-Python,
no embeddings, no ripgrep dependency — runs on the same laptop that runs every
other COO Twin skill.

Defaults search across:
  - vault/notes      (evergreen / permanent notes)
  - vault/daily      (daily notes — past briefings + braindumps)
  - logs/            (daily briefing + EOD retro markdown logs)
  - vault/meetings   (meeting notes)

Usage:
  python scripts/vault_search.py "biller proposal kader"
  python scripts/vault_search.py "essen 4/21" --top-n 3
  python scripts/vault_search.py "cardiopro back burner" --json
  python scripts/vault_search.py "kader" --paths vault/notes,vault/meetings

Output (default text mode):
  1. [3.42] vault/daily/2026-05-13.md
     Tim ENG closed for the lab — the dock_pro mapping was stale...
  2. [2.91] vault/notes/Kader-touchpoints.md
     Multi-dept contact: lab (Lincoln/Essen) and ipa (SAIPA cleanup)...
  ...

Scoring: BM25-lite. Tokenize query (lowercased, stopwords dropped), tokenize each
doc, compute TF * IDF with length normalization. Good enough to validate the
pattern; if telemetry shows it underperforms after 2 weeks, escalate to embeddings.
"""

from __future__ import annotations
import argparse
import json
import math
import re
import sys
from pathlib import Path

REPO_DIR = Path(__file__).resolve().parent.parent

DEFAULT_PATHS = [
    "vault/notes",
    "vault/daily",
    "vault/meetings",
    "logs",
]

# Minimal English stopword list. Resist the urge to grow this — too many
# stopwords hurts recall on short queries like "afc visit".
STOPWORDS = {
    "a", "an", "the", "and", "or", "but", "if", "then", "to", "of", "in",
    "on", "at", "for", "with", "by", "from", "is", "are", "was", "were",
    "be", "been", "being", "have", "has", "had", "do", "does", "did",
    "this", "that", "these", "those", "it", "its", "i", "we", "you",
    "he", "she", "they", "them", "his", "her", "their", "as", "so",
}

# BM25 parameters (Robertson/Spärck Jones defaults).
K1 = 1.5
B = 0.75

TOKEN_RE = re.compile(r"[a-z0-9][a-z0-9'_-]*")


def tokenize(text: str) -> list[str]:
    """Lowercase + split on word boundaries; drop stopwords and 1-char tokens."""
    return [
        t for t in TOKEN_RE.findall(text.lower())
        if len(t) > 1 and t not in STOPWORDS
    ]


def collect_docs(paths: list[Path]) -> list[tuple[Path, list[str]]]:
    """Walk paths for *.md, return (path, tokens) per file. Skip empty files."""
    docs = []
    for root in paths:
        if not root.exists():
            continue
        for p in root.rglob("*.md"):
            try:
                text = p.read_text(encoding="utf-8", errors="replace")
            except (OSError, UnicodeDecodeError):
                continue
            if not text.strip():
                continue
            tokens = tokenize(text)
            if tokens:
                docs.append((p, tokens))
    return docs


def bm25_score(query_tokens: list[str], doc_tokens: list[str],
               df: dict[str, int], n_docs: int, avg_dlen: float) -> float:
    """Standard BM25 score for one doc against the query."""
    dlen = len(doc_tokens)
    # Build term-frequency for this doc once per query (cheaper than dict per term).
    tf: dict[str, int] = {}
    for t in doc_tokens:
        tf[t] = tf.get(t, 0) + 1

    score = 0.0
    for q in query_tokens:
        f = tf.get(q, 0)
        if f == 0:
            continue
        # IDF (BM25's smoothed variant).
        idf = math.log((n_docs - df.get(q, 0) + 0.5) / (df.get(q, 0) + 0.5) + 1.0)
        denom = f + K1 * (1 - B + B * dlen / max(avg_dlen, 1.0))
        score += idf * (f * (K1 + 1)) / denom
    return score


def snippet(path: Path, query_tokens: list[str], width: int = 120) -> str:
    """Return a short snippet around the first query-token hit."""
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except (OSError, UnicodeDecodeError):
        return ""

    text_l = text.lower()
    best_pos = -1
    for q in query_tokens:
        pos = text_l.find(q)
        if pos != -1 and (best_pos == -1 or pos < best_pos):
            best_pos = pos
    if best_pos == -1:
        # Fall back to first non-blank line
        for line in text.splitlines():
            s = line.strip()
            if s:
                return s[:width]
        return ""

    start = max(0, best_pos - width // 3)
    end = min(len(text), best_pos + 2 * width // 3)
    chunk = text[start:end].replace("\n", " ").strip()
    return ("…" if start > 0 else "") + chunk + ("…" if end < len(text) else "")


def main(argv: list[str] | None = None) -> int:
    # Windows defaults stdout to cp1252; vault files routinely contain em-dashes,
    # curly quotes, and other non-ASCII. Force UTF-8 so snippets render correctly.
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except (AttributeError, ValueError):
        pass

    ap = argparse.ArgumentParser(description="BM25-lite search over vault + logs.")
    ap.add_argument("query", help="Free-text query.")
    ap.add_argument("--paths", default=",".join(DEFAULT_PATHS),
                    help="Comma-separated relative paths to search.")
    ap.add_argument("--top-n", type=int, default=5,
                    help="Number of results to return (default 5).")
    ap.add_argument("--json", action="store_true", help="Emit JSON instead of text.")
    ap.add_argument("--min-score", type=float, default=0.5,
                    help="Hide results scoring below this threshold (default 0.5).")
    args = ap.parse_args(argv)

    query_tokens = tokenize(args.query)
    if not query_tokens:
        print("vault_search: query has no searchable tokens (all stopwords?).",
              file=sys.stderr)
        return 2

    paths = [REPO_DIR / p.strip() for p in args.paths.split(",") if p.strip()]
    docs = collect_docs(paths)
    if not docs:
        if args.json:
            print(json.dumps({"query": args.query, "results": []}))
        else:
            print("vault_search: no .md files found in search paths.", file=sys.stderr)
        return 0

    # Document frequency per query token.
    df: dict[str, int] = {q: 0 for q in query_tokens}
    for _path, toks in docs:
        seen = set(toks)
        for q in query_tokens:
            if q in seen:
                df[q] += 1

    n_docs = len(docs)
    avg_dlen = sum(len(toks) for _, toks in docs) / n_docs

    scored = []
    for path, toks in docs:
        s = bm25_score(query_tokens, toks, df, n_docs, avg_dlen)
        if s >= args.min_score:
            scored.append((s, path))

    scored.sort(key=lambda x: -x[0])
    top = scored[: args.top_n]

    results = []
    for score, path in top:
        rel = path.relative_to(REPO_DIR).as_posix()
        results.append({
            "path": rel,
            "score": round(score, 3),
            "snippet": snippet(path, query_tokens),
        })

    if args.json:
        print(json.dumps({
            "query": args.query,
            "tokens": query_tokens,
            "n_docs_searched": n_docs,
            "results": results,
        }, indent=2))
    else:
        if not results:
            print(f"vault_search: no matches above min_score={args.min_score} "
                  f"for {query_tokens!r}", file=sys.stderr)
            return 0
        for i, r in enumerate(results, 1):
            print(f"{i}. [{r['score']:.2f}] {r['path']}")
            if r["snippet"]:
                print(f"   {r['snippet']}")
            print()

    return 0


if __name__ == "__main__":
    sys.exit(main())

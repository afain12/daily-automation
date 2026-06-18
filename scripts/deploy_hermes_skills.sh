#!/usr/bin/env bash
# deploy_hermes_skills.sh — reversible Hermes skill deploy + verify harness.
#
# The .claude copy and the ~/.hermes runtime copy of a COO Twin skill legitimately
# DIVERGE: the Hermes copy carries environmental adaptations (macOS REPO_DIR paths,
# the gws->google_api.py substitution, Notion token file-read pitfalls, NoneType
# guards, the degraded-pass section). So this is NOT a `cp` — a blind copy would
# clobber the adaptations that make the live morning runtime work.
#
# The surgical mirror of shared steps (contract #8) is done by hand (Edit). This
# script's job is the two things that make that edit SAFE:
#   1. backup  — timestamped snapshot of the live Hermes copy BEFORE you edit it,
#                so any mistake is one `restore` away.
#   2. verify  — after the edit, run skill_lint + the contract-anchor greps + the
#                output_planning unit tests against the result.
#
# ponytail: backup+verify wrapper, not a sync engine. The copies can't be byte-equal,
# so there's nothing to auto-sync; reversibility + post-edit validation is the whole job.
#
# Usage:
#   scripts/deploy_hermes_skills.sh backup            # snapshot Hermes start-day before editing
#   scripts/deploy_hermes_skills.sh verify            # lint + anchors + tests after editing
#   scripts/deploy_hermes_skills.sh restore <file>    # roll back from a snapshot
set -euo pipefail

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
HERMES_SKILL="${HOME}/.hermes/skills/coo-twin/start-day/SKILL.md"
CLAUDE_SKILL="${REPO_DIR}/.claude/skills/start-day/SKILL.md"
BACKUP_DIR="${REPO_DIR}/.context/hermes-backups"

cmd="${1:-}"

case "$cmd" in
  backup)
    [ -f "$HERMES_SKILL" ] || { echo "FATAL: Hermes skill not found at $HERMES_SKILL" >&2; exit 1; }
    mkdir -p "$BACKUP_DIR"
    stamp="$(date +%Y%m%d-%H%M%S)"
    dest="${BACKUP_DIR}/start-day-SKILL.md.${stamp}.bak"
    cp "$HERMES_SKILL" "$dest"
    echo "backed up Hermes start-day -> $dest ($(wc -l < "$dest" | tr -d ' ') lines)"
    ;;

  verify)
    fail=0
    echo "=== skill_lint (Hermes copy) ==="
    if [ -x "${REPO_DIR}/scripts/skill_lint.sh" ]; then
      bash "${REPO_DIR}/scripts/skill_lint.sh" "$HERMES_SKILL" || fail=1
    else
      echo "skip: scripts/skill_lint.sh not executable"
    fi

    echo "=== contract anchors (must all be present in Hermes copy) ==="
    # Contract #2: the LOG heading. Contract #3: end-day regex anchor.
    # Restructure: the new primary sections must have landed.
    anchors=(
      "## Top 3 Outcomes"
      "## End of Day Review"
      "## Portfolio Pulse"
      "## Kill / Defer / Delegate"
      "## Meetings That Must Convert"
      "render_output_plan_markdown"
      "render_log_top3"
      "top3_leverage_classes"
    )
    for a in "${anchors[@]}"; do
      if grep -Fq "$a" "$HERMES_SKILL"; then
        echo "  ok: $a"
      else
        echo "  MISSING: $a" >&2; fail=1
      fi
    done

    # Contract #2 guard: the daily-note headline must NOT leak into the log heading
    # and vice-versa. The Hermes copy must keep BOTH headings, distinct.
    echo "=== bidirectional-heading sanity ==="
    grep -Fq "Today — Ship These 3" "$HERMES_SKILL" \
      && echo "  ok: daily-note headline present" \
      || { echo "  MISSING: 'Today — Ship These 3' headline" >&2; fail=1; }

    echo "=== output_planning unit tests ==="
    ( cd "$REPO_DIR" && python3 -m unittest discover -s tests -q ) || fail=1

    if [ "$fail" -eq 0 ]; then
      echo "VERIFY: PASS"
    else
      echo "VERIFY: FAIL" >&2; exit 1
    fi
    ;;

  restore)
    src="${2:-}"
    [ -n "$src" ] && [ -f "$src" ] || { echo "usage: $0 restore <backup-file>" >&2; exit 1; }
    cp "$src" "$HERMES_SKILL"
    echo "restored Hermes start-day from $src"
    ;;

  *)
    echo "usage: $0 {backup|verify|restore <file>}" >&2
    exit 1
    ;;
esac

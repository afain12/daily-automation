#!/usr/bin/env bash
# Ingest vault/*.md into the local gbrain "daily-automation-vault" source.
# Workaround for gbrain's "git repo required" rule on `gbrain import` and the
# Windows /dev/stdin bug that makes `gbrain put <slug> < file` fail.
# Uses `--content` (the working code path) per file.

set -u  # not -e: keep going even if one file fails

VAULT="${VAULT:-vault}"
SOURCE="${SOURCE:-daily-automation-vault}"
COUNT_OK=0
COUNT_FAIL=0
FAILED_FILES=()

if [ ! -d "$VAULT" ]; then
  echo "Error: vault dir not found at $VAULT" >&2
  exit 1
fi

# Verify source exists
if ! gbrain sources list --json 2>/dev/null | grep -q "\"id\": \"$SOURCE\""; then
  echo "Error: source '$SOURCE' not registered. Run:" >&2
  echo "  gbrain sources add $SOURCE --path \$(pwd)/$VAULT --federated" >&2
  exit 2
fi

while IFS= read -r file; do
  rel="${file#$VAULT/}"
  slug="${rel%.md}"
  # Slug rules: lowercase alnum-hyphen-slash. Replace spaces + special chars.
  slug=$(echo "$slug" | tr ' ' '-' | tr -cd 'a-zA-Z0-9/_.-' | tr '[:upper:]' '[:lower:]')
  [ -z "$slug" ] && continue
  content=$(cat "$file" 2>/dev/null)
  [ -z "$content" ] && continue
  if gbrain put "$slug" --content "$content" --source "$SOURCE" >/dev/null 2>&1; then
    COUNT_OK=$((COUNT_OK + 1))
  else
    COUNT_FAIL=$((COUNT_FAIL + 1))
    FAILED_FILES+=("$file")
  fi
done < <(find "$VAULT" -name "*.md" -type f)

echo "Ingested: $COUNT_OK"
echo "Failed:   $COUNT_FAIL"
if [ "$COUNT_FAIL" -gt 0 ]; then
  printf '  - %s\n' "${FAILED_FILES[@]}" >&2
fi

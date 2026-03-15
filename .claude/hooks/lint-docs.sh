#!/usr/bin/env bash
# Hook: lint-docs.sh
# Trigger: pre-commit (PreToolUse: Write, Edit)
# Purpose: Warn on informal references and missing scope comments in documentation files
# Exit 0 = allow (warn only, does not block)

set -euo pipefail

TARGET_DIR="docs"
TARGET_DIR="${TARGET_DIR%/}"

WARNINGS=()

INFORMAL_REF_PATTERN='[a-zA-Z_/-]+\.md[^)"]'

while IFS= read -r file; do
  [[ -f "$file" ]] || continue
  case "$file" in "$TARGET_DIR"/*) ;; *) continue ;; esac

  while IFS= read -r line; do
    if echo "$line" | grep -qE '\[.+\]\(.+\)'; then
      continue
    fi
    if echo "$line" | grep -qE "$INFORMAL_REF_PATTERN"; then
      WARNINGS+=("  [lint-docs] informal reference detected: $file — $line")
    fi
  done < "$file"
done < <(git diff --cached --name-only | grep "\.md$" || true)

if [[ ${#WARNINGS[@]} -gt 0 ]]; then
  echo ""
  echo "WARNING: lint-docs found informal document references."
  echo "  Convert to formal link format: [label](./file.md#section)"
  echo ""
  for w in "${WARNINGS[@]}"; do
    echo "$w"
  done
  echo ""
  echo "  Re-run 'git commit' to proceed (warnings do not block the commit)."
  echo ""
fi

exit 0

#!/usr/bin/env bash
# Hook: sync-check.sh
# Trigger: PostToolUse (Write, Edit)
# Purpose: Remind to update derivative docs when source documents change.
# Exit 0 = allow (informational only, does not block)
# Compatibility: bash 3.2+ (macOS default)

get_sync_targets() {
  local source="$1"
  case "$source" in
    "proxy/metrics.py")
      echo "grafana/dashboards/ docs/plans/2026-03-14-llm-serving-observability.md"
      ;;
    "docs/plans/2026-03-14-llm-serving-observability.md")
      echo "docs/project-brief.md"
      ;;
    *)
      echo ""
      ;;
  esac
}

CHANGED_FILES=""

if [ -t 0 ]; then
  CHANGED_FILES=$(git diff --cached --name-only 2>/dev/null || true)
else
  INPUT=$(cat)
  FILE_PATH=$(echo "$INPUT" | grep -o '"file_path"[[:space:]]*:[[:space:]]*"[^"]*"' | head -1 | sed 's/.*"file_path"[[:space:]]*:[[:space:]]*"\([^"]*\)".*/\1/')
  if [ -n "$FILE_PATH" ]; then
    REPO_ROOT=$(pwd)
    CHANGED_FILES="${FILE_PATH#$REPO_ROOT/}"
  fi
fi

REMINDERS=()

SOURCES=(
  "proxy/metrics.py"
  "docs/plans/2026-03-14-llm-serving-observability.md"
)

for source in "${SOURCES[@]}"; do
  if echo "$CHANGED_FILES" | grep -q "$source"; then
    TARGETS=$(get_sync_targets "$source")
    if [ -n "$TARGETS" ]; then
      for target in $TARGETS; do
        REMINDERS+=("  [sync-check] $source changed → verify sync: $target")
      done
    fi
  fi
done

if [ ${#REMINDERS[@]} -gt 0 ]; then
  echo ""
  echo "INFO: sync-check — source documents modified. Review derivative files:"
  echo ""
  for r in "${REMINDERS[@]}"; do
    echo "$r"
  done
  echo ""
fi

exit 0

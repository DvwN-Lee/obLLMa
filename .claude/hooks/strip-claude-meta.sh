#!/usr/bin/env bash
# Hook: strip-claude-meta.sh
# Trigger: commit-msg (PostToolUse: Bash git commit)
# Purpose: Remove Claude-generated metadata lines from commit messages
#   - Removes "Co-Authored-By: Claude ..." lines
#   - Removes "Generated with [Claude Code](...)" lines
# Exit 0 = allow

set -euo pipefail

COMMIT_MSG_FILE="${1:-}"

if [[ -z "$COMMIT_MSG_FILE" || ! -f "$COMMIT_MSG_FILE" ]]; then
  # No file argument — nothing to strip
  exit 0
fi

# Strip Co-Authored-By lines referencing Claude/Anthropic
# Use temp file for cross-platform compatibility (macOS + Linux)
sed '/^Co-Authored-By:.*[Cc]laude/d' "$COMMIT_MSG_FILE" > "${COMMIT_MSG_FILE}.tmp" \
  && mv "${COMMIT_MSG_FILE}.tmp" "$COMMIT_MSG_FILE"
sed '/^Co-Authored-By:.*anthropic/Id' "$COMMIT_MSG_FILE" > "${COMMIT_MSG_FILE}.tmp" \
  && mv "${COMMIT_MSG_FILE}.tmp" "$COMMIT_MSG_FILE"

# Strip "Generated with [Claude Code](...)" trailer lines
sed '/Generated with \[Claude/d' "$COMMIT_MSG_FILE" > "${COMMIT_MSG_FILE}.tmp" \
  && mv "${COMMIT_MSG_FILE}.tmp" "$COMMIT_MSG_FILE"

# Remove trailing blank lines left after stripping
# (POSIX-safe: awk drops trailing empty lines)
awk '/^[[:space:]]*$/{blank++; next} {for(i=0;i<blank;i++) print ""; blank=0; print}' \
  "$COMMIT_MSG_FILE" > "${COMMIT_MSG_FILE}.tmp" \
  && mv "${COMMIT_MSG_FILE}.tmp" "$COMMIT_MSG_FILE"

exit 0

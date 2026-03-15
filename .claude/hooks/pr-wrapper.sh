#!/usr/bin/env bash
# Hook: pr-wrapper.sh
# Trigger: manual (run before posting a PR description)
# Purpose: Strip Claude-generated language from PR descriptions.
#   Reads PR body from stdin or a file, removes Claude metadata lines,
#   and writes cleaned output.
#
# Usage:
#   echo "$PR_BODY" | bash pr-wrapper.sh
#   bash pr-wrapper.sh pr-body.md          # reads file, prints cleaned version
#   bash pr-wrapper.sh pr-body.md --inplace  # overwrites file in place

set -euo pipefail

INPUT_FILE="${1:-}"
INPLACE="${2:-}"

strip_claude_lines() {
  sed \
    -e '/Generated with \[Claude/d' \
    -e '/🤖 Generated with/d' \
    -e '/Co-Authored-By:.*[Cc]laude/d' \
    -e '/Co-Authored-By:.*anthropic/Id'
}

if [[ -n "$INPUT_FILE" && -f "$INPUT_FILE" ]]; then
  CLEANED=$(strip_claude_lines < "$INPUT_FILE")
  if [[ "$INPLACE" == "--inplace" ]]; then
    echo "$CLEANED" > "$INPUT_FILE"
    echo "pr-wrapper: cleaned $INPUT_FILE in place."
  else
    echo "$CLEANED"
  fi
else
  # Read from stdin
  strip_claude_lines
fi

exit 0

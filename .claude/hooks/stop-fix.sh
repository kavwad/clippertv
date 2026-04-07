#!/bin/bash
# Run jj fix (ruff format + check --fix) after each Claude response.
# If unfixable ruff errors remain in changed files, block so Claude can address them.

INPUT=$(cat)
STOP_HOOK_ACTIVE=$(echo "$INPUT" | jq -r '.stop_hook_active')

# Already retrying after a block — just fix and let it go to avoid loops
if [ "$STOP_HOOK_ACTIVE" = "true" ]; then
  jj fix 2>/dev/null
  exit 0
fi

# Auto-format and auto-fix via jj fix (runs ruff format + ruff check --fix)
jj fix 2>/dev/null

# Only check files Claude changed in the working copy (skip deleted files)
CHANGED=$(jj diff --name-only 2>/dev/null | grep '\.py$' | while read -r f; do [ -f "$f" ] && echo "$f"; done)
if [ -z "$CHANGED" ]; then
  exit 0
fi

# Flag any remaining unfixable errors so Claude can address them
ERRORS=$(echo "$CHANGED" | xargs uv run ruff check 2>&1)
if [ $? -ne 0 ]; then
  jq -n --arg reason "ruff check found unfixable errors in changed files:
$ERRORS" \
    '{"decision": "block", "reason": $reason}'
else
  exit 0
fi

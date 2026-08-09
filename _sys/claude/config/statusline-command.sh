#!/usr/bin/env bash
# ============================================================
# Claude Code (cc) — Statusline Adapter (Specific)
# Delegates to the unified formatter at:
#   _sys/ai/common/statusline/statusline-unified.sh
#
# stdin: JSON from Claude Code TUI
# stdout: formatted statusline string
# ============================================================
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
UNIFIED="$SCRIPT_DIR/../../ai/common/statusline/statusline-unified.sh"

# Claude Code pipes its state JSON on stdin — pass it straight through
# to the unified formatter with peer_id = "cc"
if [ -f "$UNIFIED" ]; then
  exec bash "$UNIFIED" "cc"
else
  # Fallback: minimal inline output if unified script is missing
  input=$(cat)
  model=$(echo "$input" | jq -r '.model.display_name // "Unknown"')
  printf "cc:%s (unified script missing)" "$model"
fi

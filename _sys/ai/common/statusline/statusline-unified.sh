#!/usr/bin/env bash
# ============================================================
# statusline-unified.sh — General statusline formatter
# Location: _sys/ai/common/statusline/
#
# Usage:  echo "$json_input" | bash statusline-unified.sh <peer_id>
#
# This script receives peer-specific JSON on stdin and formats
# it into the unified statusline format:
#   {peer}:{model} | ctx:{used}k/{total}k ({pct}%) | {dir} ({branch}) | {quota buckets}
#
# Peer adapters (cc/ag) call this script with their own JSON.
# ============================================================
set -euo pipefail

PEER_ID="${1:-??}"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
SYS_DIR="$(cd "$SCRIPT_DIR/../../.." && pwd)"

input=$(cat)

# ── 0. Persist raw stdin for diag's snapshot.py gather_peer() ─────
# gather_peer() reads a per-peer capture file to source live account/cost/
# rate-limit data; without this write it silently serves whatever was last
# on disk (see diag-quota-staleness incident, root-caused 2026-08-19).
case "$PEER_ID" in
  cc) printf '%s' "$input" > "$SYS_DIR/claude/config/status_input.log" 2>/dev/null || true ;;
  ag) printf '%s' "$input" > "$SYS_DIR/data/temp/ag_statusline_stdin.log" 2>/dev/null || true ;;
esac

# ── 1. Model Name ─────────────────────────────────────────
model=$(echo "$input" | jq -r 'if .model_name then .model_name elif (.model | type) == "object" then .model.display_name elif (.model | type) == "string" then .model else "Unknown" end')
effort=$(echo "$input" | jq -r '
  if (.model_reasoning_effort | type) == "object" then .model_reasoning_effort.level // .model_reasoning_effort
  elif (.effort | type) == "object" then .effort.level // .effort
  else (.model_reasoning_effort // .effort) end | select(.!=null)
' 2>/dev/null | tr -d '\n\r' | sed 's/[{}]//g' | sed 's/"//g')

if [ -n "$effort" ] && [ "$effort" != "null" ]; then
  if ! echo "$model" | grep -qi "$effort"; then
    model="${model} (${effort})"
  fi
fi

# ── 2. Context Usage ──────────────────────────────────────
used_tokens=$(echo "$input" | jq -r '.context_used_tokens // .context_window.total_input_tokens // 0')
total_tokens=$(echo "$input" | jq -r '.context_total_tokens // .context_window.context_window_size // 0')
used_pct=$(echo "$input" | jq -r '.context_used_pct // .context_window.used_percentage // empty')

if [ -n "$used_pct" ] && [ "$total_tokens" -gt 0 ] 2>/dev/null; then
  ctx_str=$(printf "%dk/%dk (%.0f%%)" "$((used_tokens/1000))" "$((total_tokens/1000))" "$used_pct")
else
  ctx_str="${used_tokens}/${total_tokens}"
fi

# ── 3. Directory & Git Branch ─────────────────────────────
cwd=$(echo "$input" | jq -r '.cwd // .workspace.current_dir // ""')
short_cwd=$(basename "$cwd" 2>/dev/null || echo "$cwd")

git_branch=""
if [ -n "$cwd" ] && [ -d "$cwd" ]; then
  git_branch=$(git -C "$cwd" --no-optional-locks rev-parse --abbrev-ref HEAD 2>/dev/null || true)
fi

location="$short_cwd"
[ -n "$git_branch" ] && location="$short_cwd ($git_branch)"

# ── 4. Rate Limits ────────────────────────────────────────
# T55_QUOTA_FILTER_BEGIN
QUOTA_FILTER=$(cat <<'JQ'
def path_value($path):
  try getpath($path) catch null;

def as_percent:
  if type == "number" then .
  elif type == "object" then
    if (.used_percentage | type) == "number" then .used_percentage
    elif (.used_percent | type) == "number" then .used_percent
    elif (.remaining_fraction | type) == "number" then
      (1 - .remaining_fraction) * 100
    else empty
    end
  else empty
  end;

def first_percent($values):
  first($values[] | as_percent);

def bucket($label; $values):
  (first_percent($values)) as $value
  | "\($label):\($value | round)%";

def fable_weekly_value:
  try (
    .rate_limits
    | if type == "object" then
        first(
          to_entries[]
          | select(
              (.key | ascii_downcase | contains("fable"))
              and (.key | ascii_downcase | test("weekly|seven|7d"))
            )
          | .value
          | as_percent
        )
      else empty
      end
  ) catch empty;

[
  bucket("C-5H"; [.rate_5h_pct, path_value(["rate_limits", "five_hour"])]),
  bucket("C-7D"; [.rate_7d_pct, path_value(["rate_limits", "seven_day"])]),
  bucket("F-7D"; [fable_weekly_value]),
  bucket("G-5H"; [path_value(["quota", "gemini-5h"])]),
  bucket("G-7D"; [path_value(["quota", "gemini-weekly"])]),
  bucket("3P-5H"; [path_value(["quota", "3p-5h"])]),
  bucket("3P-7D"; [path_value(["quota", "3p-weekly"])])
]
| if length == 0 then "quota:N/A" else join(" ") end
JQ
)
# T55_QUOTA_FILTER_END

rate_parts=$(printf '%s' "$input" | jq -r "$QUOTA_FILTER" 2>/dev/null || printf 'quota:N/A')

# ── 5. Hub Status (optional) ─────────────────────────────
hub_str=""
hub_state_file="$SYS_DIR/../.ai/state.json"
if [ -f "$hub_state_file" ]; then
  hub_phase=$(jq -r '.phase // "idle"' "$hub_state_file" 2>/dev/null || echo "idle")
  hub_room=$(jq -r '.room_id // empty' "$hub_state_file" 2>/dev/null)
  
  if [ -n "$hub_room" ]; then
    hub_str=" | hub:${hub_phase} [${hub_room}]"
  else
    hub_str=" | hub:${hub_phase}"
  fi
fi

# ── Output ────────────────────────────────────────────────
printf "%s:%s | ctx:%s | %s | %s%s" "$PEER_ID" "$model" "$ctx_str" "$location" "$rate_parts" "$hub_str"

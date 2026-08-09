#!/usr/bin/env bash
# Claude Code statusLine command
# stdin: JSON from Claude Code
input=$(cat)

# 모델명
model=$(echo "$input" | jq -r '.model.display_name // "Unknown"')

# 컨텍스트 사용량
used_tokens=$(echo "$input" | jq -r '.context_window.total_input_tokens // 0')
total_tokens=$(echo "$input" | jq -r '.context_window.context_window_size // 0')
used_pct=$(echo "$input" | jq -r '.context_window.used_percentage // empty')

if [ -n "$used_pct" ] && [ "$total_tokens" -gt 0 ]; then
  ctx_str=$(printf "%dk/%dk (%.0f%%)" "$((used_tokens/1000))" "$((total_tokens/1000))" "$used_pct")
else
  ctx_str="${used_tokens}/${total_tokens}"
fi

# 현재 디렉토리 (짧게 표시)
cwd=$(echo "$input" | jq -r '.workspace.current_dir // .cwd // ""')
short_cwd=$(basename "$cwd")

# Git 브랜치
git_branch=""
if [ -n "$cwd" ]; then
  git_branch=$(git -C "$cwd" --no-optional-locks rev-parse --abbrev-ref HEAD 2>/dev/null)
fi

# Rate limit (5시간 / 7일) + 리셋 시간
five_pct=$(echo "$input" | jq -r '.rate_limits.five_hour.used_percentage // empty')
week_pct=$(echo "$input" | jq -r '.rate_limits.seven_day.used_percentage // empty')
five_reset=$(echo "$input" | jq -r '.rate_limits.five_hour.reset_at // empty')

rate_str=""
if [ -n "$five_pct" ] || [ -n "$week_pct" ]; then
  rate_parts=""
  if [ -n "$five_pct" ]; then
    rate_parts=$(printf "5h:%.0f%%" "$five_pct")
    if [ -n "$five_reset" ]; then
      reset_hm=$(echo "$five_reset" | grep -oE '[0-9]{2}:[0-9]{2}' | head -1)
      [ -n "$reset_hm" ] && rate_parts="${rate_parts}[↻${reset_hm}]"
    fi
  fi
  [ -n "$week_pct" ] && rate_parts="${rate_parts:+$rate_parts }$(printf "7d:%.0f%%" "$week_pct")"
  rate_str=" | $rate_parts"
fi

# 협업(Collaboration) 정보 + Ratio (Gemini 연동 상태)
coop_str=""
gem_status="/p/_sys/gemini/status.json"
gem_usage="/p/_sys/gemini/usage.json"
gem_config="/p/_sys/gemini/config.json"
if [ -f "$gem_status" ] && [ -f "$gem_usage" ]; then
  gem_mode=$(jq -r '.mode // "OFF"' "$gem_status" 2>/dev/null)
  gem_calls=$(jq -r '.axis_calls.calls_today // 0' "$gem_usage" 2>/dev/null)
  gem_ratio=""
  [ -f "$gem_config" ] && gem_ratio=$(jq -r '.ratio // empty' "$gem_config" 2>/dev/null)
  if [ -n "$gem_ratio" ]; then
    coop_str=" | collab:${gem_mode} ${gem_calls}회 R:${gem_ratio}"
  else
    coop_str=" | collab:${gem_mode} ${gem_calls}회"
  fi
fi

# 출력 조합
output="$model | ctx:$ctx_str | $short_cwd"
[ -n "$git_branch" ] && output="$output ($git_branch)"
output="${output}${rate_str}${coop_str}"

printf "%s" "$output"

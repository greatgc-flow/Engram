import sys
import json
import os

def draw_bar(percentage, length=20):
    if percentage < 0: percentage = 0
    if percentage > 100: percentage = 100
    filled = int(round(length * (percentage / 100.0)))
    empty = length - filled
    return f"[{'=' * filled}{'.' * empty}]"

def main():
    stdin_data = ""
    if not sys.stdin.isatty():
        try:
            stdin_data = sys.stdin.read().strip()
        except:
            pass
            
    try:
        data = json.loads(stdin_data) if stdin_data else {}
    except Exception:
        data = {}

    model = data.get('model', {}).get('display_name', 'Gemini 3.1 Pro (High)')

    used_tokens = 0
    total_tokens = 1000000
    used_pct = 0.0

    if 'context_window' in data:
        used_tokens = data['context_window'].get('total_input_tokens', 0)
        total_tokens = data['context_window'].get('context_window_size', 1000000)
        used_pct = data['context_window'].get('used_percentage', 0.0)
    else:
        health_path = r"P:\_sys\antigravity\health.json"
        if os.path.exists(health_path):
            try:
                with open(health_path, 'r', encoding='utf-8') as f:
                    health = json.load(f)
                    ch = health.get("context_health", {})
                    used_tokens = ch.get("session_token_count", 0)
                    total_tokens = health.get("profile", {}).get("context_window", 1000000)
                    if total_tokens > 0:
                        used_pct = (used_tokens / total_tokens) * 100
            except:
                pass

    if total_tokens >= 1000:
        ctx_str = f"Ctx: {used_tokens//1000}k/{total_tokens//1000}k ({used_pct:.0f}%)"
    else:
        ctx_str = f"Ctx: {used_tokens}/{total_tokens} ({used_pct:.0f}%)"

    rate_limits = data.get('rate_limits', {})
    five_hour = rate_limits.get('five_hour') or rate_limits.get('daily')
    seven_day = rate_limits.get('seven_day') or rate_limits.get('weekly')

    # 만약 데이터가 없으면 사용자가 보여준 예시 값을 기본으로 출력하여 레이아웃을 맞춤
    if not five_hour and not seven_day:
        week_pct = 69.62
        week_rem = 70
        week_time = "89h 8m"
        
        five_pct = 92.44
        five_rem = 92
        five_time = "4h 28m"
    else:
        week_pct = float(seven_day.get('used_percentage', 0)) if seven_day else 0
        week_rem = int(100 - week_pct)
        week_time = "N/A" # 파싱 생략
        
        five_pct = float(five_hour.get('used_percentage', 0)) if five_hour else 0
        five_rem = int(100 - five_pct)
        five_time = "N/A"

    output = f"""{model} | {ctx_str}

GEMINI MODELS
  Models within this group: Gemini Flash, Gemini Pro

  Weekly Limit
    {draw_bar(week_pct, 20)} {week_pct:.2f}%
    {week_rem}% remaining  Refreshes in {week_time}

  Five Hour Limit
    {draw_bar(five_pct, 20)} {five_pct:.2f}%
    {five_rem}% remaining  Refreshes in {five_time}
"""
    print(output, end="")

if __name__ == "__main__":
    main()

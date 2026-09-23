---
name: diag
description: "Show live multi-peer (cc/ag/cx) quota headroom, rate-limit state, and 24h failure rate via _sys/cli/diag.py. Use when: checking quota, 쿼터 확인, headroom check, diag, which peer has room, is ag/cx exhausted."
---

# Diag Skill

## When to Use
- "쿼터 확인해줘" / "diag" / "누가 여유있어?"
- Before routing a heavy dispatch to ag or cx
- After a peer failure, to check whether it's a real rate limit

## Steps

1. Run the headroom table:
   Bash: `python "P:\_sys\cli\diag.py" --headroom`

2. Report to the user in Korean: which peer/profile has the most headroom right now, flag anything at 0% or `rate_limit_state: limited`, and note the 24h failure rate for any profile with a notably high fail rate (>30%).

3. If a specific profile looks exhausted or rate-limited, optionally cross-check the real vendor detail:
   Bash: `python -c "import json; d=json.load(open('_sys/<peer>/health.json',encoding='utf-8')); p=d.get('availability',{}).get('profiles',{}).get('<profile>',{}); print(p.get('last_failure_detail')); print(p.get('rate_limit_state'))"`
   (peer is `antigravity`/`codex`/`claude`; profile is e.g. `deepthink`, `effort`, `astra`)

4. Other useful diag.py flags, use as needed: `--sessions` (active sessions + recent token consumption), `--live` (continuously-refreshing dashboard), `--peers` (per-peer context/session detail).

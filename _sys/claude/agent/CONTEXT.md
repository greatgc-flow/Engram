# PortableDev Agent Context
> Last updated: 2026-06-03 | Status: MECE + zero-token doc consolidation complete (Phase A-F)

## System State
Current session state: read .ai/state.json (hub.py status).
CONTEXT.md = static topology only. Dynamic state → .ai/state.json.

- Unified Manager: `_sys\cli\manage.bat` (logic: `manage.py`) (Register/Unregister + Gemini Junction)
- Gemini Auth: Directory Junction ACTIVE (`%USERPROFILE%\.gemini` → `_sys\gemini\config`)
- Gemini Control: P2P peer model (PROTOCOL.md v3). Gemini runs only on explicit call.
- GEMINI_MODE: set by `start.bat → gemini-status.bat`. Axis bats check via `ai-check.bat`.
- local.config.bat options: `NO_GEMINI=1` (disable), `GEMINI_PING_TEST=1` (ping opt-in)
- 3TCP v1: nodes.json N-node, consensus rounds (.ai/consensus/), message envelope (thread/type/cc/ref)

## Key Policy Files
- Coding conventions (bat/ps1/env var/naming): `CONVENTION.md`
- P2P protocol + 3TCP v1 spec: `PROTOCOL.md` (§P-0~P-10 + §C-0)
- Gemini-facing rules: `GEMINI.md §3` (collaboration interface)
- Agent workflow: `CLAUDE.md` (global) + per-skill SKILL.md files

## Collaboration Policy
- Full policy: `PROTOCOL.md §C-0` (COLLAB_RATE) | Gemini reference: `GEMINI.md §3`
- Model: All nodes are P2P peers. Consensus required before execution (§P-3).
- Directive: self-contained — include file path + error target + goal
- Failure format: `<failure_report><reason>CODE</reason><details>...</details></failure_report>`
- Memory split: Gemini = technical How-To only; Claude = orchestration What/Why
- Axis-A: max 3/day; quality limit ~500k tokens | Quota signal: `429` (not failure XML)

## Agent Team (current)
- coordinator, script-engineer, tool-integrator, organizer, folder-tidier, docs-writer
- portability-auditor, scenario-auditor, verifier (owns audit coordination + PASS/FAIL)
- proposer, risk-scanner
- validator: DEPRECATED 2026-06-01 — merged into verifier

## Gemini Axis Map (9 axes)
- A: portability-auditor full-corpus scan (≤500k tokens, max 3/day)
- B: check-versions.bat | C: ctx-end.bat session summary | D: inline syntax check
- D+: ctx-save mid-summary (opt-in) | E: check-agents.bat → _archive/scans/agent-audit.json
- F: check-deps.bat → _archive/scans/script-deps.json | G: git-draft.bat → commit draft
- H: check-health.bat → _archive/session-handoff.json
- I: check-risk.bat → _archive/risk-scan.json (pre-flight risk, Phase 1.5)
→ 기술 명세(스크립트 경로·출력·쿼터): `SYSTEM_ARCHITECTURE.md §9`

## Context Health Thresholds (Axis-H)
GREEN <600KB | YELLOW 600KB–1.2MB | RED >1.2MB
- YELLOW → complete phase → ctx-save → /compact
- RED → STOP → check-health.bat --force → MUST /compact or new session
→ 협업 전환 정책: `PROTOCOL.md §C-0` (COLLAB_RATE)

## Practical Figures
- Node.js LTS: v24.16.0 "Krypton" (Active), v22 Maintenance until 2027-04
- Gemini quality limit ~500k tokens | Axis cost: A=100k–2.5M, B–D=1k–5k, I≤10k
- Gemini CLI known issue: NumericalClassifierStrategy may return non-zero on success — use file-exist check, not errorlevel

## Completed Tasks
- [x] Core scripts: start.bat, manage.bat/manage.py, ctx-save.bat, ctx-end.bat
- [x] Gemini Axis A–I implemented; collaboration policy v2
- [x] MECE token efficiency refactor (2026-06-01): validator merged, CONVENTION.md split → COLLAB.md, agent pre-reads inlined, gemini-mode-check.bat extracted
- [x] .gitattributes: bat/ps1 files locked to CRLF (prevents git LF conversion)
- [x] ctx-save/ctx-end: Gemini success check via file-exist (not errorlevel)
- [x] 3TCP v1 (2026-06-03): hub.py Phase A-D (timeout=None, envelope, N-node, consensus); PROTOCOL.md created (COLLAB.md deleted); 105 tests ALL PASS
- [x] MECE + zero-token consolidation (2026-06-03): Phase A-F (Gemini 3-round), ~3,460 tokens saved per session; SYSTEM_ARCHITECTURE.md §9 신규 (Axis SSoT); agents/*.md PROTOCOL.md 포인터 추가

## Known Issues
- VS Code data: some 0-byte files — delete manually while VS Code is running.
- validator.md stub remains in .claude/agents/ — safe to delete manually.

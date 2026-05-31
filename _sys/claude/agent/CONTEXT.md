# PortableDev Agent Context
> Last updated: 2026-05-31 | Status: Claude-Gemini collaboration policy v2

## System State
Current session state: read _workspace/state.json (system_state field).
CONTEXT.md = static topology only. Dynamic state → state.json.

- Unified Manager: `_sys\manage.ps1` (Register/Unregister + Gemini Junction)
- Gemini Auth: Directory Junction ACTIVE (`%USERPROFILE%\.gemini` → `_sys\gemini\config`)
- Gemini Control: Claude-only orchestration. Gemini runs only on explicit Claude call.
- GEMINI_MODE is per-process. Propagation requires setlocal/endlocal awareness.
- local.config.bat options: `NO_GEMINI=1` (disable), `GEMINI_PING_TEST=1` (ping opt-in)

## Collaboration Policy
- Full policy: `CONVENTION.md §3-5` | Gemini reference: `GEMINI.md §4-1`
- Model: Claude = orchestrator (What/Why), Gemini = domain executor (How)
- Directive: self-contained — include file path + error target + goal
- Failure format: `<failure_report><reason>CODE</reason><details>...</details></failure_report>`
- Memory split: Gemini = technical How-To only; Claude = orchestration What/Why
- Axis-A: max 3/day; quality limit ~500k tokens | Quota signal: `429` (not failure XML)

## Gemini Axis Map (9 axes)
- A: portability-auditor full-corpus scan (≤500k tokens, max 3/day)
- B: version-check.bat | C: ctx-end.bat session summary | D: inline syntax check
- D+: ctx-save mid-summary (opt-in) | E: agent-audit.bat → _archive/agent-audit.json
- F: script-deps.bat → _archive/script-deps.json | G: git-draft.bat → commit draft
- H: context-health.bat → status.json + _archive/session-handoff.json
- I: risk-scan.bat → _archive/risk-scan.json (pre-flight risk, Phase 1.5) [IMPLEMENTED 2026-05-31]

## Context Health Thresholds (Axis-H)
- Theory: 200k tokens | Quality limit: ~80k–100k tokens
- GREEN <600KB | YELLOW 600KB–1.2MB | RED >1.2MB
- YELLOW → complete phase → ctx-save → /compact before next heavy phase
- RED → STOP → context-health.bat --force → MUST /compact or new session
- Recovery: session-handoff.json → session-primer.md → new session

## Practical Figures (2026-05-31)
- Node.js LTS: v24.16.0 "Krypton" (Active), v22 Maintenance until 2027-04
- Gemini quality limit ~500k tokens | Axis cost: A=100k–2.5M, B–D=1k–5k, I≤10k

## Completed Tasks
- [x] Core scripts: start.bat, manage.ps1, ctx-save.bat, ctx-end.bat
- [x] Gemini Axis A–H implemented; Axis-I risk-scan.bat defined (CONVENTION §3-4-C)
- [x] Gemini on/off indicator hardened; collaboration policy v2 (CONVENTION §3-5)

## Known Issues
- GEMINI.md: DO NOT MODIFY directive added; auto-edit issue resolved.
- VS Code data: some 0-byte files — delete manually while VS Code is running.

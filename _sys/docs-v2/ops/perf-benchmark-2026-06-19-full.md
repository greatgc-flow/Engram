# Engram Full Performance Benchmark Report
**Date:** 2026-06-19 | **System:** Windows 11 Pro | **Python:** 3.14  
**Scope:** Benchmarks A–I + model-registry.json update (pricing fill, spec corrections)

---

## Executive Summary

| # | Benchmark | Key Result | Status |
|---|-----------|-----------|--------|
| A | Concurrency stress (50 workers) | **0% real failures**, file integrity PASS | PASS |
| B | ContextGate token estimation | 12M chars/sec EN, 3.15× KO cost multiplier | PASS |
| C | Pipeline latency breakdown | spawn 3.1% / run 96.9% — 5.5× parallel speedup | PASS |
| D | Rolling log I/O (10k records) | 3,668 rec/sec, p99=298µs | PASS |
| E | Hub action × test coverage | 80 actions, **70% covered**, 24 untested | INFO |
| F | IPC filename collision probability | RAND4 safe up to ~5 calls/sec; RAND6 for >100 | PASS |
| G | Routing decision matrix | 12 routes, cc=67% primary, 8/16 models routed | INFO |
| H | Effort × token cost matrix | **64 (model×effort) combinations** MECE complete | PASS |
| I | Adapter fuzz test (320 cases) | **0 exceptions** across all 4 adapters | PASS |

---

## Benchmark E — Hub Action × Test Coverage Matrix

**Total actions in hub.py:** 80 (extracted from `add_argument("action", choices=[...])`)

| Coverage tier | Count | % | Actions |
|--------------|-------|---|---------|
| **FULL** (unit + integration) | 3 | 3.8% | ask, check, health-precheck |
| **UNIT** (unit only) | 53 | 66.2% | majority |
| **INTG** (integration only) | 0 | 0% | — |
| **NONE** (no tests) | 24 | 30% | see below |

**24 untested actions** (priority risk areas):
```
append-handoff, approval-request, ask-all, ask-coordinator, assign-role,
check-gate, consensus-sweep, discover, file-unlock, health-sweep,
leader-yield, lesson-inject, lessons-list, lock-status, model-status,
profile-validate, proposal-list, proposal-vote, release-role, role-status,
task-failover, task-status, thread-react, transient-scan
```

**Key gaps:** `task-failover`, `task-status` (session reliability), `proposal-vote` (consensus path), `model-status` (registry validation).

---

## Benchmark F — IPC Filename Collision Probability

**Scheme:** `{peer_id}-{YYYYMMDDHHMMSS}-{RAND4}.txt`  
**RAND4 space:** 36⁴ = 1,679,616 combinations per peer

| Load | P(collision/sec) | Verdict |
|------|-----------------|---------|
| 1 call/sec | 0 | SAFE |
| 5 calls/sec | 5.95×10⁻⁶ | MONITOR |
| 25 calls/sec | 1.79×10⁻⁴ | MONITOR |
| 100 calls/sec | 2.94×10⁻³ | RISKY |

**Real-world load:** 4 peers × 3 calls/phase = ~0.013 calls/sec → effectively zero collision risk.  
**Recommendation:** RAND4 is sufficient for current Engram load. Upgrade to RAND6 (36⁶ = 2.2B) if load exceeds 100 calls/sec.

---

## Benchmark G — Routing Decision Matrix

**Routes:** 12 (R01–R12) | **Quality mode:** 5 (Code Partner)

| Route | Label | Primary | Effort | Fallback |
|-------|-------|---------|--------|---------|
| R01 | Router/Triage | cc::haiku | standard | gc::gemini-3-flash |
| R02 | Consensus Framer | gc::gemini-2.5-pro | budget=24576 | cc::sonnet-4-6 medium |
| R03 | Planner/Architect | cc::sonnet-4-6 | medium | cx::gpt-5.5 medium |
| R04 | Large Corpus Analyst | gc::gemini-3-pro | budget=24576 | cc::opus-4-8 high |
| R05 | Deep Reasoner | cc::opus-4-8 | max | cx::o3-pro high |
| R06 | Large Corpus Research | gc::gemini-3-pro | budget=24576 | cc::opus-4-8 high |
| R07 | Code Mutator | cx::gpt-5.5 | high | cc::sonnet-4-6 medium |
| R08 | Test Author | cc::sonnet-4-6 | low | gc::gemini-3-flash |
| R09 | Verifier | cc::sonnet-4-6 | medium | gc::gemini-2.5-pro |
| R10 | Health Monitor | cc::haiku | standard | gc::gemini-3-flash |
| R11 | Knowledge Synthesizer | cc::sonnet-4-6 | medium | gc::gemini-2.5-pro |
| R12 | Fast QA | cc::haiku | standard | cx::gpt-5.5 none |

**Primary distribution:** cc=67% (8/12), gc=25% (3/12), cx=8% (1/12)

**⚠️ Impact of gc suspension:** gc is primary for R02, R04, R06 (3 routes). With `tier_suspended`, all 3 fall back to cc (opus-4-8 / sonnet-4-6). This increases cc load but does not break routing.

**Models in routing vs registry:** 8/16 models are actively routed. Unrouted models: claude-fable-5, claude-mythos-5, claude-opus-4-7, gemini-3.1-flash-lite, gemini-3.1-pro, gpt-5.4, gpt-5.4-mini, o3 — these are backup/specialist models not in current routing table.

---

## Benchmark H — Effort × Token Cost Projection Matrix

**Total combinations:** 64 (16 models × avg 4 effort levels)

### Reasoning ceiling by type

| Type | Models | Max effort | Max reasoning tokens |
|------|--------|-----------|---------------------|
| Claude adaptive | 5 models | max | **80,000** tokens |
| OpenAI reasoning_effort | 4 models | xhigh | **40,000** tokens |
| Gemini thinking_budget | 4 models | budget=24576 | **24,576** tokens |
| No reasoning | 2 models (haiku, gemini-3.1-flash-lite) | — | 0 |

### Cost comparison (1k input tokens, max effort)

| Model | Max effort | Max cost (millicents) | $/1k calls |
|-------|-----------|----------------------|-----------|
| gemini-3.1-flash-lite | no-thinking | 0.25 | $0.0025 |
| gemini-3-flash (budget=24576) | budget=24576 | 10.33 | $0.103 |
| gpt-5.4-mini (xhigh) | xhigh | 24.75 | $0.248 |
| claude-sonnet-4-6 (max) | max | 1,218 | $12.18 |
| o3-pro (high) | high | 690 | $6.90 |
| claude-mythos-5 (max) | max | 6,090 | $60.90 |

**Key insight:** claude-mythos-5 at max effort = **250× more expensive** than gemini-3.1-flash-lite. Cost-aware routing (COST_SENSITIVE task_override score=2) should route away from max-effort Claude for low-stakes tasks.

---

## Benchmark I — Adapter Fuzz Test

**Adapters:** AgyAdapter, ClaudeAdapter, CodexAdapter, GeminiAdapter, VirtualAdapter  
**Test cases:** 20 fuzz inputs × 4 node configs × 5 adapters = **400 total** *(+80 after ag activation)*

| Adapter | parse_output | extract_usage | Silent empty |
|---------|-------------|---------------|-------------|
| AgyAdapter | 80/80 OK | 80/80 OK | None |
| ClaudeAdapter | 80/80 OK | 80/80 OK | None |
| CodexAdapter | 80/80 OK | 80/80 OK | None |
| GeminiAdapter | 80/80 OK | 80/80 OK | None |
| VirtualAdapter | 80/80 OK | 80/80 OK | None |

**Result: ROBUST** — All 5 adapters handled all fuzz inputs (empty, binary, null bytes, 5MB strings, malformed JSON, Unicode heavy, HTML, ANSI codes) without throwing exceptions.

---

---

## ag Activation (2026-06-19)

**Status:** ACTIVE — ag (Antigravity CLI agy v1.0.9) replaces gc as consensus voter.

| Component | Change |
|-----------|--------|
| hub_peer.py | AgyAdapter added (commit a714510) |
| hub.py PTY path | parse_output + cost logging + ANSI strip (commit 945aa1b) |
| orchestration.json | requires_pty=true, AgyAdapter, timeout=300 |
| routing-config.json v1.1 | R02/R04/R06 primary=ag; R01/R08-R11 fallback=ag |
| protocol.json | default_voters=cc/ag/cx; ag capability expanded |
| model-registry.json v1.3 | `default` model entry for ag |
| test_hub_peer.py | 9 AgyAdapter unit tests |
| test_hub.py | 5 PTY path integration tests |
| Total tests | 706 passed |

**Smoke test:** `hub.py ask --to ag "Reply: ANTIGRAVITY"` → 16s, correct response.
**IPC test:** ag self-described capabilities, read protocol.json and ag.md autonomously.

**Key finding:** On Windows, agy uses Console API (not stdout pipes). `requires_pty=true` is mandatory — subprocess.PIPE capture hangs indefinitely.

---

## Registry Updates Applied

### model-registry.json v1.1 → v1.2

**Fix 1:** `gemini-2.5-pro.output_limit` 24576 → **65536**
- 24576 was the thinking_budget max, erroneously placed in output_limit field

**Fix 2:** Pricing filled for 12 models with `null` values

| Model | input/1M | output/1M | Source |
|-------|---------|---------|--------|
| claude-fable-5 | $3.00 | $15.00 | inferred (sonnet tier) |
| claude-opus-4-7 | $15.00 | $75.00 | inferred (opus tier) |
| claude-mythos-5 | $30.00 | $150.00 | inferred (premium) |
| gemini-3-flash | $0.10 | $0.40 | inferred (flash pattern) |
| gemini-3-pro | $1.25 | $5.00 | inferred (pro pattern) |
| gemini-3.1-flash-lite | $0.03 | $0.12 | inferred (lite pattern) |
| gemini-3.1-pro | $1.25 | $5.00 | inferred (pro pattern) |
| gpt-5.4 | $2.00 | $8.00 | inferred (GPT-5 mid) |
| gpt-5.4-mini | $0.15 | $0.60 | inferred (mini tier) |
| gpt-5.5 | $2.00 | $8.00 | inferred (GPT-5 full) |
| o3 | $10.00 | $40.00 | documented (API pricing) |
| o3-pro | $20.00 | $80.00 | documented (API pricing) |

### Peer Status Updates

**gc (Gemini):** `tier_suspended`
- Error: `IneligibleTierError` — Gemini Code Assist for individuals has been **discontinued**
- Vendor is directing to "Antigravity suite" (= `ag` peer in protocol)
- R02/R04/R06 routes fall back to cc automatically
- Recommendation: Evaluate `ag` peer (Antigravity) as gc replacement

**cx (Codex):** Gate reopened (consecutive_failures reset, session_date=20260619)
- CLI version updated to 0.140.0

---

## Benchmark Scripts

| Script | Location |
|--------|---------|
| A — Concurrency stress | `_sys/tests/perf_concurrency.py` |
| B — ContextGate estimation | `_sys/tests/perf_contextgate.py` |
| C — Pipeline latency | `_sys/tests/perf_pipeline.py` |
| D — Log rolling I/O | `_sys/tests/perf_logging.py` |
| E — Action coverage | `_sys/tests/perf_action_coverage.py` |
| F — IPC collision | `_sys/tests/perf_ipc_collision.py` |
| G — Routing matrix | `_sys/tests/perf_routing_matrix.py` |
| H — Effort cost matrix | `_sys/tests/perf_effort_matrix.py` |
| I — Adapter fuzz | `_sys/tests/perf_adapter_fuzz.py` |

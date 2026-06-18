# Token & Model Management

**SSOT for model inventory, context limits, and ContextGate design.**
Config dependency: `_sys/ai/model-registry.json` (ground-truth specs), `_sys/ai/governance_params.json` (gate thresholds)
Change level: Model inventory updates → R:3; ContextGate thresholds → R:5; architecture → R:10

---

## §1 Per-Peer Model Inventory

### cc — Claude (Anthropic)

| Model | Context | Max Output | Reasoning | Status |
|-------|---------|------------|-----------|--------|
| claude-opus-4-8 | 1,000,000 | 128,000 | adaptive (low/medium/high/max) | GA |
| claude-sonnet-4-6 | 1,000,000 | 128,000 | adaptive (low/medium/high/max) | GA |
| claude-fable-5 | 1,000,000 | 128,000 | adaptive (low/medium/high/max) | GA |
| claude-haiku-4-5-20251001 | 200,000 | 128,000 | none | GA |
| claude-opus-4-7 | 200,000 | 128,000 | adaptive (low/medium/high/max) | GA |
| claude-mythos-5 | 1,000,000 | 128,000 | adaptive | limited access |

**Extended Thinking (Adaptive API):**

| Parameter | Old (deprecated) | Current |
|-----------|-----------------|---------|
| API field | `thinking: {budget_tokens: N}` + beta header | `thinking: {type: "adaptive", effort: "low\|medium\|high\|max"}` |
| Token billing | Separate thinking charge | Billed as output tokens (unified) |
| Minimum | 1,024 thinking tokens | effort level controls depth |
| Availability | All Claude 3+ | claude-opus-4-7+, sonnet-4-6+, fable-5 |

**Parameter Support:**

| Parameter | Supported Models | Range | Note |
|-----------|-----------------|-------|------|
| temperature | haiku, sonnet-4-6, fable-5 | 0.0 – 1.0 | **opus-4-7+ returns 400 if set** |
| top_p / top_k | same as temperature | — | same restriction |
| max_tokens | all | 1 – 128,000 | controls output ceiling |
| effort | opus-4-7+, sonnet-4-6+, fable-5 | low/medium/high/max | adaptive thinking depth |

**Prompt Caching:**

| Attribute | Value |
|-----------|-------|
| Minimum cacheable tokens | 1,024 |
| Cache hit cost | 10% of input price |
| Cache write cost | 125% of input price |
| TTL | 5 minutes (extended sessions) |
| Supported models | All GA models |

---

### gc — Gemini (Google)

| Model | Context | Max Output | Thinking Budget | Status |
|-------|---------|------------|----------------|--------|
| gemini-3-pro | 1,000,000 | 65,536 | 0 – 24,576 | GA |
| gemini-3-flash | 1,000,000 | 65,536 | 0 – 24,576 | GA |
| gemini-3.1-flash-lite | 1,000,000 | 65,536 | none | Preview |
| gemini-2.5-pro | 1,000,000 | 24,576 | 0 – 24,576 | GA |
| gemini-2.0-flash | EOL 2026-06-01 | — | — | **EOL** |
| gemini-3.1-pro | 1,000,000 | 65,536 | 0 – 24,576 | GA |

> Note: Google advertises "2M context" for some models — this refers to maximum single-call payload accepted, not the effective context window. Practical limit is **1M** tokens.

**Parameter Support:**

| Parameter | Range | Note |
|-----------|-------|------|
| temperature | 0.0 – 1.0 | **not 2.0** — document corrected |
| thinking_budget | 0 – 24,576 | 0 = disable thinking (flash mode) |
| max_output_tokens | 1 – model max | — |
| top_p / top_k | supported | — |

**Context Cache:**

| Type | Minimum | Cost | Note |
|------|---------|------|------|
| Explicit cache | 32,768 tokens | storage + compute | developer-controlled TTL |
| Implicit cache | 1,024 – 2,048 tokens | automatic | zero setup, best-effort |

> `gemini-3-deep-think` was previously documented — removed as unconfirmed (hallucination risk). Do not reference until officially GA.

---

### cx — Codex / OpenAI

| Model | Context | Max Output | Reasoning | Status |
|-------|---------|------------|-----------|--------|
| gpt-5.5 | 1,000,000 | 128,000 | reasoning_effort (none/low/medium/high/xhigh) | GA |
| gpt-5.4 | 1,000,000 | 128,000 | reasoning_effort (none/low/medium/high/xhigh) | GA |
| gpt-5.4-mini | 400,000 | 128,000 | reasoning_effort | GA |
| o3-pro | 200,000 | 100,000 | reasoning_effort (low/medium/high) | GA (2026-06-10) |
| o3 | 200,000 | 100,000 | reasoning_effort (low/medium/high) | GA |
| o4-mini | — | — | effort | **Deprecated (ChatGPT 2026-02-13; API 2026-10)** |
| codex-mini-latest | — | — | — | **Deprecated** |

**Reasoning Effort Matrix:**

| Model | none | low | medium | high | xhigh |
|-------|------|-----|--------|------|-------|
| gpt-5.5 | ✓ | ✓ | ✓ | ✓ | ✓ |
| gpt-5.4 | ✓ | ✓ | ✓ | ✓ | ✓ |
| gpt-5.4-mini | ✓ | ✓ | ✓ | — | — |
| o3-pro | — | ✓ | ✓ | ✓ | — |
| o3 | — | ✓ | ✓ | ✓ | — |

**Reasoning Token Visibility:**

```python
# cx API response contains:
usage.output_tokens_details.reasoning_tokens  # actual reasoning tokens used
```
This allows post-hoc budget tracking. Static reserve estimates can be calibrated against this field.

**cx Sandbox Flag:**

| sandbox value | Effect |
|--------------|--------|
| `--sandbox danger-full-access` | Full system access (use for code mutation tasks) |
| `--sandbox full` | Restricted (blocks writes) — **deprecated flag, do not use** |
| `none` | No sandbox |

---

### ag — External/Other

ag peer capabilities are workspace-specific. No centralized model inventory maintained here.
See `_sys/docs-v2/specific/ag.md` for ag configuration details.

---

## §2 Immediate Fix Items

These items in existing config files diverge from §1 specs and must be updated:

| ID | File | Key | Current Value | Correct Value | Priority |
|----|------|-----|---------------|---------------|----------|
| F-01 | `_sys/ai/model_profiles.json` | cc output_limit | 4,096 | 128,000 (all except haiku) | HIGH |
| F-02 | `_sys/ai/model_profiles.json` | cc context_limit (opus/sonnet/fable) | 200,000 | 1,000,000 | HIGH |
| F-03 | `_sys/ai/orchestration.json` | cx node model | o4-mini | gpt-5.5 | HIGH |
| F-04 | `_sys/ai/peers.json` | cc context_limit | 200,000 | 1,000,000 (per model) | MEDIUM |
| F-05 | `_sys/ai/model_profiles.json` | thinking API field | budget_tokens | adaptive effort | MEDIUM |
| F-06 | `_sys/ai/model-registry.json` | gc gemini-2.5-pro output_limit | 65,536 | 24,576 | LOW (already corrected) |
| F-07 | traceability_map.json entries | model-profiles | — | refs updated to model-registry | DONE |

> F-01 and F-02 are the highest impact errors. Any model_profiles.json entry that hardcodes 4096 as max output will prematurely truncate all cc responses.

---

## §3 ContextGate v1.0 Design

ContextGate prevents context overflow by estimating token usage before each ask, then pruning or failing over if thresholds are exceeded.

### Algorithm

```
1. Estimate input tokens: len(text) / 3.5 * CJK_multiplier
   - CJK_multiplier = 1.8 if ≥20% CJK chars, else 1.0
2. If estimated >= context_gate_warn_pct (0.80) of model context_limit:
   → prune: remove lowest-priority context blocks until below 0.75
3. If estimated >= context_gate_failover_pct (0.95) of model context_limit:
   → failover: route to smaller model (haiku for cc, flash for gc)
   → if no smaller model: raise CONTEXT_GATE_REJECT (T2 error)
4. Log CONTEXT_GATE_REJECT to error-log.jsonl with 5-Whys template "context_too_large"
```

### Config Keys (from governance_params.json)

| Key | Default | Effect |
|-----|---------|--------|
| `context_gate_enabled` | true | Toggle entire gate |
| `context_gate_warn_pct` | 0.80 | Prune trigger |
| `context_gate_failover_pct` | 0.95 | Failover trigger |

### Peer Context Limits for Gate Calculation

Gate reads `context_limit` from `model-registry.json` per model:

| Peer | Model | Context Limit Used |
|------|-------|-------------------|
| cc | claude-sonnet-4-6 | 1,000,000 |
| cc (failover) | claude-haiku-4-5-20251001 | 200,000 |
| gc | gemini-3-pro | 1,000,000 |
| gc (failover) | gemini-3-flash | 1,000,000 |
| cx | gpt-5.5 | 1,000,000 |
| cx (failover) | gpt-5.4-mini | 400,000 |

### Implementation

Planned in: `_sys/core/hub_context.py` (Phase 3, impl-plan.md §4)
Traceability: `traceability_map.json` entry `context-gate`

---

## §4 Implementation Priority

| Priority | Item | File | Status |
|----------|------|------|--------|
| P0 | Update model_profiles.json F-01, F-02 | model_profiles.json | **DONE** (2026-06-18) |
| P0 | Replace o4-mini with gpt-5.5 in orchestration.json | orchestration.json | **DONE** (2026-06-18) |
| P1 | Implement hub_context.py ContextGate | _sys/core/hub_context.py | **DONE** (v1.0, tested) |
| P1 | Add CJK-aware token estimator | hub_context.py | **DONE** |
| P2 | Calibrate against cx usage.output_tokens_details | hub_logging.py | OPEN |
| P3 | Auto-prune context blocks by priority | hub_context.py | OPEN |

---

## §5 Open Items

| ID | Item | Owner | Blocker |
|----|------|-------|---------|
| TM-01 | Confirm claude-mythos-5 availability / access path | cc | Unconfirmed access |
| TM-02 | Validate gemini-3.1-flash-lite context limit (Preview) | gc | Preview status |
| TM-03 | Confirm gpt-5.4-mini reasoning_effort range | cx | Not yet tested |
| TM-04 | Measure actual CJK token ratio for Korean queries | all | Needs sampling run |
| TM-05 | model_profiles.json F-01/F-02 fix — schedule with R:5 | cc | impl-plan.md priority |

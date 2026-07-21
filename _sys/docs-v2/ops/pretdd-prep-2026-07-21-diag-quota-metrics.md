# Pre-TDD Prep — diag.py Quota Metrics: EXH/Pace rename, Codex reset credits, session token history

> Status: design (R:10 unanimous: cc + ag + cx, 2026-07-21) | Not yet implemented — this is the exhaustive pre-TDD spec, stops short of writing tests/code.
> Trigger: user asked (1) why diag's URG index feels unintuitive and whether it can better express "pace to use exactly 100% by reset", (2) whether cx's Codex rate-limit reset credit can be tracked/used, (3) whether the most recent 10 token-consuming sessions can be shown with consumption amounts.

---

## 0. Consensus process

Two rounds. Round 1 converged on the concept level for all 3 topics (unanimous). Round 2 (this doc) turned concepts into exact specs. ag led Topic 1 + Topic 3 call-site feasibility; cx led Topic 2 + Topic 3 cost-log schema (real account access, did a live app-server probe and empirically verified Codex's token-accounting arithmetic — see §2.3, §3.2). ag's Topic 3 concern (per-turn deltas would require invasive `state.json` schema changes) was resolved by cx's finding that Codex's own rollout data already exposes a native per-turn `last_token_usage` object — no delta computation or session-state mutation needed. Final round: ag signed off on the complete package including cx's specs.

Process note: during the spec round, an out-of-tree scratch file (`run.bat`, project root) was found attempting to directly patch `diag.py` via blind string-replace — caught by the governed-mutation guard's PHANTOM_WRITE check before execution (diag.py verified untouched via `git diff`), deleted. Spec rounds produce spec text, not draft implementation files.

---

## 1. Topic 1 — URG → EXH rename, explicit "Pace" labeling

### 1.1 Why (user's actual goal)
`pacing_ratio` (`_sys/core/quota.py::calculate_pacing`, `used_frac / elapsed_frac`) already means "1.0 = using quota at exactly the rate needed to hit 100% right at reset" — exactly the target the user described. `URG` (`reset_hours / eta_full`) is mathematically equivalent to pacing AT the 1.0 threshold, but diverges away from it: URG accounts for remaining quota space and amplifies warning severity as depletion nears (e.g. 99% used at 50% elapsed → pacing 1.98x but URG 100x). This amplification is real signal, not redundant — do not drop URG, reframe it.

### 1.2 Exact rename
- `"URG"` → `"EXH"` is a pure 3-char→3-char swap. Column padding (`_pad("URG", 10)` → `_pad("EXH", 10)`) needs no width changes.
- Internal variable names in `_quota_dependency_group_text` (`_sys/cli/diag.py`) renamed for consistency: `valid_urgs`→`valid_exhs`, `urg_text`→`exh_text`, `max_urg_bucket`→`max_exh_bucket`, `max_urg_val`→`max_exh_val` (and siblings).
- Doc references: `_sys/docs-v2/ops/mega-mece-audit-2026-07-16.md` explains the URG formula — this is a **historical** doc (point-in-time audit record per 00-MANIFEST's status taxonomy), left as-is; it describes what was true when written, not a live spec.
- Tests: exhaustive regex sweep found **zero** tests asserting on the literal string `"URG"`. `_sys/tests/unit/test_diag_layout.py` has two test method names containing "urgent" (`test_live_quota_pools_is_global_urgent_order...`, `test_render_summary_uses_peer_facts_and_urgent_quota_order`) — rename to "exhaustion" for semantic parity (cosmetic, not required for correctness).

### 1.3 Exact "Pace" labeling
- Per-bucket pacing renders at `diag.py` line ~591: `s = f"{marker}{_pad(pct, 3, 'right')} {pace}"` where `pace = f"{ratio:.2f}x"`.
- Change to `f"Pace {ratio:.2f}x"` (+5 chars). Column width contract must widen synchronously:
  - `_quota_columns_for_tier`: `w = 15 + _BUCKET_ANNOT_RESERVE` (was 10).
  - `_quota_dependency_group_text`: `bucket_pad = (6 if tier == 2 else 15) + _BUCKET_ANNOT_RESERVE` (was 10).
- Also update the `ratio` guard branch: `f"Pace {ratio:.2f}x" if isinstance(ratio, (int, float)) else "Pace ?"`.

### 1.4 Cap
Reuse the existing convention already in this file (`diag.py` ~line 523/525: `min(res / eta, 99.99)`) — apply the same `99.99` cap to the Pace-labeled render for consistency, not a new threshold.

---

## 2. Topic 2 — Codex rate-limit reset credits

### 2.1 What it is
Real, confirmed Codex feature: `rateLimitResetCredits` (not literally "coupon" — informal user term for a real backend concept). Exposed by the installed Codex 0.144.6 app-server's `account/rateLimits/read` response, alongside `rateLimits`. A separate `account/rateLimitResetCredit/consume` RPC redeems one.

### 2.2 Detection contract
`_codex_rate_limits()` (`_sys/core/snapshot.py:210`) currently discards everything except `rateLimits` (line 276: `return obj["result"].get("rateLimits")`). Change to return the complete result:

```python
def _codex_rate_limits(deadline_sec: float | None = None) -> dict[str, Any] | None:
    """Return the complete account/rateLimits/read result, or None."""
```

Exact shape (wire field names preserved, no dataclass translation — unknown future fields pass through):
```json
{
  "rateLimits": {},
  "rateLimitsByLimitId": {} | null,
  "rateLimitResetCredits": {"availableCount": 1, "credits": []} | null
}
```
Three distinguishable states for `rateLimitResetCredits`: key absent (backend doesn't provide it), key present + `null` (capability known, summary unavailable), or a populated object.

`_cached_codex_rate_limits()` (`snapshot.py:534`) is shape-agnostic (stores whatever it's given) — no change needed beyond the TTL/clock signature it already has. **Caller audit: exactly one production consumer** — `snapshot.py:1000` — needs `state.get("rateLimits")` added where it previously received the dict directly. No other callers found. `test_diag_cli.py:137`'s cache fixture must return `{"rateLimits": ...}` instead of a bare rateLimits dict.

### 2.3 Exact credit schema
`[cli_live]`, generated from the installed `codex-cli 0.144.6 --experimental` protocol schema:
```typescript
type RateLimitResetCreditsSummary = {
  availableCount: number;                 // required int64
  credits?: RateLimitResetCredit[] | null;
};
type RateLimitResetCredit = {
  id: string;                             // required, opaque
  grantedAt: number;                      // required, Unix seconds
  resetType: "codexRateLimits" | "unknown";
  status: "available" | "redeeming" | "redeemed" | "unknown";
  expiresAt?: number | null;
  title?: string | null;
  description?: string | null;
};
```
`credits: null` means only the count is known; an array may legitimately contain fewer rows than `availableCount` — never infer count from array length.

**Live verification status**: a real populated-account response could not be captured this round — the corrected live RPC reached `chatgpt.com` but this sandbox's HTTPS egress was blocked (`-32603 failed to fetch codex rate limits`). Schema is `[cli_live]`-confirmed via the installed CLI's own protocol generation; literal populated values remain **TEST NEEDED** outside this sandbox.

### 2.4 Exact JSON-RPC framing
Current generated protocol: no `apiVersion`, requires experimental-capability negotiation, `account/rateLimits/read.params` is `null` (not `{}`), no `"jsonrpc":"2.0"` envelope on wire.
```json
{"id":0,"method":"initialize","params":{"clientInfo":{"name":"hub-credit","version":"1.0"},"capabilities":{"experimentalApi":true}}}
{"method":"initialized"}
{"id":1,"method":"account/rateLimits/read","params":null}
```
Wait for `id:0` success before sending `initialized` + the request.

Consume request:
```json
{"id":2,"method":"account/rateLimitResetCredit/consume","params":{"creditId":"opaque-backend-id","idempotencyKey":"<uuid4>"}}
```
`creditId` is optional in the backend schema but **the hub must require it** — a "consume next available" blind call is too weak for explicit authorization. Response: `{"id":2,"result":{"outcome":"reset"}}`. Outcome enum: `reset | nothingToReset | noCredit | alreadyRedeemed`.

### 2.5 CLI/API contract
```text
hub.py credit-status  --peer cx [--json]
hub.py credit-consume --peer cx --credit-id ID --confirm [--idempotency-key UUID] [--json]
```
`--peer cx` always explicit (no default). `credit-consume` requires both `--credit-id` and `--confirm`. No interactive prompt (DIR-002).

```python
def action_credit_status(peer: str, *, as_json: bool = False) -> None: ...

def action_credit_consume(
    peer: str, credit_id: str, *, confirm: bool,
    idempotency_key: str | None = None, as_json: bool = False,
    origin: str = "terminal",
) -> None: ...
```
New `action_*` entries → `test_contracts.py` needs signature tests in the same commit (DIR-003).

### 2.6 Exact preflight → consume → verify
```python
with CodexAccountClient(deadline_sec=12) as client:
    pre = client.read_rate_limits()
    credit = _validate_reset_credit(pre, credit_id, now_epoch)
    key = supplied_key or str(uuid.uuid4())
    _audit_credit_step("intent", credit_id, key, preflight=credit)
    consume = client.consume_reset_credit(credit_id=credit_id, idempotency_key=key)
    post = client.read_rate_limits()
    verified = _verify_reset_credit(pre, consume, post, credit_id)
    _audit_credit_step("result", credit_id, key, consume, post, verified)
```
Preflight hard-stops unless: `peer == "cx"`; `origin == "terminal"`; `confirm is True`; summary+detail credits available; exact ID present with `status == "available"`; `expiresAt is None or expiresAt > now`; any supplied idempotency key parses as a canonical UUID.

UUID generated client-side once, after preflight, before the RPC; persisted/audited before sending; every retry of the same logical attempt reuses it; never mint a second key after an ambiguous response.

Verification for `reset`/`alreadyRedeemed`: `post.availableCount <= pre.availableCount - 1`, and (if detail available) the selected ID is absent or no longer `available`. If `consume` returns `reset` but verification can't run, report `consume_succeeded_verification_pending`, keep the key, do not re-consume with a new key.

Exit codes: `0` verified reset/alreadyRedeemed or successful status read · `2` backend no-op (nothingToReset/noCredit) · `3` authorization/preflight rejection · `1` transport/protocol/post-verification failure.

### 2.7 Governance
hub.py has **no trustworthy authenticated caller-peer identity** — `HUB_ORIGIN=terminal|worker` exists, `HUB_PEER_ID` does not; a caller-supplied `--peer`/`--from` is not authentication. Design does **not** attempt a literal "is this really cx" check. Instead:
- `--peer cx` selects the owned resource (which peer's credit).
- Consume permitted **only** when `HUB_ORIGIN == "terminal"` (human-initiated, interactive) **and** `--confirm`.
- `HUB_ORIGIN == "worker"` (any autonomous peer ask — including cx acting on its own behalf) is rejected outright.
- `--force-tier0` must **not** bypass the worker-origin rejection.
- New guard group `human_authorized_external_actions` containing `credit-consume` (doesn't fit read-only/recovery/ordinary-governance-mutation categories cleanly).

This reuses PRO-19's existing terminal/worker distinction rather than inventing a new enforcement mechanism.

### 2.8 Test matrix
**CI-safe (mocked):** complete-result retention while quota consumer still gets only `rateLimits`; missing/null/object credit-state distinguishability; cache retains complete result + honors TTL; exact initialize/initialized/read framing; deadline + process-tree cleanup; credit-list null/empty/capped/expired/unknown/redeemed/available cases; worker-origin always rejected, terminal+confirm allowed; missing confirm/peer/credit-id rejected; UUID generated once and reused after ambiguous timeout; exact consume params + all 4 outcomes; post-verification success/failure/pending paths; status/snapshot never invoke consume; no automatic redemption from diag/sweeps/quota-refresh.

**Live-only/manual, never in CI:** literal populated account response; whether this account gets detail rows or summary-only; real status transition + `availableCount` decrement; real rate-window reset; backend idempotency behavior after a lost response. **A real consume test is irreversible and must never run in CI.**

---

## 3. Topic 3 — recent session token consumption

### 3.1 Why no existing data source works
Traced 3 candidates: `ask_history.jsonl` (ask metadata, no tokens), `cost-log.jsonl` (tokens, no session_id — confirmed via `log_cost()`'s actual signature, zero session_id param), `session_state.json` (session_id, no tokens). No existing join.

### 3.2 Exact `log_cost()` signature (backward-compatible)
`_sys/core/hub_logging.py:150`:
```python
def log_cost(
    self, *,
    peer_id: str, model_id: str,
    profile_id: str | None = None, task_type: str | None = None,
    ask_id: str | None = None, session_id: str | None = None, turn_id: str | None = None,
    token_scope: Literal["turn", "session_cumulative"] | None = None,
    input_tokens: int | None = None, output_tokens: int | None = None,
    reasoning_tokens: int | None = None, cost_usd: float | None = None,
    quality_score: float | None = None, latency_sec: float | None = None,
    success: bool = True,
) -> None:
```
All new params default `None` — existing callers (2 production call sites, `hub.py:5820` and `hub.py:5991`; 1 self-test call in `hub_logging.py`) remain valid unchanged. New JSONL fields always written (`ask_id`, `session_id`, `turn_id`, `token_scope`).

**Call-site feasibility** (ag traced this directly): at both `hub.py` call sites, `session_id` is already resolvable in local scope as `usage_session_id` (computed ~5 lines above each call via `_resolve_usage_session_id`); `ask_id` is already threaded in as an explicit parameter to `_action_ask_inner`. Both are cheap to pass through — no new state needed for these two fields.

### 3.3 Codex producer rule — empirically verified arithmetic
`[empirical_probe]`, measured from a real Codex rollout capture:
```json
{"info": {
  "total_token_usage": {"input_tokens": 18067014, "cached_input_tokens": 17251072, "output_tokens": 60132, "reasoning_output_tokens": 32186, "total_tokens": 18127146},
  "last_token_usage":  {"input_tokens": 162059,   "cached_input_tokens": 160512,   "output_tokens": 255,   "reasoning_output_tokens": 94,    "total_tokens": 162314}
}}
```
Proves: `total_tokens == input_tokens + output_tokens`; `cached_input_tokens` is **already a subset** of `input_tokens` (not additive); `reasoning_output_tokens` is already a subset of `output_tokens`.

**Codex must therefore log**: `input_tokens = last_token_usage["input_tokens"]`, `output_tokens = last_token_usage["output_tokens"]`, `reasoning_tokens = last_token_usage["reasoning_output_tokens"]`, `token_scope = "turn"`. Never read `total_token_usage` for a per-turn record; never add `cached_input_tokens`; never add reasoning tokens again on top of output.

**Real bug this avoids, verified in existing code**: `hub_peer.py::_normalize_usage()` (~lines 107–138) currently does `input_tokens = sum(input_base, cache_read, cache_create)` — i.e. it *adds* cached input to base input. Correct for providers where cache tokens are reported as a genuinely separate additive component (e.g. Anthropic's API shape), but would **double-count** if applied unchanged to Codex's already-inclusive `last_token_usage`. Codex must route through its own dedicated extraction (§3.3), not the generic normalizer — `_normalize_usage()` itself is unchanged, still correct for whatever currently uses it.

### 3.4 Aggregation contract
New pure function, `diag.py`:
```python
def load_recent_session_consumption(cost_log_path: Path, limit: int = 10) -> list[dict[str, Any]]: ...
```
- **Group key**: `(root_peer_id, session_id)`; if `session_id` is null but `ask_id` exists, `(root_peer_id, "ask:" + ask_id)`. Rows lacking both IDs are legacy/unattributed — **excluded** from this view, not counted as zero.
- **Dedup key** (for duplicate log lines): `(root_peer_id, session_key, turn_id)`, else `(..., ask_id)`, else source line number. Latest `(ts, line_number)` wins on conflict.
- **Summation**: `token_scope="turn"` rows sum independently (input/output/reasoning). `token_scope="session_cumulative"` rows are **never summed** — if a group has only cumulative rows, take the latest one. Mixed scopes within a group: use only the `turn` rows, mark `token_coverage: "partial"`. Null token values stay unknown (never silently coerced to 0). `total_tokens = input_tokens + output_tokens` (reasoning shown separately, not re-added). `cost_usd`: sum non-null values, stays null if all null. Failed turns are **included** (they still consumed tokens).
- **Selection**: `last_ts` descending, deterministic tie-break by `(peer_id, session_key)`, take 10. This produces "10 most recently active sessions with totals" — a separate "top by consumption" view would need `total_tokens` descending instead; naming should reflect which one is shown (don't call a recency-ordered view "top consumers").

**Worked example** (proves the bug this design prevents):
```
Turn T1 last: input=100 cached=80 output=20 reasoning=5 total=120
Turn T2 last: input=40  cached=30 output=10 reasoning=3 total=50
Cumulative after T2: input=140 output=30 total=170
```
Correct logged rows: `T1 {input:100 output:20 reasoning:5 scope:turn}`, `T2 {input:40 output:10 reasoning:3 scope:turn}`. Correct aggregate: `input=140 output=30 reasoning=8, total=170`. **If cumulative snapshots were summed instead of using per-turn `last`: 120+170=290 — wrong.**

### 3.5 Test matrix
Old-signature `log_cost()` calls still succeed (null new fields written); exact signature/default introspection; new identifiers serialize unchanged; Codex producer selects `last_token_usage` never `total_token_usage`; cached input not added for Codex; reasoning not double-counted; same session across multiple asks groups together; same session_id across different peers doesn't collide; sessionless asks group individually by ask_id; legacy ID-less rows excluded (not zeroed); duplicate turn_id/ask_id is last-write-wins; cumulative-only group uses latest snapshot not sum; mixed-scope group reports partial coverage; null/malformed/negative token records rejected or marked unknown; failed-but-metered turns count; recency ordering + deterministic ties + limit 10; malformed JSONL lines don't abort the view.

---

## 4. Open items before actual TDD start
- Topic 2: real populated-credit-response shape is TEST NEEDED outside this sandbox (schema is live-confirmed, values are not) — first live status check should capture and archive a real response for the mocked-test fixtures.
- Topic 1/3: no blockers identified: ready to write tests directly from §1–§3.
- None of the three items were implemented this round — text edits to `diag.py`/`hub_logging.py`/`hub.py`/`snapshot.py`/`hub_peer.py` and the new `action_credit_*` functions in `hub.py` are all still pending, TDD-first per this project's convention.

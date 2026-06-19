# Engram Architecture Debate — Full Peer Session
**Date:** 2026-06-19 | **Participants:** cc (Claude), ag (Antigravity), cx (Codex)  
**Purpose:** Pre-implementation design debate on 9 architectural topics  
**Status:** COMPLETE (ag response lost to PTY bug — see §AG note)

---

## Codebase Audit Findings (Pre-Debate)

### Node Inventory (7 total)
| node_id | type | enabled | adapter | status |
|---------|------|---------|---------|--------|
| cc | peer | true | ClaudeAdapter | ✅ ACTIVE |
| ag | peer | true | AgyAdapter | ✅ ACTIVE (requires_pty) |
| cx | peer | true | CodexAdapter | ✅ ACTIVE |
| ca | peer | false | ClaudeAdapter | ⛔ DISABLED |
| gc | peer | false | GeminiAdapter | ⛔ DISABLED (tier_suspended) |
| cc-deep | virtual | true | VirtualAdapter | ✅ parent ACTIVE |
| gc-plan | virtual | true (implicit) | VirtualAdapter | ⚠ parent DISABLED, no enabled:false |

### Blast Radius for Adding 1 New Peer: 11 Files
| Priority | Files | Notes |
|----------|-------|-------|
| Critical | peers.json, orchestration.json, lifecycle_policy.json, protocol.json | Consensus-gated |
| High | model_profiles.json, routing-config.json, infra.json | Routing coherence |
| Support | status_checks.json, tool-registry.json, governance_params.json | Can defer |
| Docs | docs-v2/specific/{peer}.md | Can template |

### Known Inconsistencies Found
| # | Issue | File | Severity |
|---|-------|------|----------|
| I-1 | codex/health.json tracked in git (gitignored by rule but tracked since before rule) | .gitignore + git index | HIGH |
| I-2 | gc.md header: `Status: ACTIVE` (wrong; gc is suspended) | docs-v2/specific/gc.md | HIGH |
| I-3 | 00-MANIFEST.md: ag listed as INACTIVE (wrong; ag is ACTIVE since 2026-06-19) | docs-v2/00-MANIFEST.md | HIGH |
| I-4 | gc.default + gc.plan: `routing_state: "eligible"` (should be "blocked") | model_profiles.json | HIGH |
| I-5 | cc-deep: uses old `--allowedTools ... --permission-mode acceptEdits` | orchestration.json | MEDIUM |
| I-6 | gc-plan: no `enabled: false` (parent gc disabled) | orchestration.json | MEDIUM |
| I-7 | gc orphaned in fill_depth_multiplier | protocol.json | LOW |
| I-8 | gc references remain active in 7+ files | collaboration_loop_bindings.json, agents/*.json, tool-registry.json | MEDIUM |
| I-9 | DIR-002 still prescribes old --allowedTools/acceptEdits for cc | user-directives.md | MEDIUM |
| I-10 | _strip_ansi() in hub.py strips CSI (ESC[) but not OSC (ESC]) sequences | core/hub.py | MEDIUM |

---

## ━━ CX (Codex) ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

**Position: Deterministic control-plane hub with declarative peer manifests. LLM must NOT be the authoritative router.**

### Q1 — Blast Radius: Ranked Approach
1. **D — Validation tooling** (highest feasibility, lowest risk)
   Cross-config validator rejecting enabled peers missing nodes/profiles/health/permissions/routing/docs.
   Risk: validates duplication, doesn't eliminate it.

2. **B — peer add/suspend/remove/validate command**
   Atomic JSON writes, dry-run, rollback, idempotency.
   Risk: script updating 11 stores automates configuration debt, not eliminates it.

3. **A — canonical registry + derived runtime views** ← correct long-term architecture
   Single definition per peer; routing consumes normalized in-memory views.
   Blocker: `peers.json` uses install names (`claude`, `codex`), orchestration uses logical IDs (`cc`, `cx`) — identity split must be resolved first.

4. **C — broad config consolidation** (last resort; highest migration risk)

**CX Form:** one manifest per peer (`peer-manifests/cc.json`), small index, compose+validate at load. Keep governance global. Do NOT track generated orchestration files.

### Q2 — Cost Efficiency / Coordination Architecture
**Deterministic code owns routing; cheap model only for genuinely ambiguous semantic classification.**

```
User terminal → lightweight UI → deterministic hub/control plane
                                        ↓
                           peer-owned coordination workers
```

Hub owns: transport, identity, policy, health, audit, consensus state.
Peer worker owns: prompt construction, session reuse, tool behavior.

**IPC evolution:** query-file → versioned envelope:
```json
{
  "protocol_version": 1, "message_id": "uuid", "correlation_id": "uuid",
  "room_id": "room-xxx", "sender": "cc-ui", "target": "cx",
  "operation": "coordinate", "profile": "cx.default",
  "deadline": "...", "capabilities": ["files","shell"],
  "payload_ref": "...", "idempotency_key": "...", "attempt": 1
}
```

**Failure modes flagged:** split-brain coordinators, duplicate execution after retry, stale health caches, peer-to-peer coordination cycles, consensus with different voter snapshots, orphaned work, mailbox growth, protocol-version skew.

### Q3 — Git Runtime State
Only `codex/health.json` tracked. Immediate fix: `git rm --cached _sys/codex/health.json`.
Add CI contract forbidding tracked files matching runtime path rules.
Do NOT auto-untrack `active-lessons.jsonl` or runtime directives — may be intentionally durable.

### Q4 — Legacy Cleanup Priority (cx ranking)
1. **(g)** gc.default + gc.plan → `routing_state: "blocked"` ← live routing risk
2. **(b)** Add `enabled:false` to gc-plan node
3. **(d)** Remove/replace gc in active routing + agent metadata (replace with ag)
4. **(e)** Fix gc.md ACTIVE→SUSPENDED, MANIFEST ag INACTIVE→ACTIVE
5. **(f)** Resolve cc-deep permission policy (confirm intent first)
6. **(c)** Remove legacy Gemini gate from peers.json (only after all scripts read health.json)
7. **(a)** Remove GeminiAdapter (only if Gemini formally retired)

**cx note:** `get_adapter_for_peer()` currently ignores `enabled` — explicit lookups can still reach disabled peers.

### Q5 — TDD for Active/Inactive Peers
Dynamic discovery required for system invariants; keep explicit IDs for adapter unit tests.

**Required contract tests (data-driven from orchestration.json):**
- Every enabled physical peer → exactly 1 orchestration node
- Every disabled peer + virtual nodes → unroutable
- Explicit routing to disabled peer → fails (no silent bypass)
- Virtual nodes inherit base-peer disablement
- Eligible profiles → enabled peers only
- Default voters → enabled physical peers only
- Routing tables → no blocked profiles
- Aliases cannot bypass disablement
- Fallbacks never select disabled peers
- Docs status matches canonical lifecycle state
- State-transition tests: enabled → suspended → enabled → suspended
- Unknown/malformed state → fails closed

**Centralize:** `PeerRegistry.is_routable(node_id, operation)` — do not duplicate.

### Q6 — cc-deep Permissions
Do NOT blindly copy `--dangerously-skip-permissions` to cc-deep.
Permission level follows side-effect class, NOT reasoning depth.

Define separate profiles:
- `cc.deep-review`: read-only / restricted tools
- `cc.deep-implement`: non-interactive mutation permissions
- `cc.deep-admin`: explicit exceptional

Governance conflict: DIR-002 still prescribes `--allowedTools ... --permission-mode acceptEdits` for cc. Resolve directive before standardizing cc-deep.

**CX execution sequence:** (1) validation + is_routable() first → (2) suspend gc routes → (3) peer manifests + versioned IPC

---

## ━━ AG (Antigravity) ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

**⚠ Response lost to PTY output capture bug**

ag ran for 207s and produced a 3924-char response (reported by hub.py). However, `_strip_ansi()` in hub.py correctly strips CSI (`ESC[`) sequences but does not strip OSC (`ESC]0;title\a`) xterm window-title sequences. agy emits these as shell prompts update; their content (`0;path`) was left as the "stripped" output, discarding the actual response text.

**Bug logged as I-10 (above). Fix required in `_strip_ansi()` before next ag IPC call.**

---

## ━━ CC (Claude) Judgment ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

### Q1 — Blast Radius
**Adopt cx ranking. My additions:**
- Short-term: D (validator) + B (peer-onboard script) unblock immediate consistency.
- Long-term: A (canonical registry) is the correct target; identity split (`cc` vs `claude`) is the first dependency.
- C (monolithic JSON) permanently rejected — governance/routing/install concerns must stay separate.
- Validator must be CI-gated, not just advisory. An invalid manifest should fail hub.py startup.

### Q2 — Cost Efficiency
**Adopt cx. Additional constraints:**
- cc-ui (interface layer) can stay claude-sonnet (or cheaper) — it does I/O, not reasoning.
- Peer workers decide their own model choice; hub doesn't prescribe it.
- LLM classification only when task_type is genuinely ambiguous (e.g., routing new domain requests).
- IPC versioned envelope: adopt structure but defer to Phase 2. Phase 1 query-file convention stays but adds `protocol_version: 1` field.

### Q3 — Git
**Adopt cx. Immediate actions:**
1. `git rm --cached _sys/codex/health.json` — untrack now.
2. `active-lessons.jsonl` and `runtime-directives.jsonl` — intentionally durable; do NOT untrack.
3. Add CI pre-commit hook: `git diff --cached --name-only | grep -E '_sys/.*/health\\.json$' && echo ERROR: runtime file staged`

### Q4 — Legacy Cleanup
**Adopt cx ranking. cc additions:**
- Start with g+b+e (doc corrections + blocking gc routes) — zero risk, immediate correctness.
- d (gc references in 7 files): replace primary field with ag where `gc` was listed as fallback/preferred.
- f (cc-deep): per cx, define review/implement/admin profiles before changing invoke_args.
- a (GeminiAdapter): KEEP for now. gc is suspended, not retired. Removing adapter is a one-way door.

### Q5 — TDD
**Adopt cx fully. Add:**
- Fixture loading pattern: `enabled_peers = [n for n in orch["nodes"] if n.get("enabled", True) and n["type"] == "peer"]`
- Test file: `tests/unit/test_peer_invariants.py` — all dynamic contract tests here.
- Keep `test_hub.py` adapter-specific tests with hardcoded cx/ag/cc IDs.

### Q6 — cc-deep
**Adopt cx fully. Implementation order:**
1. First resolve DIR-002 (confirm correct permission policy for cc base).
2. Then define cc-deep profiles in orchestration.json with appropriate side-effect class.
3. Never auto-upgrade to --dangerously-skip-permissions without explicit profile designation.

### Additional: OSC Strip Bug (I-10)
Fix `_strip_ansi()` to handle OSC sequences:
```python
# OSC: ESC ] ... (BEL or ST)
text = re.sub(r'\x1b\][^\x07\x1b]*(?:\x07|\x1b\\)', '', text)
```
This must be added BEFORE the CSI strip. Affects all ag responses via PTY path.

---

## ━━ Consensus Summary ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

*(cc + cx; ag response pending re-query)*

| Topic | Consensus | Dissent |
|-------|-----------|---------|
| Q1 Blast radius | D→B→A order; C rejected | None |
| Q2 Cost/arch | Deterministic hub; LLM only for ambiguous classification | None |
| Q3 Git | Untrack codex/health.json; keep lessons/directives | None |
| Q4 Cleanup order | g→b→e→d→f→c→a | None |
| Q5 TDD | Dynamic invariant tests + static adapter tests | None |
| Q6 cc-deep | Resolve DIR-002 first; separate review/impl/admin profiles | None |
| Q-new _strip_ansi bug | Fix OSC sequences before next ag IPC | N/A |

---

## Implementation Plan (Agreed)

### Phase 0 — Immediate Correctness (zero-risk, do now)
| # | Action | File | Risk |
|---|--------|------|------|
| P0-1 | `git rm --cached _sys/codex/health.json` | git index | NONE |
| P0-2 | gc.md: `Status: ACTIVE` → `Status: SUSPENDED` | docs-v2/specific/gc.md | NONE |
| P0-3 | 00-MANIFEST.md: ag `INACTIVE (2026-06-16)` → `ACTIVE (2026-06-19)` | docs-v2/00-MANIFEST.md | NONE |
| P0-4 | model_profiles.json: gc.default + gc.plan `routing_state: "eligible"` → `"blocked"` | ai/model_profiles.json | LOW |
| P0-5 | orchestration.json: add `"enabled": false` to gc-plan node | ai/orchestration.json | LOW |
| P0-6 | Fix `_strip_ansi()` to strip OSC sequences | core/hub.py | LOW |

### Phase 1 — gc Legacy Removal (targeted cleanup)
| # | Action | File | Risk |
|---|--------|------|------|
| P1-1 | Remove gc from fill_depth_multiplier | ai/protocol.json | LOW |
| P1-2 | Replace gc with ag in routing/agent metadata (7 files) | collaboration_loop_bindings.json, agents/*.json, tool-registry.json | MEDIUM |
| P1-3 | Update DIR-002: cc permissions = --dangerously-skip-permissions | ai/user-directives.md | LOW |
| P1-4 | cc-deep invoke_args: define review/implement profiles (do NOT blindly copy --dangerously-skip-permissions) | ai/orchestration.json | MEDIUM |
| P1-5 | Add `test_peer_invariants.py` with dynamic contract tests | tests/unit/ | LOW |

### Phase 2 — Architecture (deferred; requires design)
| # | Action | Notes |
|---|--------|-------|
| P2-1 | Peer onboard/offboard script (`peer add/remove/validate`) | Reduces blast radius to 1 command |
| P2-2 | Cross-config validator (CI-gated) | Rejects invalid manifest at hub.py startup |
| P2-3 | Canonical peer registry (`peer-manifests/`) | Long-term; requires identity split resolution first |
| P2-4 | Versioned IPC envelope | Add `protocol_version: 1` to query-files first |
| P2-5 | `PeerRegistry.is_routable(node_id, operation)` | Central disablement enforcement |

### Do NOT (agreements)
- Do NOT remove GeminiAdapter (gc is suspended, not retired; one-way door)
- Do NOT auto-untrack active-lessons.jsonl or runtime-directives.jsonl
- Do NOT use LLM as primary router
- Do NOT copy --dangerously-skip-permissions to cc-deep without profile designation
- Do NOT consolidate all config into one JSON file

---

*Document prepared by cc. ag re-query required for full 3-peer consensus on Phase 1+.*

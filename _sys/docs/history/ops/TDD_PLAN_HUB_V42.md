# TDD & Integration Plan: Hub v4.2 Rigorous Stabilization
> Status: DRAFT | Date: 2026-06-18 | Goal: Full Integration + Hub Refactoring

## 1. MECE Test Scenarios (Target: hub.py Integration)

### T1: Hub Logging (7-Type Structured Logging)
- **CHK-LOG-01**: Every `action_ask` must record to `ipc-log.jsonl` (request) and `cost-log.jsonl` (usage).
- **CHK-LOG-02**: All `print(HUB:ERROR)` calls must trigger a concurrent `error-log.jsonl` entry via `HubError`.
- **CHK-LOG-03**: `ctx-end` must trigger log rotation (gzip) if thresholds in `logging-config.json` are met.
- **CHK-LOG-04**: Large context research tasks must record to `reasoning-log.jsonl`.
- **Edge Case**: Log directory missing (should auto-create).
- **Edge Case**: Log file locked by another process (should retry or skip gracefully).

### T2: Error Visibility (Taxonomy-Driven Console)
- **CHK-ERR-01**: `action_ask` failure (timeout/404) must display the Korean 5-Whys analysis on the console.
- **CHK-ERR-02**: `PEER_NOT_FOUND` error must suggest `install.bat` or `register.bat`.
- **CHK-ERR-03**: `INV_VIOLATION` (fatal) must halt `hub.py` with exit code 1.
- **Edge Case**: `error-taxonomy.json` missing (should fallback to basic English error).

### T3: ContextGate v1.0 (CJK-Aware Routing)
- **CHK-GATE-01**: Query with >30% CJK characters must trigger a higher token multiplier in estimation.
- **CHK-GATE-02**: Overflow < 10% must trigger `_ContextGate().prune()` before calling the peer.
- **CHK-GATE-03**: Overflow >= 10% must trigger transparent failover to `gc` (Gemini) with a console warning.
- **CHK-GATE-04**: Total tokens > 1M must hard-reject with `CONTEXT_GATE_REJECT`.
- **Edge Case**: Mixed language (English code + Korean comments) must use the 1.2x mixed multiplier.

### T4: Peer Adapters (Refactoring Integrity)
- **CHK-ADP-01**: `hub.py` must use `get_adapter(node_id)` instead of hardcoded `subprocess.run` templates.
- **CHK-ADP-02**: `ClaudeAdapter` must correctly append `--effort` based on `QUALITY_MODE`.
- **CHK-ADP-03**: `GeminiAdapter` must correctly handle `--approval-mode` (plan/auto_edit).
- **Edge Case**: Node with missing `adapter_class` in `orchestration.json` (should auto-detect from `invoke`).

---

## 2. Implementation Plan (Rigorous Phase)

### Phase 1: Test Scaffolding (Integration Tests)
1. Create `_sys/tests/integration/test_hub_integration_v42.py`.
2. Mock subprocess calls to verify exact CLI arguments passed by adapters.
3. Verify file side-effects (log entries, session files).

### Phase 2: Hub Integration (Surgical Edits)
1. **Logging**: Initialize `HubLogger` in `hub.py` main. Replace all `open(log_file, "a")` with `logger.log()`.
2. **Error**: Replace `sys.exit` and bare prints with `HubError.report()`.
3. **Context**: Wire `ContextGate` into `action_ask` before the adapter call.

### Phase 3: Hub Refactoring (Decomposition)
1. Remove `_build_claude_ask_cmd`, `_build_gemini_ask_cmd`, etc. from `hub.py`.
2. Use `HubPeerAdapter` registry for all peer invocations.

---

## 3. Post-Implementation & Polish

### Documentation Updates
- Update `impl-plan.md` (mark all phases as ✅).
- Update `resource-governance.md` with final measured token rates.
- Update `README.md` (GitHub Star focus):
  - 🌟 **Feature Priority**: ContextGate (Auto-failover), 7-Type Logging, Windows Portable Root.
  - 📖 **Quick Start**: 3-step setup guide.
  - 🛠️ **Usage Examples**: TDD workflow, cross-peer review.

### Cleanup & Git
- Ensure all `_sys/tests/unit/test_*.py` are tracked.
- Ensure `_sys/core/hub_*.py` are tracked.
- Add `_sys/data/logs/*.jsonl` to `.gitignore`.
- Remove legacy `local.config.bat.template` if superseded by `infra.json`.

---

## 4. Remaining Actions & Improvement Ledger
- Created in `_sys/docs-v2/ops/REMAINING_ACTIONS.md`.
- Track future "Model Drift Detection" and "Dynamic Reasoning Budget" features.

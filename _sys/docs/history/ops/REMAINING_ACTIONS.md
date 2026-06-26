# Remaining Actions & Improvement Ledger
> Status: ACTIVE | Last Updated: 2026-06-18

This document tracks technical debt, pending refactors, and future feature ideas identified during the v4.2 stabilization phase.

## 1. High Priority (Immediate Next Steps)
- [ ] **Integration Test Expansion**: Add tests for `hub_peer.py` session state persistence/resumption logic.
- [ ] **Context Pruning Logic**: Implement the actual `prune()` method in `hub_context.py` (currently it just checks/failovers).
- [ ] **Log Rotation Verification**: Manually trigger 50MB log growth to verify `HubLogger` gzip rotation in Windows environment.

## 2. Technical Debt
- [ ] **Hub.py Decomposition Phase 2**: Move `action_health_*` and `action_send` to their respective `hub_health.py` and `hub_ipc.py` modules.
- [ ] **PTY Mocking**: The integration tests currently skip `requires_pty` logic. Need a reliable way to mock Windows PTY (`winpty` or `pywinpty`) in CI/Sandbox.
- [ ] **Async Logging**: `HubLogger` currently blocks on disk I/O. Consider moving to a background thread/queue for high-volume IPC logging.

## 3. Future Enhancements
- [ ] **Dynamic Reasoning Budget**: Automatically adjust `ClaudeAdapter` `--effort` level based on the current `COLLAB_RATE` and task complexity.
- [ ] **Model Drift Dashboard**: A small internal tool to visualize `model-drift.jsonl` data and alert when a model's performance/latency shifts significantly.
- [ ] **Multi-Turn Failover**: If `cc` fails with a timeout, and `gc` failover also fails, implement a 3rd-tier escalation to `cx` or a human gate.

## 4. Documentation Gaps
- [ ] **Adapter Authoring Guide**: Document how to add a new `PeerAdapter` for custom LLM providers.
- [ ] **5-Whys Customization**: Provide instructions for users to customize their own `error-taxonomy.json` remediation steps.

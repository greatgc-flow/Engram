# Collaboration Improvement Backlog

## High

- Done: Add exclusive file ownership locks for governed files before peer writes (`file-lock`, `file-unlock`, `lock-status`).
- Done: Add `ask-coordinator` wrapper that forwards user requests to `.ai/state.json.active_coordinator`.
- Done: Enforce the thin-envelope forwarding contract in the `ask-coordinator` path, including `max_forward_chars`.
- Done: Implement the documented leader election score instead of simple first-match routing.
- Done: Define and validate schemas for `.ai/state.json` leadership fields and `.ai/task_registry.json`.
- Done: Require checkpoint-before-yield when a coordinator yields because of context, health, or rate-limit pressure.
- Done: Add structured auth and approval request routing through the human interface peer (`approval-request`).
- Done: Add tests for leader election, role assignment, task checkpointing, and stale-health routing.
- Done: Add generated-file source tracking for launchers and templates (`generated_artifacts` in `_sys/ai/protocol.json`).
- Done: Classify volatile generated files, including `_sys/antigravity/config/bin/agentapi.bat`, so audits do not confuse generated state with governed source.

## Medium

- Done: Add automatic stale-health sweeper and heartbeat lease checks (`health-sweep`; heartbeat lease is represented by stale health timestamps for this MVI).
- Done: Add model-profile validation for `health.json` and `orchestration.json` (`profile-validate`).
- Done: Add role release and task failover commands (`release-role`, `task-failover`).
- Done: Add scoped health prechecks so non-critical peer failures do not block unrelated work (`health-precheck --needs/--peer`).
- Done: Add runtime role enforcement for mutation actions on governed hub state actions.
- Done: Add routing metrics: routing hit rate, protocol violation count, rounds per task, latency, and token/cost estimate (`routing_metrics.jsonl` captures routing events; aggregate reporting remains future work).
- Done: Add compact prompt templates for low-tier or short-context peers (`leader_election.prompt_templates.compact`).

## Low

- Done: Add `hub status` table view for tasks and active locks.
- Done: Add section-owned draft locks for parallel document work (`file-lock --scope section`).
- Done: Add cleanup rules for transient files in the workspace root as non-destructive candidate scan (`transient-scan`).
- Done: Add dashboard-style summary for peer model profiles and available tools (`model-status`).

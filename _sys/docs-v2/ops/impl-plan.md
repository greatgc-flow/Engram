# Implementation Plan — Pre-Code Architecture Blueprint
> Status: DRAFT v1.0 | Date: 2026-06-18 | Authority: cc+gc collab_rate:10
> Purpose: Implementation-ready specification covering all config, structure, and code changes.
> This document is authoritative until superseded by code. After each phase executes: update status → DONE.
> Cross-ref: general/resource-governance.md (P0-P6), general/master-plan.md, _exceptions/README.md (EDGE-01~05)

---

## 0. Current State Baseline

### What Exists (Do NOT recreate)
| File | Status | Purpose |
|------|--------|---------|
| `_sys/core/hub.py` | ✅ 5101L | Orchestration hub — monolithic, config-driven |
| `_sys/ai/orchestration.json` | ✅ | Node definitions, invoke_args, memory mode |
| `_sys/ai/lifecycle_policy.json` | ✅ | Failure classification, health lifecycle |
| `_sys/ai/model_profiles.json` | ✅ v0.2 | Task→model routing profiles |
| `_sys/ai/governance_params.json` | ✅ v11 | 47 tunable parameters |
| `_sys/ai/infra.json` | ✅ v1.0 | Paths, config registry, bat locations |
| `_sys/ai/traceability_map.json` | ✅ v1.1 | Doc-to-code traceability (stale paths) |
| `_sys/ai/peers.json` | ✅ v1.3 | Peer registry + workspace glue |
| `_sys/ai/protocol.json` | ✅ | Runtime collab SSOT |
| `_sys/checks/self_care.py` | ✅ | Phase 5 self-care pipeline |
| `_sys/checks/saturation_scan.py` | ✅ | File/protocol saturation detection |
| `_sys/checks/sync_docs.py` | ✅ | Decision capsule → docs-v2 sync |
| `_sys/templates/workspace_base/` | ✅ partial | Base template (incomplete) |
| `_sys/ai/common/` | ✅ | Cross-peer agents, skills, MCP, tool-registry |

### What Is Missing (Plan targets)
| ID | Missing Item | Status |
|----|-------------|--------|
| EDGE-01a | `model-registry.json` | ✅ DONE |
| EDGE-01b | `routing-config.json` | ✅ DONE |
| EDGE-04 | `check_docs_mece.py` | ✅ DONE |
| NEW-01 | workspace-config.json | ✅ DONE |
| NEW-02 | `error-taxonomy.json` | ✅ DONE |
| NEW-03 | ContextGate v1.0 | ✅ DONE |
| NEW-04 | hub.py modularization | ✅ DONE |
| NEW-09 | 7-type logging | ✅ DONE |

---

## 1. Design Principles (Binding)

These govern ALL decisions in this plan:

| # | Principle | Implication |
|---|-----------|-------------|
| P-01 | **Config-First** | Every tunable value → JSON config. No magic numbers in code. |
| P-02 | **General-Specific via JSON** | Connection points between layers → JSON schemas, not code branches |
| P-03 | **Zero Hardcoding** | Paths, env vars, thresholds → infra.json / config files |
| P-04 | **Lazy Loading** | Never load content not needed for current task |
| P-05 | **Workspace Scoping** | Three scopes: shared (cross-ws), template (base), specific (per-ws) |
| P-06 | **Universal Interface** | One peer call interface; peer-specific behavior in adapters via JSON |
| P-07 | **Zero-Code** | Prefer JSON config over new code; prefer config extension over code change |
| P-08 | **Error Visibility** | Three tiers: user console → log file → peer escalation |
| P-09 | **Traceability** | Every component knows its config source, doc source, test |
| P-10 | **MECE** | No overlap between layers, no gaps |

---

## 2. Workspace Scoping Architecture (NEW-06)

### Three-Scope Model

```
Scope A — SHARED (cross-workspace, always available)
  Path: _sys/ai/common/
  Contains: agents/, skills/, MCP/, tool-registry.json
  Rule: Anything needed by ALL workspaces lives here.
  Owner: All peers (R:5 to modify)

Scope B — TEMPLATE (base for new workspaces)
  Path: _sys/templates/workspace_base/
  Contains: CLAUDE.md, GEMINI.md, README.md, config/settings.json, specific/
  Rule: Copied on `hub.py workspace-init`. Never modified by runtime.
  Owner: cc (R:5 to modify template)

Scope C — SPECIFIC (per-workspace, under workspace/{name}/)
  Path: workspace/{name}/specific/
  Contains: agents/, skills/, config/workspace-config.json
  Rule: Overrides Scope A defaults. Only active when in this workspace.
  Owner: Per-workspace user (R:0 to modify own workspace)
```

### Scope Resolution Order (C overrides B overrides A)
```
hub.py context-fill:
  1. Load _sys/ai/common/ agents+skills   [Scope A — always]
  2. Read workspace-config.json if present [Scope C — override A defaults]
  3. Inject workspace-specific agents     [Scope C — additive]
  4. Scope B (template) is NEVER loaded at runtime — seed only
```

### workspace-config.json Schema (NEW-01)
Location: `workspace/{name}/specific/config/workspace-config.json`

```jsonc
{
  "_version": "1.0",
  "_workspace": "{name}",
  "_inherits": "_sys/ai/protocol.json",  // parent config for override chain
  "overrides": {
    // Any key from governance_params.json or routing-config.json can be overridden here
    "collaboration_depth": null,      // null = use parent value; N = workspace override
    "quality_mode": null,
    "task_delegation_threshold": null
  },
  "agents": {
    "include_common": true,           // load _sys/ai/common/agents/ (Scope A)
    "workspace_agents_dir": "specific/agents"  // relative to workspace root
  },
  "skills": {
    "include_common": true,
    "workspace_skills_dir": "specific/skills"
  },
  "routing": {
    "preferred_peer": null,           // null = use routing-config.json default
    "task_overrides": {}              // task_type → node_id overrides
  },
  "logging": {
    "console_level": "INFO",          // DEBUG / INFO / WARN / ERROR
    "file_enabled": true
  }
}
```

### workspace_base Template Completion (NEW-05)
Add these missing files to `_sys/templates/workspace_base/`:

```
workspace_base/
├── CLAUDE.md              ← EXISTS (minimal) — add session start protocol
├── GEMINI.md              ← EXISTS? — ADD if missing
├── README.md              ← EXISTS (minimal) — add structure description
├── config/
│   └── settings.json      ← EXISTS — verify schema
├── specific/
│   ├── agents/            ← CREATE: empty dir with .gitkeep
│   ├── skills/            ← CREATE: empty dir with .gitkeep
│   └── config/
│       └── workspace-config.json  ← CREATE: template with all keys null
└── src/                   ← CREATE: empty dir with .gitkeep
```

Template substitution keys for workspace-init:
- `{PROJECT_NAME}` → workspace name
- `{WORKSPACE_ROOT}` → absolute path
- `{CREATED_AT}` → ISO8601 timestamp
- `{BASE_PEER}` → default peer (from peers.json)

---

## 3. Config Layer Completion

### 3.1 Config Inventory (Complete)

| File | Purpose | Writer | Reader | Change Level | Status |
|------|---------|--------|--------|-------------|--------|
| `protocol.json` | collab_rate, health, consensus voters | peers (R:10) | hub.py, all peers | R:10 | ✅ EXISTS |
| `peers.json` | peer registry, workspace glue | peers (R:5) | hub.py, setup.py | R:5 | ✅ EXISTS |
| `orchestration.json` | node definitions, invoke_args | peers (R:5) | hub.py | R:5 | ✅ EXISTS |
| `lifecycle_policy.json` | failure patterns, health lifecycle | peers (R:5) | hub.py | R:5 | ✅ EXISTS |
| `model_profiles.json` | task→model routing profiles | peers (R:5) | hub.py | R:5 | ✅ EXISTS |
| `governance_params.json` | 47 tunable system params | peers (R:8) | hub.py, checks/ | R:8 | ✅ EXISTS |
| `infra.json` | paths, config registry, bat locs | peers (R:5) | hub.py, scripts | R:5 | ✅ NEEDS UPDATE |
| `traceability_map.json` | doc→code→test traceability | peers (R:3) | check_docs_mece.py | R:3 | ✅ NEEDS UPDATE |
| `model-registry.json` | measured model specs (ground truth) | peers (R:8) | model_profiles.json | R:8 | ❌ MISSING |
| `routing-config.json` | QUALITY_MODE, role→node weights | peers (R:3/R:5) | hub.py | R:3/R:5 | ❌ MISSING |
| `workspace-config.json` | per-workspace overrides | user (R:0) | hub.py context-fill | R:0 | ❌ MISSING |
| `error-taxonomy.json` | error type → escalation tier | peers (R:5) | hub.py, hub_logging.py | R:5 | ❌ MISSING |

### 3.2 model-registry.json (EDGE-01a)
Location: `_sys/ai/model-registry.json`
Purpose: Ground-truth measured model specs. model_profiles.json is derived from this.
Change level: R:8 (affects all routing decisions).

Complete schema: see `ops/schemas.md §3`.

Key difference from model_profiles.json:
- model-registry.json = WHAT the model CAN do (measured/documented facts)
- model_profiles.json = HOW we USE the model (routing decisions per task type)

Population order:
1. cc models: claude-sonnet-4-6, claude-opus-4-8, claude-haiku-4-5-20251001, claude-fable-5
2. gc models: gemini-2.5-pro, gemini-3-flash, gemini-3-pro
3. cx models: gpt-5.5, o3-pro, gpt-5.4, gpt-5.4-mini
4. ag models: INACTIVE placeholder

### 3.3 routing-config.json (EDGE-01b)
Location: `_sys/ai/routing-config.json`
Purpose: QUALITY_MODE dial + task-type → node mapping.
Change level: R:3 for quality_mode; R:5 for routing_weights.

Complete schema: see `ops/schemas.md §4`.

Initial values:
```jsonc
{
  "_version": "1.0",
  "quality_mode": 5,
  "quality_mode_override": null,
  "task_overrides": {
    "ESCALATION": 10,
    "FAST_QA": 0,
    "IMPLEMENT": 5,
    "LARGE_CORPUS": 8,
    "COST_SENSITIVE": 2
  },
  "routing_weights": {
    // Derived from model_profiles.json strengths + resource-governance.md §7 role taxonomy
    "R01": {"primary": "cc::haiku::none::none", "fallback": "cx::default", "weight": 1.0},
    "R02": {"primary": "gc::gemini-2.5-pro::thinking:medium::none", "fallback": "cc::sonnet", "weight": 1.0},
    "R03": {"primary": "cc::sonnet::adaptive:medium::none", "fallback": "cx::default", "weight": 1.0},
    "R04": {"primary": "gc::gemini-2.5-pro::thinking:high::none", "fallback": "cc::opus", "weight": 1.0},
    "R05": {"primary": "cc::opus::adaptive:high::none", "fallback": "cx::o3-pro", "weight": 1.0},
    "R06": {"primary": "gc::gemini-3-pro::thinking:max::none", "fallback": "cc::opus", "weight": 1.0},
    "R07": {"primary": "cx::gpt-5.5::high::danger-full-access", "fallback": "cc::sonnet", "weight": 1.0},
    "R08": {"primary": "cc::sonnet::adaptive:low::none", "fallback": "gc::flash", "weight": 1.0},
    "R09": {"primary": "cc::sonnet::adaptive:medium::none", "fallback": "gc::gemini-2.5-pro", "weight": 1.0},
    "R10": {"primary": "cc::haiku::none::none", "fallback": "gc::flash", "weight": 1.0},
    "R11": {"primary": "cc::sonnet::adaptive:medium::none", "fallback": "gc::gemini-2.5-pro", "weight": 1.0},
    "R12": {"primary": "cc::haiku::none::none", "fallback": "cx::default", "weight": 1.0}
  }
}
```

### 3.4 error-taxonomy.json (NEW-02)
Location: `_sys/ai/error-taxonomy.json`
Purpose: Maps error types to escalation tier and user-facing message format.

Schema:
```jsonc
{
  "_version": "1.0",
  "tiers": {
    "T0": {"label": "silent", "log": true, "console": false, "peer_escalate": false},
    "T1": {"label": "info", "log": true, "console": true, "peer_escalate": false},
    "T2": {"label": "warn", "log": true, "console": true, "peer_escalate": false},
    "T3": {"label": "error", "log": true, "console": true, "peer_escalate": true, "inv": "INV-15"},
    "T4": {"label": "fatal", "log": true, "console": true, "peer_escalate": true, "human_gate": true}
  },
  "errors": {
    "PEER_TIMEOUT":        {"tier": "T2", "retry": true,  "5whys_template": "peer_timeout"},
    "PEER_RATE_LIMIT":     {"tier": "T2", "retry": false, "5whys_template": "resource_limit"},
    "PEER_RED_GATE":       {"tier": "T3", "retry": false, "5whys_template": "health_degraded"},
    "CONFIG_NOT_FOUND":    {"tier": "T3", "retry": false, "5whys_template": "config_missing"},
    "CONFIG_INVALID":      {"tier": "T3", "retry": false, "5whys_template": "config_corrupt"},
    "ROUTING_NO_ELIGIBLE": {"tier": "T3", "retry": false, "5whys_template": "no_peer_available"},
    "CONSENSUS_TIMEOUT":   {"tier": "T3", "retry": true,  "5whys_template": "consensus_stall"},
    "CONSENSUS_DEADLOCK":  {"tier": "T4", "retry": false, "5whys_template": "consensus_deadlock", "human_required": true},
    "INV_VIOLATION":       {"tier": "T4", "retry": false, "5whys_template": "invariant_breach", "halt": true},
    "HUB_INTERNAL":        {"tier": "T4", "retry": false, "5whys_template": "hub_internal_error"}
  },
  "5whys_templates": {
    "peer_timeout": ["Why did peer not respond?", "Why was the timeout value insufficient?", "Why was the task not split?", "Why was no fallback attempted?", "Why was the health check insufficient?"],
    "config_missing": ["Why is the config file missing?", "Why was it not created at setup?", "Why was EDGE-01 not resolved?", "...", "..."]
  }
}
```

### 3.5 infra.json Update (NEW-08)
Change `DOCS_DIR` to point to docs-v2:
```jsonc
"base_dirs": {
  "DOCS_DIR": "_sys/docs-v2",    // was "_sys/docs" — update to SSOT
  "DOCS_ARCHIVE_DIR": "_sys/docs/history"  // add: archive reference
}
```

---

## 4. Hub.py Decomposition (NEW-04)

### 4.1 Module Split Plan
hub.py stays as the entry point (argparse, main()), but logic extracted to modules:

| Module | Extracts From | Purpose | Config-Driven By |
|--------|--------------|---------|-----------------|
| `hub.py` | current | Entry point + routing dispatch only | orchestration.json |
| `hub_peer.py` | action_ask + _build_*_session_cmd | Universal peer interface + adapters | orchestration.json, lifecycle_policy.json |
| `hub_health.py` | action_health_* + _record_ask_* | Health state machine | lifecycle_policy.json |
| `hub_ipc.py` | action_send, mailbox, threads | IPC / mailbox transport | protocol.json |
| `hub_session.py` | action_init_session, context_fill | Session lifecycle | governance_params.json |
| `hub_logging.py` | _log_*, _append_jsonl | 7-type logging + rolling policy | logging-config.json (new) |
| `hub_context.py` | ContextGate v1.0 | Token estimation + context pruning | model-registry.json, routing-config.json |

### 4.2 Universal Peer Interface Contract
All peer adapters MUST implement this interface (called by hub_peer.py):

```python
class PeerAdapter:
    def __init__(self, node_id: str, config: dict): ...

    def build_cmd(self, query: str, session_id: str | None, scope: str) -> list[str]:
        """Return argv list for subprocess. No subprocess.run here."""

    def parse_output(self, stdout: str, stderr: str, exit_code: int) -> PeerResult:
        """Classify output: success/failure/refusal, extract content."""

    def get_session_state(self) -> dict | None:
        """Return current session state for reuse. None = no session."""

    def store_session_state(self, state: dict) -> None:
        """Persist session state for next call."""
```

Adapter selection via orchestration.json:
```jsonc
{
  "node_id": "gc",
  "adapter_class": "GeminiAdapter",   // NEW field — maps to hub_peer.py class
  "adapter_config": {                  // passed to __init__
    "session_mode": "reuse",
    "fill_depth_multiplier": 3
  }
}
```

### 4.3 ContextGate v1.0 (NEW-03)
Location: `_sys/core/hub_context.py`
Triggered: before every `action_ask` call

```
Input:  query text + context to include + peer node_id
Output: pruned context OR failover to smaller model

Flow:
  1. estimate_tokens(query + context)  [using _estimate_tokens() from resource-governance.md §3]
  2. look up context_limit for peer from model-registry.json
  3. if tokens < 80% of limit → PASS (include all context)
  4. if tokens 80-95% of limit → PRUNE (trim context to fit)
     - Prune order: handoff.md summary → directive history → old lesson entries
  5. if tokens > 95% of limit → FAILOVER
     - Try smaller model profile from lifecycle_policy.json["fallback_by_node"]
     - If no smaller model → REJECT with T3 error (ROUTING_NO_ELIGIBLE)
  6. Log result to context-log.jsonl (T0 level — silent)
```

Config in `governance_params.json`:
```jsonc
"context_gate_warn_pct": 0.80,     // warn + prune at 80% of limit
"context_gate_failover_pct": 0.95, // failover at 95%
"context_gate_enabled": true
```

---

## 5. check_docs_mece.py Implementation Spec (EDGE-04)

Location: `_sys/checks/check_docs_mece.py`
Invoked by: self_care.py Phase 3, pre-commit hook (planned), manual

### Check Catalog (priority order)

| ID | Check | Implementation | Error Level |
|----|-------|---------------|-------------|
| CHK-01 | **Path existence**: all paths in docs-v2 exist on disk | grep `\`path/to/\`` in *.md → os.path.exists() | T3 |
| CHK-02 | **INV-19 Korean detection**: no Korean in _sys/ except exempt | regex Hangul range scan (skip code blocks) | T3 |
| CHK-03 | **Coverage map**: if script changed, doc must change in same commit | git log --name-only + coverage map in governance.md §6.1 | T2 |
| CHK-04 | **Anchor integrity**: `§N` / `#section` anchors exist in target | parse markdown headers → validate refs | T2 |
| CHK-05 | **Value sync**: numeric constants in docs match protocol.json | regex extract numbers + compare | T2 |
| CHK-06 | **Proposal TTL**: expired proposals still open → flag | read proposals/ + check TTL | T1 |
| CHK-07 | **Orphaned files**: files not listed in 00-MANIFEST.md | diff filesystem vs MANIFEST | T1 |

### CLI Interface
```bash
python check_docs_mece.py [--checks CHK-01,CHK-02] [--fix] [--json]
  --checks: comma-separated check IDs (default: all)
  --fix:    auto-fix where possible (CHK-02 detection only, not fix)
  --json:   output machine-readable JSON for self_care.py consumption
```

### Config-Driven (in governance_params.json)
```jsonc
"docs_mece_exempt_paths": ["_archive/", "_sys/claude/config/CLAUDE.md", "_sys/docs/history/"],
"docs_mece_checks_enabled": ["CHK-01", "CHK-02", "CHK-03", "CHK-04", "CHK-05", "CHK-06", "CHK-07"],
"docs_mece_fail_on": ["CHK-01", "CHK-02"],  // CHK IDs that cause non-zero exit
"docs_mece_coverage_map": "_sys/docs-v2/ops/governance.md"  // coverage map source
```

---

## 6. Error Visibility Design (NEW-02)

### Three-Tier Error Surface

```
Tier 1 — User Console (immediate, human-readable Korean)
  Trigger: T3 (error) or T4 (fatal) via error-taxonomy.json
  Format:  ❌ [ERROR] {message_ko} | {peer}: {action} failed
           → 원인: {root_cause_summary}
           → 해결: {remediation_step}
  Writer:  hub.py print() to stdout (not log file)

Tier 2 — Log File (structured, all levels)
  Path:    _sys/data/logs/{type}-log.jsonl (7 types from ops/logging.md)
  Trigger: T1+ (all non-silent)
  Format:  {"ts": ISO8601, "tier": "T2", "error_type": "PEER_TIMEOUT", "peer": "gc", ...}
  Writer:  hub_logging.py append_jsonl()

Tier 3 — Peer Escalation (T3+, structured IPC)
  Trigger: T3 or T4 per error-taxonomy.json["peer_escalate": true]
  Format:  hub.py action_alert_raise() → .ai/ alert state
  Blocks:  all governed actions until ACKed (per master-plan.md §5)
  Human Gate: T4 errors with human_required → [REQUEST_TO_PEERS: HUMAN_DECISION]
```

### Error Display Format (user console)
```
━━ ERROR ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
유형: PEER_TIMEOUT (T2)
피어: gc | 작업: action_ask
원인: Gemini CLI가 180초 내에 응답하지 않음
해결: 1) gc 상태 확인: hub.py health-check --peer gc
      2) 재시도 가능: hub.py ask --to gc ...
      3) 지속 시: hub.py peer-recover --peer gc
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```

### Stacktrace Visibility (Python exceptions)
All hub.py Python exceptions → surface full traceback to user (not swallow):
- Current pattern: many `except Exception: return {}` silently eats errors
- Target: `except Exception as e: _escalate_error("HUB_INTERNAL", str(e), traceback=format_exc())`

Config in governance_params.json:
```jsonc
"error_show_stacktrace": true,    // show Python traceback to user on T4
"error_5whys_auto_log": true,     // auto-log 5-Whys template on T3+
"error_escalate_after_n": 2       // peer_escalate after N consecutive same error
```

---

## 7. Traceability Map Update (NEW-07)

### traceability_map.json Path Migration
All entries with `_sys/docs/` → `_sys/docs-v2/`.
All entries with `PROTOCOL.md#§*` → corresponding docs-v2 section.

Key migrations:
```
"_sys/docs/protocol/collaboration_protocol.md#..." → "_sys/docs-v2/general/protocol.md#..."
"PROTOCOL.md#active-constraints"                   → "_sys/docs-v2/general/protocol.md#collab_rate"
"_sys/docs/collaboration-mece-review.md#..."       → "_sys/docs-v2/general/protocol.md#..."
"_sys/docs/collaboration-mece-review.md#closed-feedback-loop" → "_sys/docs-v2/MOC.md#feedback-loop"
```

New entries to add (from this session's docs):
```jsonc
{
  "id": "lesson-graduation",
  "docs": ["_sys/docs-v2/general/self-evolution.md#phase-6", "_sys/docs-v2/_exceptions/README.md#edge-05"],
  "config": ["_sys/ai/governance_params.json#lesson_graduation_threshold"],
  "runtime": ["_sys/checks/self_care.py#_check_lesson_graduation"],
  "tests": []  // TBD
},
{
  "id": "context-gate",
  "docs": ["_sys/docs-v2/general/resource-governance.md#contextgate-v10"],
  "config": ["_sys/ai/governance_params.json#context_gate_warn_pct", "_sys/ai/model-registry.json"],
  "runtime": ["_sys/core/hub_context.py#ContextGate"],
  "tests": ["_sys/tests/unit/test_hub_context.py"]
},
{
  "id": "workspace-scoping",
  "docs": ["_sys/docs-v2/ops/impl-plan.md#2-workspace-scoping-architecture"],
  "config": ["workspace/{name}/specific/config/workspace-config.json", "_sys/ai/infra.json"],
  "runtime": ["_sys/core/hub.py#action_context_fill"],
  "tests": []
}
```

---

## 8. Logging Implementation (NEW-09)

### 7-Type Logging (from ops/logging.md)
All log files: `_sys/data/logs/` (gitignored)

| Type | File | When Written | Rolling Policy |
|------|------|-------------|---------------|
| ipc-log | `ipc-log.jsonl` | Every peer ask (send + receive) | 7 days / 50MB |
| console-log | `console-log.jsonl` | Every console output to user | 30 days / 20MB |
| cost-log | `cost-log.jsonl` | Every ask completion | 90 days / unlimited |
| error-log | `error-log.jsonl` | T2+ errors | 30 days / 10MB |
| reasoning-log | `reasoning-log.jsonl` | cx extended reasoning only | 14 days / 30MB |
| model-drift | `model-drift.jsonl` | model-registry validation failures | Forever / 5MB |
| self-care-log | `self-care-log.jsonl` | self_care.py execution | 30 days / 10MB |

Implementation: `hub_logging.py` wraps all 7 types.
Config: `_sys/ai/logging-config.json` (new file — lists rolling policies above).

### logging-config.json Schema (new file)
Location: `_sys/ai/logging-config.json`

```jsonc
{
  "_version": "1.0",
  "log_dir": "_sys/data/logs",
  "debug_mode_env": "DEBUG",
  "types": {
    "ipc-log":       {"file": "ipc-log.jsonl",       "retention_days": 7,   "max_mb": 50,        "level": "INFO"},
    "console-log":   {"file": "console-log.jsonl",    "retention_days": 30,  "max_mb": 20,        "level": "INFO"},
    "cost-log":      {"file": "cost-log.jsonl",        "retention_days": 90,  "max_mb": null,      "level": "INFO"},
    "error-log":     {"file": "error-log.jsonl",       "retention_days": 30,  "max_mb": 10,        "level": "WARN"},
    "reasoning-log": {"file": "reasoning-log.jsonl",   "retention_days": 14,  "max_mb": 30,        "level": "DEBUG"},
    "model-drift":   {"file": "model-drift.jsonl",     "retention_days": null,"max_mb": 5,         "level": "WARN"},
    "self-care-log": {"file": "self-care-log.jsonl",   "retention_days": 30,  "max_mb": 10,        "level": "INFO"}
  },
  "rolling": {
    "strategy": "size_and_age",      // rotate on size OR age
    "archive_dir": "archive",         // relative to log_dir
    "archive_format": "{name}-{date}.jsonl.gz",
    "compress": true
  }
}
```

---

## 9. Self-Evolution Phase 6 (EDGE-05)

### Lesson Graduation Algorithm
Location: `_sys/checks/self_care.py` — new function `_check_lesson_graduation()`

```
Trigger: Every session_end (already wired to self_care.py Phase 5)

Algorithm:
  1. Read active-lessons.jsonl
  2. For each lesson: count occurrences in last 7 days
  3. If count ≥ graduation_threshold (from governance_params.json):
     a. Generate proposal: hub.py proposal-add
        title: "Graduate lesson LL-{id} to docs-v2 rule"
        body:  lesson text + occurrence count + suggested docs-v2 target
        voters: protocol.json["consensus"]["r10_voters"]
     b. Mark lesson as "graduation_proposed": true in active-lessons.jsonl
  4. Log to self-care-log.jsonl
```

Config in governance_params.json (add these keys):
```jsonc
"lesson_graduation_threshold": 3,         // occurrences in 7 days → propose graduation
"lesson_graduation_window_days": 7,
"lesson_graduation_target_doc": "_sys/docs-v2/10-invariants.md",  // default target
"lesson_graduation_auto_propose": true    // create proposal without human trigger
```

---

## 10. Implementation Phases & Sequence

### Phase 0: Quick Config Fixes (No code — P0 from resource-governance.md)
**Prerequisite for all other phases. Do first.**

| Item | Action | File |
|------|--------|------|
| P0-01 | Update infra.json DOCS_DIR → docs-v2 | `_sys/ai/infra.json` |
| P0-02 | Update traceability_map.json docs paths | `_sys/ai/traceability_map.json` |
| P0-03 | Fix peers.json gc model (standard: gemini-2.5-pro) | `_sys/ai/peers.json` |
| P0-04 | Fix peers.json cc context/output limits | `_sys/ai/peers.json` |
| P0-05 | Fix orchestration.json cx sandbox flag | `_sys/ai/orchestration.json` |
| P0-06 | Add governance_params.json new keys | `_sys/ai/governance_params.json` |

### Phase 1: Workspace Architecture (P1 — config-only)
1. Complete workspace_base template (add missing files)
2. Create `workspace-config.json` template in workspace_base/specific/config/
3. Add workspace-config.json schema to ops/schemas.md §5 (new section)
4. Add `_sys/ai/common/` as Scope A in infra.json

### Phase 2: Config Layer Creation (P2 — new JSON files)
1. Create `model-registry.json` (from schemas.md spec, populated)
2. Create `routing-config.json` (from §3.3 above)
3. Create `error-taxonomy.json` (from §3.4 above)
4. Create `logging-config.json` (from §8 above)
5. Update traceability_map.json with new entries (§7 above)

### Phase 3: Check Automation (P3 — new Python) ✅ DONE (2026-06-18)
1. ✅ `_sys/checks/check_docs_mece.py` — CHK-01~07, config-driven, exit 0 verified
2. ✅ `_sys/core/hub_logging.py` — 7-type JSONL + rolling gzip
3. ✅ `_sys/core/hub_context.py` — ContextGate v1.0 (CJK-aware, failover chain)
4. ✅ self_care.py wired: docs_mece → Step 3 (CHK-01,02 in --json mode)

### Phase 4: Hub Decomposition (P4 — refactor) ✅ DONE (2026-06-18)
1. ✅ `_sys/core/hub_peer.py` — PeerAdapter Protocol + 4 concrete adapters
2. ✅ `_sys/core/hub_health.py` — read-only health state reader (HealthReader, PeerHealthState)
3. ⏳ adapter_class field in orchestration.json hub_nodes (not yet; auto-detect works)
4. ⏳ Wire hub_context.py ContextGate into action_ask() (Phase 7 — requires R:10)

### Phase 5: Self-Evolution Closure (P5) ✅ DONE (2026-06-18)
1. ✅ self_care.py lesson_graduation step — EDGE-05 closed
2. ⏳ protocol.json autonomous_maintenance section — pending R:10
3. ⏳ health thresholds: currently in lifecycle_policy.json, not protocol.json

### Phase 6: Error Visibility (P6) ✅ DONE (2026-06-18)
1. ✅ `_sys/core/hub_error.py` — taxonomy-driven Korean console display
2. ✅ T1+: Korean console display (peer/action/cause/fix/5Whys + stacktrace)
3. ✅ hub.py action_report_error: calls HubError.report_from_legacy() for severity=error/fatal
4. ✅ error_show_stacktrace, error_5whys_auto_log in governance_params.json

### Phase 7: Integration Closure (P7) ✅ DONE (2026-06-18)
1. ✅ model_profiles.json v0.3 — F-01/F-02 applied (context_window, output_limit corrected)
2. ✅ orchestration.json — adapter_class field added to all 7 hub_nodes
3. ✅ hub.py — ContextGate lazy import + action_ask() check (failover warn / reject exit)
4. ✅ protocol.json v1.2 — autonomous_maintenance section (Phase 1 of self-evolution.md)
5. ✅ traceability_map.json v1.3 — version bump + 4 new runtime entries

### Phase TDD: Comprehensive Test Coverage ✅ DONE (2026-06-18)
1. ✅ test_hub_logging.py — 47 tests, HubLogger 7-type JSONL + rolling/gzip
2. ✅ test_hub_error.py — 37 tests, T0–T4 taxonomy, sys.exit(4), 5-Whys
3. ✅ test_check_docs_mece.py — 44 tests, CHK-01~07 all edge cases
4. ✅ test_hub.py fixes — HubError T4 exit isolation, EPERM exit code
5. ✅ test_hub_peer.py fixes — build_cmd tuple API, stdin mode
6. ✅ test_hub_v41_features.py fixes — lease sweep HubError isolation
7. ✅ hub.py fixes — _write_json_atomic race condition (UUID + backoff), ctx.get() KeyError
8. ✅ README.md rewrite — feature-first, collab_rate table, follow-along examples
9. ✅ remaining-items.md — tech debt + improvement backlog
10. ✅ **Total: 688 tests, 0 failures**

---

## 11. Completion Criteria

Each phase is DONE when:
- [ ] All JSON files created/updated per spec
- [ ] All new Python files pass `python -m py_compile`
- [ ] `check_docs_mece.py --checks CHK-01,CHK-02` exits 0
- [ ] traceability_map.json entries for changed items updated
- [ ] ops/governance.md §6.1 coverage map updated
- [ ] commit: `{type}: {scope} — impl-plan phase N complete`
- [ ] self-evolution.md §5 status updated (⏳ → ✅)
- [ ] _exceptions/README.md EDGE item closed

---

## 12. Open Questions (Require R:10 Before Proceeding)

| # | Question | Blocks |
|---|---------|--------|
| Q1 | Hub module extraction: maintain single hub.py entry or move to package? | Phase 4 |
| Q2 | logging-config.json: new file vs extend governance_params.json? | Phase 2 |
| Q3 | workspace-config.json location: under workspace/ or _sys/ai/? | Phase 1 |
| Q4 | ContextGate: token estimation python function vs hub.py built-in? | Phase 3 |

_All Q answers require peer review before implementation begins. Create proposals via `hub.py proposal-add` for each._

---

_impl-plan.md v1.0 | 2026-06-18 | cc authored, gc architecture input incorporated_
_Next action: Phase 0 config fixes (no code, immediate execution)_

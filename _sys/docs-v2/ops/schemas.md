# Ops — Configuration Schema Reference

> Status: ACTIVE v2 | Updated: 2026-06-19

## 1. peers.json

Installation/provider registry only. Required fields depend on installation type:
package or native binary, root/sys directories, workspace glue, environment,
relocation, cleanup, and logical `node_ids`.

It must not contain model profiles, logical lifecycle, votes, or roles.

## 2. orchestration.json

```jsonc
{
  "_schema_version": 2,
  "profile_contract": {
    "node_id_format": "{peer}.{profile}",
    "required_profiles": ["standard", "effort", "deepthink"]
  },
  "hub_nodes": [{
    "node_id": "cx",
    "type": "peer",
    "enabled": true,
    "adapter_class": "CodexAdapter",
    "invoke": "codex",
    "invoke_args": [],
    "default_profile": "standard",
    "capability_class": "trusted_ipc_mutation",
    "profiles": {
      "standard": {
        "model_id": "gpt-5.4-mini",
        "reasoning_effort": "low",
        "routing_state": "eligible",
        "profile_args": []
      }
    }
  }]
}
```

Tracked `hub_nodes` contain roots only. Generated children inherit adapter,
invocation, memory, timeout, and lifecycle. A profile may narrow but not widen its
parent's lifecycle state.

### `memory` versus `session_mode`

`memory` is descriptive metadata for peer-local persistence available across
invocations. It does not mean that a hub-managed CLI process or conversation is
resumed, and hub routing does not currently consume this field.

- `persistent`: durable peer-local files may survive one-shot invocations.
- `short-term`: local state is bounded or manually managed.
- `session`: the CLI may support resumable conversation state.
- `ephemeral`: no peer-local persistence is relied upon.

`session_mode` is the sole runtime control for hub-managed session reuse.
Therefore `cc` may be `memory: persistent` while every `claude -p` invocation
remains a separate process.

## 3. routing-config.json

`auto_profile_routing` defines deterministic root-request classification:

- ordered profiles and score thresholds;
- explicit metadata and marker signals;
- language-independent request-shape signals;
- capped failure promotion;
- same-peer downward fallback;
- fail-closed all-blocked behavior.

Model IDs remain in `orchestration.json`; routing policy must not duplicate them.

## 4. model-registry.json

Official vendor facts keyed by model ID:

- provider;
- context/output limits when documented;
- reasoning options when documented;
- current status;
- official source and validation date;
- pricing only when verified.

Unknown fields are omitted. Runtime CLI availability does not belong here.

## 5. status_checks.json

Probe definitions only. It must not duplicate lifecycle or gate state. Routine
checks must be zero-token and declare effect class.

## 6. protocol.json

Global collaboration policy: consensus, roles, forwarding, context, health
thresholds, operational guard, and runtime provenance. Voter lists may contain only
enabled root peers.

## 7. Runtime State

`.ai/`, `health.json`, `status.json`, session files, logs, and usage files are
runtime data and must not be tracked. Peer-specific legacy gate files are not
authoritative.

# General — AI Resource Governance

> Status: ACTIVE v4 | Updated: 2026-06-19
> Sources: `orchestration.json`, `model-registry.json`, `routing-config.json`

## 1. Separation of Concerns

| Concern | Canonical source |
|---|---|
| CLI installation, relocation, workspace glue | `peers.json` |
| Logical peer lifecycle, profiles, invocation, permission class | `orchestration.json` |
| Vendor model facts | `model-registry.json` |
| Global collaboration and governance policy | `protocol.json` |
| Runtime health and failures | ignored `health.json` plus `.ai/` provenance |

No generated node list is tracked.

## 2. Node Architecture

Each tracked root peer owns exactly three MECE profiles:

- `standard`: lowest sufficient cost/latency;
- `effort`: default balanced profile;
- `deepthink`: highest verified reasoning setting.

Runtime normalization generates `{peer}.{profile}` children. Root IDs stay stable
and use the low-cost `standard` profile in direct terminals. Root asks through
the hub are classified automatically. Effective enablement is recursive and
fail-closed.

## 3. Routing

Routing order:

1. reject unknown, disabled, blocked, cyclic, or orphaned nodes;
2. preserve an explicitly selected profile;
3. classify root asks using deterministic zero-token signals;
4. select the lowest sufficient eligible profile;
5. prefer continuity when quality is equal;
6. use same-peer downward fallback for blocked profiles;
7. default ambiguous requests to `effort`.

The hub owns transport and policy. A peer adapter owns CLI syntax and session
behavior.

## 4. Cost and Quality

Cost tiers are routing hints, not vendor facts. Exact prices and capacities come
from `model-registry.json`. Runtime measurements are appended to routing/cost logs.
Unknown price or model identity must be recorded as `unknown`, never inferred.

Quality acceptance requires:

- task-specific tests pass;
- independent review for governed changes;
- no unresolved HIGH finding;
- provenance includes selected peer/profile and failure class.

## 5. Context

Peers share explicit state references, not hidden model memory. Compact forwarding
contains the task, constraints, and references. Full history is not relayed through
the human-interface model. Durable shared context requires promotion or ACK.

## 6. Governance and Permissions

Active peers have equal vote weight, leadership eligibility, role eligibility, and
human communication rights. Execution permission mappings are adapter-specific and
must declare a capability class. Governance equality does not require identical
dangerous flags.

## 7. Continuous Update

1. Verify vendor facts from official documentation.
2. Verify local CLI model/option support without a paid model call where possible.
3. Update the registry and affected nested profile once.
4. Run strict config validation, profile validation, tests, and benchmarks.
5. Record source, as-of date, confidence, and any unavailable runtime variant.

For logical peers that reuse an existing installation provider:

```text
peer_mgr.py add <peer> --invoke <cli> [--provider <provider>] --model <model>
peer_mgr.py suspend <peer>
peer_mgr.py resume <peer>
peer_mgr.py remove <peer>
peer_mgr.py validate --strict
```

The lifecycle command synchronizes topology, installation `node_ids`, status
probe inheritance, active/inactive voters, role registries, and the Specific
document. A brand-new CLI/provider installation must first be registered in
`peers.json`.

## 8. Acceptance Metrics

| Metric | Target |
|---|---|
| Normalization median | < 1 ms |
| Full-tree routability median | < 5 ms |
| Generated files tracked | 0 |
| Routine status model calls | 0 |
| Active voter/role parity | exact set equality |
| Disabled descendant routing | 0 |

See `ops/peer-debate-2026-06-19.md` for the full decision record.

# Gate 2 — reconciliation against already-ratified Phase 1 design (ag.deepthink, 2026-09-02)

Verification round following cx's critique's discovery of existing ratified
Phase 1 manifest/admission docs (2026-08-20/21). Three citations
independently spot-verified by the terminal — all accurate:
`peerhub/core/evidence.py:17-24` really defines exactly the 5
`EvidenceState` values (`MEASURED`/`ABSENT`/`UNAVAILABLE`/`ERROR`/`STALE`);
a source-tree grep for `ManifestAdmissionCoordinator`/`engine_id` across
`peerhub/` returns zero hits (confirms the design was never implemented);
`PHASE1-THIRDPARTY-DEFERRAL-AND-SHIMS-2026-08-20.md` really does state the
manifest schema design "stays strictly within the existing deferral
outlined in `ARCHITECTURE.md` section 16.3" for third-party discovery.

## 1. Current vs. drifted

Not drifted — **never implemented**. The design's real target contract
(`peerhub/adapters/contract.py`: `PeerDescriptor`/`ProfileDescriptor`/
`PromptPolicy`/`InvocationPlan`) still matches what the docs describe.
`peerhub/core/evidence.py` implements exactly the 5-state vocabulary the
docs mandate but stops there — it lacks the docs' `attempt_outcome` enums
(`EXECUTED_PASS`/`PRODUCT_FAILURE`/etc.). The design and the current
codebase are consistent where they overlap; the design simply has no
running code behind it.

## 2. Dormant, not abandoned-for-cause

The 2026-08-27 to 2026-09-02 TDD marathon (this session's LEGACY_CATALOG
work) never touched this — it was exclusively scoped to the hub.py-action
translation layer. The marathon's only "manifest" mention is an unrelated
pre-existing test (`test_committed_manifest_snapshot_is_valid`, a Stage-0
surface-manifest generator check, nothing to do with adapter admission).
No formal decision set this design aside; it was simply outside that
marathon's scope the whole time.

## 3. Does the ratified Phase 1 design resolve cx's 4 blocking findings?

| cx's finding | Status |
|---|---|
| 1. Manifest-only discovery silently narrows "auto-detect installed CLIs" | **Not addressed.** Phase 1 explicitly defers third-party *discovery* — it only designs *admission* of an already-configured manifest, per the deferral doc above. |
| 2. `GenericManifestAdapter` doesn't satisfy the real `PeerAdapter` protocol | **Fully addressed.** `PHASE1-MANIFEST-SCHEMA-V2-2026-08-20.md` sections 2-3 solve exactly this: the manifest declares static shape matching `contract.py`, a bounded `engine_id`-selected built-in engine implements the Turing-complete parts (`plan_invocation`/`new_decoder`/`interpret_output`). |
| 3. Registration path can't handle cc/ag/cx (register_adapter_factory raises on existing kinds) | **Partially addressed, real gap remains.** `PHASE1-MANIFEST-SCHEMA-V2` section 6 shows example manifests using `cc`/`cx`/`ag`; `PHASE1-ARCHITECTURE-CONSOLIDATION-2026-08-21` isolates manifest storage in its own `manifest_admission_receipts` table — but never specifies how a loaded manifest bypasses or replaces the hardcoded factories in `registry.py:84-127` that throw on collision. Still open. |
| 4. DTO can't represent its own failure cases | **Not addressed.** Phase 1 designs immutable *admission receipt* schemas (`ManifestAdmissionReceipt`, `ManifestProvisioningEvidenceReceipt`) — since it deferred the discovery sweep entirely, it has no DTO for discovery successes/failures. |

## 4. Concrete scoping recommendation: (c), but split and smaller than it looked

**The ratified Phase 1 design solves the admission/contract-mapping half
completely and correctly. It explicitly, deliberately never attempted the
discovery-sweep half — that's a real, separate, still-open design gap, not
a flaw in what Phase 1 did design.**

Recommended split for the actual remaining work:

1. **Reuse, don't redesign:** adopt `PHASE1-MANIFEST-SCHEMA-V2-2026-08-20.md`
   as-is for the manifest-vs-`PeerAdapter`-contract problem. No new design
   round needed for this half.
2. **New, narrowly-scoped design round:** the discovery sweep itself —
   cx's proposed two-lane model (bounded built-in PATH resolution for
   cc/ag/cx + trusted-manifest discovery for third parties), a
   discriminated DTO for reporting sweep results, and — the one piece
   nothing has designed yet — exactly how a discovered/admitted manifest
   gets bound into `registry.py` without hitting its collision guard for
   already-registered built-in kinds.

This meaningfully shrinks Gate 2's remaining scope: half of it (contract
mapping) is design-complete and just needs implementation once ratified;
the other half (discovery sweep + registry integration) is the one piece
that genuinely still needs a focused design round.

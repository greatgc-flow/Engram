# Architecture decision register and risk register — Rev. 0.6

Status terminology: **USER** = direction explicitly requested or accepted; **PROPOSED** = design default requiring review, not implementation; **OPEN** = technical evidence or owner decision required before dependent implementation; **DEFERRED** = outside MVP. No acceptance implies installation or authorization to collect data, start bots, contact external providers, modify a repository or merge main. These decisions retain ADR-01 through ADR-30 from Rev. 0.5 and extend them, resolving conflicting earlier sketches in favor of the current specification.

| ADR | Decision | Status / rationale | Reversal or gate | Tests |
|---|---|---|---|---|
| ADR-01 | `_sys/AI` root | USER; one portable subtree | Case-insensitive collision and ownership guard | T05,T43 |
| ADR-02 | Optional profiles inside Engram | USER; baseline unaffected | Absent no effects; selected only | T01,T02,T40,T44 |
| ADR-03 | One Ollama; independent native agent sessions | PROPOSED; shared compute but separate source authority | GPU and plugin PoC | T12,T14,T125 |
| ADR-04 | Hindsight + PG/pgvector/native graph | PROPOSED; minimal memory infrastructure | Windows PG and local provider feasibility | T13,T17,T18,T75 |
| ADR-05 | pg0 development only | PROPOSED; not production proof | Verified PG distribution, restore and ACL | T13,T26 |
| ADR-06 | Hermes 64,000 actual context | OPEN; hard documented requirement vs 12 GB VRAM | If no usable profile, Hermes unavailable; direct API alternatives | T10,T120,T124 |
| ADR-07 | Native memory vs verified SSOT | PROPOSED; separate candidates and approved evidence | Test plugin auto-write/approval bypass; disable unsafe path | T15,T113,T114 |
| ADR-08 | Existing PeerHub independent; SecondBrain excluded | USER; reuse without duplicate stores | No install, DB reset or source scan | T38,T77,T92 |
| ADR-09 | Portability versus host dependencies | PROPOSED; driver/credential/security depend on host | Show actual limitations and reauthentication | T06,T27,T65 |
| ADR-10 | Offline versus messenger | PROPOSED; distinct modes | Strict offline only if enforceable, connected-local disclosed | T23,T25,T81 |
| ADR-11 | GPU queue and admission | PROPOSED; prefer backend queue plus minimal arbitration | Prevent nested lease/deadlock, measure | T12,T125,T127 |
| ADR-12 | Standalone graph DB | DEFERRED; use Hindsight first | Concrete unsupported query/performance need and read projection ADR | T18,T119 |
| ADR-13 | Data preservation and sensitive backups | PROPOSED; encrypted private data or explicit omissions | Restore drill, secret sentinel | T26,T32,T55,T138 |
| ADR-14 | Upstream self-updates/lazy installs | PROPOSED; controlled lifecycle only | Disable or mark unsupported | T37,T45,T74,T88 |
| ADR-15 | Existing environment as SSOT | USER; reuse launcher env, CLI and tools | Separate app and task overlays | T33,T34,T76 |
| ADR-16 | Standalone AI extraction | DEFERRED; move full Engram | New scope if explicitly requested | T27,T54 |
| ADR-17 | `ai` terminal entrypoint | USER; no new root launcher or `engram ai` namespace | `_sys/cli/ai.cmd`, shared guard | T39,T42,T43 |
| ADR-18 | Installed AI lifecycle participation | USER; common coordinator | Preserve legacy flags, absent skip, partial report | T44–T48,T57,T84 |
| ADR-19 | Managed model discovery/update | USER; verify same approved variant and recommend new | Risky families/major/cloud changes explicit approval | T49,T50,T51 |
| ADR-20 | Encoder/DB generation consistency | PROPOSED; no mixed spaces even same dimension | Verified migration/backup/rollback | T52,T53,T137 |
| ADR-21 | General Multi-Python | USER direction; independent of AI, legacy paths preserved | Pure registry and provider compatibility | T58–T66 |
| ADR-22 | Latest stable compatible patch per minor | PROPOSED; source/binary/compatible separate | No EOL/new minor automatic installation | T59,T60,T61 |
| ADR-23 | Immutable extra builds and venv generations | PROPOSED; reference-aware GC; no junction | Atomic registry, restore and remove guards | T64,T67,T72 |
| ADR-24 | Full portable provider + optional uv | OPEN; preserve legacy embed; verified new archive | Provider/ABI/registry/junction/security probe | T60,T65,T66,T71 |
| ADR-25 | Hermes PM pin and external interpreter | OPEN; official contract or vendor-private exception | No forced repin/fork; block unsupported | T74,T76 |
| ADR-26 | Default versus session/project selection | PROPOSED; child shell, run/pin, default unchanged | Explicit selection, conflict reject | T58,T63 |
| ADR-27 | App vs task runtime | PROPOSED; environment reconstruction, no in-process import | Existing tools and credential isolation | T35,T36,T76 |
| ADR-28 | PeerHub skill and typed bridge | PROPOSED; existing CLI/DB only, MCP optional | Scope, dry-run, replay/uncertain | T20,T77–T82 |
| ADR-29 | Shared runtime lifecycle | PROPOSED; extra patches auto participate; legacy default special | Consumer pin, offline recovery | T67–T73,T84 |
| ADR-30 | Effective tool/network enforcement | OPEN blocker; prompts/paths not sandbox | Restrict to trusted interactive/manual if no OS enforcement | T23,T81,T113,T136 |
| ADR-31 | Source onboarding and consent | PROPOSED; discover metadata only, explicit selected content | Scope and revocation tests | T87,T103,T104 |
| ADR-32 | Native hooks first, bounded fallback | PROPOSED; Coding Agents and vendor plugins where supported | Per-harness portable config/local endpoint, never all by default | T88–T91 |
| ADR-33 | PeerHub existing history reader first | PROPOSED; no source changes for initial PoC | Explicit source read-only, coverage report | T92,T93,T99 |
| ADR-34 | Generic incremental PeerHub export | PROPOSED, separate repo review; no Hindsight dependency | Independent cursor channels, restore fencing, limits | T94–T98,T149 |
| ADR-35 | Source event identity vs logical task | PROPOSED; preserve evidence, not duplicate success | Exact IDs or explicit mapping; heuristic remains candidate | T100,T101,T146 |
| ADR-36 | At-least-once + idempotent outbox | PROPOSED; no cross-store exactly-once claim | Fault injection before/after ack, reconciliation | T102,T118,T128 |
| ADR-37 | Knowledge Banks + Memory Banks | PROPOSED; document truth distinct from derived memory | 1.3 local text/KB APIs first; unsupported media deferred | T107,T110,T111 |
| ADR-38 | Logical memory types, minimal physical DBs | PROPOSED; native sessions/PeerHub source + Hindsight PG + one control ledger + files | No redundant live semantic store or extra graph/vector server | T112,T147 |
| ADR-39 | Bank isolation and separate trust axes | PROPOSED; scope/actor/type/trust/validity separate | Explicit permission; strict filters alone insufficient | T113,T116,T143 |
| ADR-40 | Independent evidence validation | PROPOSED; adoption/transport not proof, derived observations reviewed | Verification receipt and source refs, conflict/invalidation | T114,T115,T117 |
| ADR-41 | Hippocampal-inspired indexing, not brain simulation | PROPOSED; identity, graph/temporal recall and separation | Use Hindsight first; HippoRAG research only | T18,T119,T146 |
| ADR-42 | Context Manager and real budget | PROPOSED; reuse native compaction; count all context; no forged capacity | Tokenizer/adapter capability, pinned constraints, profile tests | T120–T124 |
| ADR-43 | One shared Sleep Engine | PROPOSED; Hindsight explicit consolidation, native Dreaming private/off by default | Verify single writer and supported async APIs | T126–T131 |
| ADR-44 | Idle compute opt-in and foreground first | PROPOSED; no OS wake/autorun, bounded jobs, safe drain | Real GPU/CPU measurements and lifecycle fencing | T125–T128,T135,T140 |
| ADR-45 | Skill evolution requires independent proof | PROPOSED; immutable approved version, no autonomous active overwrite | Scope, digest, regression, approval, rollback | T133,T134,T148 |
| ADR-46 | Forgetting is retrieval eligibility first | PROPOSED; source retention separate, immediate deny | Deletion/revocation and backup caveats | T103,T117,T142 |
| ADR-47 | Predictive preparation local-only | PROPOSED; scoped draft packs, no external action, expire stale | Source/policy fingerprint and no cloud | T132,T136 |
| ADR-48 | Quality- and coverage-adjusted metrics | PROPOSED; failures/retries included, cumulative not sum | Paired baseline, unknown distinct, no measured claims | T30,T139,T140,T144 |
| ADR-49 | KB/media encoder migration separate | OPEN; memory reembed does not establish KB migration | Candidate rebuild and old generation retained | T137,T138 |
| ADR-50 | English pre-TDD package and stop point | USER; no code/test execution, no repo write | Document audit, resolve blockers before dependent RED | T141 |

## Risk register and gates

Severity is a prospective engineering classification, not measured likelihood. A blocker applies to the affected profile, not necessarily to all independent components. No risk is marked closed merely by design.

| Risk ID | Failure mode | Severity | Mitigation / decisive evidence | Gate / owner | Residual |
|---|---|---|---|---|---|
| K01 | GPU cannot sustain usable 64K Hermes | Critical for Hermes | Actual backend allocation, context/tool gold, peak VRAM/latency | G1 / runtime | Disable Hermes; no silent fallback |
| K02 | PG+pgvector native Windows distribution/ABI unavailable | Critical for memory | Verified artifact, extension, backup/restore, standard-user process | G1 / memory | Block memory profile or separately approve alternate backend |
| K03 | Hindsight 1.3 local model/KB provider exceeds RAM/VRAM | High | Text-first, CPU resource caps, isolated media benchmark | G1/G3 / memory | Text profile; media unsupported |
| K04 | Hermes PM requires private pinned Python / writes host | High | Pinned launcher/update and footprint probe | G1 / runtime | Vendor exception only if managed and approved |
| K05 | uv/vendor install changes registry/junction or host deps | High | Archive stage, verify flags/footprint | G1/G2 / Engram | Block provider or choose approved alternative |
| K06 | Untrusted hooks or plugin sends history to cloud | Critical | Explicit endpoint, consent and traffic probe, config restore | G3/G5 / collector | Disable unsafe integration |
| K07 | Direct same-user shell/network bypass | Critical | Real OS/ACL/egress containment, deny unsafe automation | G5 / security | Trusted interactive only; no strict offline claim |
| K08 | Candidate or observation becomes approved without evidence | Critical | Controlled writer, bank/response filter and proof checks | G3/G5 / memory | Candidate-only mode |
| K09 | Cross-project/untagged/linked KB leakage | Critical | Auth mapping and adversarial query suite | G5 / security | Separate instance or disabled scope if boundary inadequate |
| K10 | Source/derived data duplicated or lost on replay/restore | Critical | Identity, source lineage, outbox and resnapshot fault tests | G3/G4 / collector | Explicit partial coverage, quarantine |
| K11 | Late PeerHub outcome or terminal ack missed | High | Independent change channels/watermarks, overlap fallback | G3 / PeerHub | Coverage partial until export proved |
| K12 | Export depends on private SQLite schema | High | Generic read extension and versioned contract; fallback current CLI | G3 / PeerHub | Pin supported API only, no write coupling |
| K13 | Provider usage double counted / false savings | High | Attributable measurement and coverage, no cumulative sum | G6 / evaluation | Unknown metrics excluded from claim |
| K14 | Model tag overwrite destroys rollback | Critical | Verified candidate stage and old revision retention | G4 / runtime | Hold update |
| K15 | Embedding space mixed or migration loses memories | Critical | Candidate generation, restore and gold recall | G4 / memory | Old index kept; migration blocked |
| K16 | PG/SQLite/files backup cut inconsistent | Critical | Drain/checkpoint/hash/restore in isolated target | G4 / lifecycle | No successful backup claim |
| K17 | Sleep background work starves interactive or deadlocks | High | Priority/short units, actual wait measurements, no nested leases | G3/G6 / scheduler | Defer or disable sleep |
| K18 | Stale sleep worker publishes after restore/update | Critical | Generation/lease fence and reconcile ambiguous operation | G4 / scheduler | Quarantine unknown |
| K19 | Generated skill executes untrusted or unsafe code | Critical | Candidate isolated tests, explicit approval, typed runner | G5 / skills | No automated skill execution |
| K20 | Compaction drops required instruction/evidence | High | Pinned constraints, serialized budget, proof comparisons | G3/G6 / context | Segmentation / block |
| K21 | Raw logs/documents contain secrets, legal/private information | Critical | Scoped enrollment, metadata-only mode, redaction and encrypted backup | G5 / privacy | Quarantine/exclude; no universal completeness |
| K22 | File parser bomb/macro/path escape or source change | High | Bounds, no-follow, stable hash, local parser isolation | G3/G5 / ingestion | Unsupported/missing source explicitly |
| K23 | Uninstall/reset deletes durable data or external workspace | Critical | Ownership subplan, purge separate, verified backup | G4 / Engram | Preserve by default |
| K24 | Core update handoff loses pending AI plan or stale approval | Critical | Durable parent/child receipts, revalidate and fault injection | G4 / Engram | PARTIAL / recovery required |
| K25 | New features break existing single-runtime Engram | Critical | Baseline regression and absent-profile no-effect suite | G2/G4 / Engram | Reject release |
| K26 | Source consent revoked but stale result still returned | Critical | Check at retrieval/serialization, invalidate derivatives and cache | G5 / policy | Deny immediately; purge separately |
| K27 | Long history scan pins WAL or blocks collaboration | High | Short bounded pages, approved snapshot, latency evidence | G3 / PeerHub | Throttle/defer and report coverage |
| K28 | Actual provider/session context or tool behavior differs from docs | High | Pin/probe; record coverage and no invented private context | G1/G3 / adapters | Disable unsupported feature |

## Open decisions before dependent RED tests

1. Exact approved release/architecture/artifact digests/licenses, CPython provider, native runtime lock, PG+pgvector pairing, Hindsight/KB package and local model role candidates. No live version pin in this document.
2. Hermes PM external interpreter/runtime ownership and actual 64K performance; OpenClaw npm/native gateway; installed CLI hook paths and compatible Hindsight plugin versions.
3. Runtime-specific support of local embedding/reranker/decision/KB providers and supported async operations, review/invalidation hooks and same-ID retain semantics. Choose text-only P0 if needed.
4. Source consent scopes and retention defaults, actual user's selected folders/AI history; no consent inferred for broad import. Exact owner/bank isolation and OS-level tool policy, safe failure mode.
5. PeerHub read export contract review; determine whether append-only evidence and feedback sequence + stream partition cursors cover all required revisions. Phase A fallback remains useful with partial coverage.
6. Exact CLI syntax/exit mapping, selector compatibility, schemas and canonical digest rules; numeric thresholds for actual hardware, acceptable foreground wait, storage limits, test fixtures and benchmark scoring. No speculative universal thresholds.
7. Backup encryption/key handling and recovery scope, optional native private Dreaming, optional messenger/media and graph expansion are separate feature choices.

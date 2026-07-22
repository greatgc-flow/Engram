# Phase 2 Architecture: No-Code, Config-Driven General-Specific MECE Structure
> **Status:** design, architecture AND feasibility both converged 2026-07-22
> (architecture: 5 rounds, ag.deepthink draft -> cx.effort reject-with-
> alternative -> ag concede+revise -> cx round-3 gaps -> ag apply-fixes ->
> cx catalog/conformance gap -> applied. Feasibility: independent parallel
> reviews by ag.deepthink + cx.effort, converged on §12's risk assessment
> and phasing despite different measurement methodologies -- real
> agreement, not rubber-stamping). User independently confirmed the §7
> SUBST/legacy-migration decision after the 260-char justification was
> verified empirically. §13 (Ideal Target Architecture) adds a further,
> unlimited-round adversarial-debate layer (5 more rounds, ag.deepthink +
> cx.effort) plus a final ratification pass by each peer's highest-capability
> model (ag.opus, cx.deepthink, cc.fable) -- no architectural flaws found,
> concrete spec gaps patched into §13.8-13.12. A FURTHER 14-round QA-diff
> audit chain then followed (self-audit, ag.deepthink, cx.effort, and
> cx.deepthink alternating; EXH-based quota routing sent later rounds to
> whichever peer's pool was safest), each round checking the PRIOR round's
> own fixes for new inconsistencies -- finding density genuinely dropped
> round over round (6,5,4,5,3,3,3,2,1) and round 14 returned an explicit,
> unforced **CONVERGED** verdict after tracing every remaining concurrency
> interaction (upgrade-vs-emergency-quarantine race, crash recovery,
> first-init bootstrap ordering, and more) with no further findings. A
> SEPARATE meta-level pass (5-Whys + MECE + feedback-loop lenses, per user
> request, 3 further rounds) then asked a different question -- not "is
> each mechanism correct" but "is §13 organized at the right level of
> abstraction" -- and found a real cross-cutting Constraint-5 violation
> (bundle/workspace/registry mutation had independently reinvented the same
> CAS+receipt+audit pattern three times) plus a genuinely missing feedback
> loop (accumulated Evidence was write-only, never improving future
> decisions). §13.15 (Governed Mutation Protocol) and §13.16 (Evidence
> Feedback Loop) were added to close both gaps, explicitly rejecting a
> stronger "everything is one universal resource" generalization as
> over-engineering, then themselves audited for 2 further rounds (5 fit
> problems found and fixed, including a HIGH-severity emergency-quarantine/
> generic-protocol mismatch) before round 3 returned CONVERGED with an
> explicit, reasoned abstraction-ceiling verdict: going further than
> §13.15/13.16 would add indirection with no new consumer. This does NOT
> change the §1-12 MVP migration path; it documents the further target
> §1-12 must not foreclose. Not yet implemented -- §1-12 is the
> architecture AND phasing to build Phase 3 (TDD prep) against, starting
> with §12's phasing step 1 only; §13 is the North Star those phasing steps
> must remain compatible with.
> **Scope:** Phase 2 Pre-TDD Architectural Planning
> **Objective:** Dismantle hardcoded coupling (Windows/SUBST/.bat assumptions) and establish a strict, lazy, configuration-driven MECE boundary between General (Source) and Specific (Config/Instructions).

## 0. Prior Art

`ops/endgame-general-specific-plan-2026-06-28.md` (still `design` status,
never implemented, found only after this document had already converged
through 5 debate rounds) covers substantially the same ground -- General/
Specific/Directive separation, JSONized connection points, a base-template
concept, workspace-local vs. common-vs-core layering, lazy loading, error
visibility. Rather than maintain two competing "endgame" architecture docs
(a MECE violation this project has specifically been cleaning up elsewhere),
this document supersedes it as the primary architecture reference and
absorbs its still-valuable structural pieces below (§9-§11); the 06-28 doc
is marked `superseded-by` in 00-MANIFEST.md. What THIS document adds beyond
06-28: an explicit multi-platform / installed-elsewhere framing (06-28 was
scoped to reorganizing the single existing PortableDev install, not true
cross-OS or install-once-use-many-workspaces), the `RuntimeContext`
construction-precedence design, and a hardened, catalog+conformance-checked
adapter contract mechanism (vs. 06-28's looser field-list description) --
refined over 3 further debate rounds specifically because the first version
(a raw importable string path per method) was a real security/robustness
gap, not just style.

## 1. General vs. Specific Boundary
The core architectural mandate is that **Source Code = General** and **Config/Instructions = Specific**.

*   **General (Source Engine):**
    *   Files: `hub.py`, `snapshot.py`, `diag.py`, `provisioner.py`, and underlying Python modules.
    *   Role: Pure execution engines. They provide a non-implementation-specific common interface.
    *   Constraint: They MUST NOT contain hardcoded references to specific peers (`cc`, `ag`), specific paths (`P:\.ai`, `_sys/`), specific OS dependencies (unless abstracted behind an interface), or magic strings. If an entity exists, it is loaded dynamically from configuration.
*   **Specific (Config, Instructions, Profiles):**
    *   Files: `orchestration.json`, `protocol.json`, `paths.json` (new), `runtimes.json`.
    *   Role: Declare the universe. They define what peers exist, what OS-specific adapters to use (e.g., WinPTY vs. standard PTY), thresholds, paths, and metadata.
    *   Constraint: Ambiguous edge cases and "one-off" wiring logic are absorbed here via structured properties, never by adding new conditional branches (`if peer == "ag"`) in the source.

## 2. Four Logical Stores (Replacing 3 Physical Locations)
The current architecture tightly couples the portable application (`PORTABLE_ROOT`) with the user's workspace. The new design splits these domains into four distinct logical stores.

*   **Immutable Core (The Engine):**
    *   Location: E.g., `~/.engram-core/` or `%APPDATA%/Engram/`.
    *   Contents: The Python source, base JSON schemas, downloaded runtimes. Upgraded collectively via a bootstrap script. No user project data lives here.
    *   *Bootstrap Manifest Exception:* A minimal packaged bootstrap manifest (`bootstrap.json` or `.env`) declares core environment variables used by the launcher shell script to find Python.
*   **Shared Global Config + Instructions:**
    *   Location: E.g., `~/.engram-shared/config/`.
    *   Contents: Global `user-directives.md`, `peers.json` (installed adapter configurations), and global security policies.
*   **Shared Mutable Data:**
    *   Location: E.g., `~/.engram-shared/data/`.
    *   Contents: `global-mistake-events.jsonl`, centralized telemetry, vector DBs. Distinct from config to ensure safe backups and reset paths.
*   **Workspace-State (The Active Context):**
    *   Location: A dedicated `.ai/` (or `.engram/`) directory under the active repository (e.g., `C:\MyProject\.ai\`).
    *   Contents: Active session pointers, `project-directives.md`, and local config *overrides*.

## 2.5 RuntimeContext (The General-Specific Bridge)
No module may derive a root from `__file__`, `cwd`, or an environment variable later in its execution (eliminating the `CORE_DIR = Path(__file__).parent` anti-pattern).
Instead, a single `RuntimeContext` is constructed exactly once at startup and passed through every service. 

**Construction Precedence (Highest to Lowest):**
1.  **CLI Arguments:** e.g., `--workspace C:\Project`.
2.  **Bootstrap Manifest / Environment Variables:** e.g., values sourced from `bootstrap.json` by the launcher shell script.
3.  **Discovery (Heuristics):** Walking up from `cwd` to find a `.ai/` or `.engram/` directory.

## 3. The "Base Template" for Workspace Setup
When initializing a new workspace, the system uses a purely configuration-driven template instead of hardcoded initialization logic.

*   **Artifact (`core_templates/init_workspace.json`):**
    ```json
    {
      "schema_version": "1.1",
      "directories": [
        { "operation": "ensure_directory", "path": ".ai/sessions", "permission_profile": "workspace_private" },
        { "operation": "ensure_directory", "path": ".ai/logs", "permission_profile": "workspace_private" }
      ],
      "files": [
        { "operation": "ensure_from_template", "destination": ".ai/local-config.json", "source": "defaults/workspace_config.json", "on_existing": "preserve" },
        { "operation": "ensure_managed_block", "destination": ".gitignore", "block_id": "engram-workspace-state", "content_template": "defaults/gitignore.engram", "on_conflict": "report" }
      ]
    }
    ```
*Note: `workspace_private` resolves per-platform (POSIX mode 0700 / Windows owner-only ACL) via the platform service, not the template.*
*   **Execution:** A generalized initializer reads this JSON and guarantees the directory shape, providing the base template without writing custom Python initialization code.

## 6. Versioned Adapter Contract Schema & Config Trust
The wiring between the General engine and Specific integrations is governed by a versioned adapter contract. The engine validates this contract and resolves to exactly one adapter, failing loudly if the OS is unsupported. 

**Precedence & Trust:** A workspace MUST NOT be able to override global adapter executables or security policy. Only schema-declared properties (like timeouts or model choices) can be overridden by workspace configs. No unknown configuration may fall back to `BaseAdapter`.

*   **Catalog/conformance rule (cx.effort's final-round finding, applied
    2026-07-22):** `peers.json` may reference only a LOGICAL implementation
    ID (e.g. `builtin.agy.v1`) -- it must never contain an importable
    string path/method (`"internal.AgyAdapter.build_cmd"` is not safely
    executable on its own: no defined trust boundary for what `internal`
    resolves to, no interface-version check, no import/integrity
    validation). Instead:
    - The **Immutable Core** owns an allowlisted **adapter catalog**:
      implementation ID → package/module factory, `PeerAdapter` interface
      version, required platform-service bindings, and package/version/
      integrity metadata.
    - At startup, the engine resolves the catalog entry, validates the
      loaded object's FULL `PeerAdapter` conformance (not just the 5
      methods named below -- the real interface also includes
      `session_fingerprint`, `get_session_state`, `store_session_state`,
      verified against hub_peer.py:458/473/497/501), then calls it as a
      normal object. Method names in a peer's config are documentation/
      conformance-test expectations, never runtime dispatch strings.
    - `platform_overrides`' `service_binding` values (e.g.
      `platform.winpty.launcher`) resolve through the same kind of
      engine-owned, catalog-checked platform-service registry -- never a
      raw string executed directly.

*   **Example (`peers.json` schema separating implementations from instances):**
    ```json
    {
      "schema_version": "1.3",
      "adapter_implementations": {
        "builtin.agy.v1": {
          "description": "Antigravity PTY Adapter",
          "peer_adapter_interface_version": "1.0",
          "package": "engram_core.adapters.agy",
          "integrity": { "sha256": "<pinned-at-install-time>" }
        },
        "builtin.codex.v1": {
          "description": "Codex Subprocess Sandbox Adapter",
          "peer_adapter_interface_version": "1.0",
          "package": "engram_core.adapters.codex",
          "integrity": { "sha256": "<pinned-at-install-time>" }
        }
      },
      "peer_instances": {
        "ag": {
          "implementation": "builtin.agy.v1",
          "platform_overrides": {
            "windows": { "service_binding": "platform.winpty.launcher" }
          }
        },
        "cx": {
          "implementation": "builtin.codex.v1",
          "platform_overrides": {}
        }
      }
    }
    ```
*Note: The actual parsing/session/transport logic lives in code inside the
catalog-registered implementation package (`builtin.agy.v1`), never named
by string in config. The WIRING of which implementation handles which peer
is strictly config-driven and fails loudly on a catalog-lookup or
conformance-check mismatch -- never a silent fallback to `BaseAdapter`.*

**Catalog metadata taxonomy (absorbed from 06-28's adapter capability
schema, which named more semantic categories than this document's own
examples covered):** each `adapter_implementations` entry should declare,
not just `contracts`/`package`/`integrity`, but also: `transport` (pty /
subprocess / sandboxed-subprocess), `session` (resumable / stateless),
`permissions` (filesystem/network scope the implementation needs),
`context_policy` (how it reports/manages context window occupancy),
`status_probe` (how health/liveness is checked), `runtime_home` (where its
own state/cache lives, mapping to the 4-store model in §2), and
`mutation_profile` (whether it can perform governed mutations at all, and
under what guard). A peer delta checklist requirement carries over
unchanged from 06-28 §"Phase 5": every registered implementation must fill
the same fields or explicitly declare a field unsupported -- no silent
gaps.

## 7. Hardcoded but Genuinely Un-Generalizable Exceptions
Per Constraint #5, exceptions must be flagged explicitly:

1.  **The Bootstrap Shell Layer (`INSTALL.bat` / `launcher.sh`):** To launch Python, we need a shell script. Shell syntax (cmd/bash) is inherently OS-specific. This layer should do nothing more than resolve the Python executable path and pass arguments.
2.  **Low-Level OS API Calls (Terminal / PTY):** e.g., `pywinpty` for AntiGravity's transport on Windows. These must be encapsulated behind a General interface (e.g., `ITerminal`), but the concrete classes will inherently contain specific hardcoded syscalls.
3.  **Process Supervision & Command Resolution:** Managing subprocesses (starting, tracking PIDs, killing trees) touches OS primitives heavily.
4.  **Filesystem Permissions & Locking:** Atomic file replacements and read/write locks behave fundamentally differently on NTFS vs. POSIX.

> **⚠️ LEGACY MIGRATION FLAG:** The current `SUBST`/junction-based virtualizer (`virtualizer.py`) is demoted to an **Optional Legacy Migration Backend**. Because this has a high blast radius (our current environment relies on it to bypass 260-char limits), this transition MUST be gated behind explicit user confirmation before being locked in. We will shift to native LongPaths where possible.

## 8. Structured Error Model (Constraints 13 & 14)
*   **Structured Outcomes:** `ConfigResolutionError` is insufficient. The General engine must use a structured outcome model (e.g., `Result[Value, FailureReason]`). If `snapshot.py` fails to read a config, it returns a structured `Unavailable(reason="Missing File")` rather than swallowing the error or relying on broad `try/except` fallbacks. This guarantees the user can clearly perceive *why* an action failed.
*   **Laziness:** Configuration schemas, adapters, and heavy modules are strictly lazily loaded. If a workspace asks `cc`, the engine will *never* evaluate or import the `ag` adapter configuration.

## 9. Cleanup Policy (absorbed from 06-28 §5, adapted)

Any implementation slice that touches runtime state needs an explicit
policy for what's safe to remove automatically vs. what needs a human:

*   **Delete automatically when requested:** root-level transient logs,
    `tmp/`/pytest-local temp dirs and synthetic write-probe files, empty
    untracked accidental peer directories, untracked scratch folders with
    no manifest/config reference/active process lock.
*   **Keep:** `.ai/` active room state, `_archive/` durable history,
    `_sys/env/` (reinstallable but currently active runtime), peer auth/
    config homes (unless running a full cleanup tier), all tracked docs/
    source/config/templates/schemas.
*   **Human-only purge:** `Garbage/`, accepted/rejected/expired proposal
    archives, any tracked file, any runtime cache that may contain auth,
    conversation continuity, or paid-usage state.

## 10. Traceability (absorbed from 06-28 §"Phase 6")

Every implementation slice in Phase 3+ needs a row in a
`traceability_map.json`-style ledger before source changes: requirement ID
-> docs section -> config node -> source module -> check/test. A release
gate checks: docs MECE, profile parity, config strictness, path existence,
anchor integrity, hardcoded-path scan. No implementation slice lands without
its row existing first -- this is a process gate for Phase 3/4, not
something Phase 2 itself needs to build.

## 11. Completion Loop (absorbed from 06-28 §8, unchanged -- still the
right process)

Repeat until no open gaps remain, for this document and its successors:
1. Observe: run status, docs, config, path, and git checks.
2. Classify: map every finding to docs, config, source, runtime, template,
   or archive.
3. Plan: update this design (or its successor) with exact artifacts and
   acceptance gates.
4. Cross-review: at least one non-author peer reviews architecture/risk
   (this document's own 5-round history is one instance of this loop
   already running).
5. Reconcile: convert agreed findings into manifest, MOC, traceability, or
   backlog updates.
6. Stop line: do not implement source until the affected slice has
   schemas, tests, and traceability.

## 12. Feasibility & Risk Assessment (converged 2026-07-22, ag.deepthink +
cx.effort independent parallel reviews)

The design in §1-11 is sound but **not buildable as a single implementation
pass** -- both reviews independently measured the real coupling and
converged on the same conclusion by different methodologies (ag: 48
`Path(__file__)` sites across 12 files; cx: 122 direct root/path-resolution
references across hub.py/snapshot.py/diag.py/hub_peer.py, hub.py alone at
10,825 lines / ~330 functions). Per-concern verdict:

1. **hub.py's internal coupling (consensus/IPC/leases/routing) is real and
   high-risk to untangle.** Do NOT attempt to split hub.py into
   microservices as part of this work. Inject `RuntimeContext`/catalog
   services at action boundaries; leave the internal engine cohesive.
   Characterization tests must precede any change to lease/IPC/routing
   code specifically.
2. **RuntimeContext's blast radius is real but bounded if done right.**
   Do NOT thread a new parameter through every function signature (would
   touch hundreds of call sites). Instead: a small number of service
   objects (e.g. `HubRuntime`, `SnapshotService`, `AdapterCatalog`) hold
   the `RuntimeContext` and get migrated in incrementally, module by
   module -- snapshot/diag's read-only paths first (lower risk), hub.py's
   config/action boundaries later.
3. **Dynamic adapter loading (a raw "package" string resolved via
   importlib) is a genuine critical security risk, not just a style
   concern -- confirmed independently by both reviews.** Scope reduction:
   the engine ships a hardcoded, allowlisted built-in registry
   (`"builtin.agy.v1"` -> the real `AgyAdapter` class); the JSON config is
   a STRING SELECTOR into that registry, never a dynamic import path.
   True third-party/plugin loading is explicitly deferred until there's a
   real second implementation that needs it, plus package signing/
   ownership/isolation design that doesn't exist yet.
4. **Multi-platform support cannot be claimed, only designed for, until
   real CI exists.** No Linux/macOS runner exists today; current tests
   include Windows Sandbox/WinPTY-only paths. The honest framing (cx's
   phrasing, adopted here) is **"portable-ready, Windows-validated"** --
   the schema has a `platform_overrides` shape, but only Windows bindings
   are actually implemented and claimed until a Linux runner exists (macOS
   follows its own separate runner).
   *Mobile platforms (user question, 2026-07-22, revised same day after a
   follow-up question):* **Android** is not a separate target -- a genuine
   Linux userland (e.g. Termux) provides real subprocess/PTY/filesystem
   support, so it falls out of Linux support once that exists, with no
   dedicated mobile work needed. **iOS is out of scope for the CLI-based
   execution model in this document, but NOT permanently impossible --
   correcting an overstated claim made earlier the same day.** The specific
   things iOS's app sandbox prohibits (arbitrary subprocess spawning, PTYs,
   unrestricted filesystem access) are exactly what the current
   `pty_wrapper`/`subprocess`/`subprocess_sandbox` adapter kinds in §6
   depend on. A hypothetical fourth adapter kind, `api_client` -- calling
   each peer's underlying LLM directly (Anthropic Messages API / OpenAI
   API / Gemini API) instead of spawning its CLI, with tool-use (file
   read/write, code execution) reimplemented natively for iOS's sandbox
   (app-container storage, user-granted folder access) instead of shelling
   out -- would sidestep the exact restrictions that block iOS today. This
   is explicitly NOT "porting" work: it replaces the entire peer-execution
   layer with a different mechanism, is a much larger and separate effort
   from everything else in this document, and needs its own feasibility
   pass (including whether ag/Antigravity's actual capabilities have a
   1:1 API equivalent, which is unconfirmed) -- not scoped or committed to
   here, just recorded as "possible via a different architecture," not
   "impossible."
5. **Over-configuration is a real, checkable risk.** Concrete test for
   whether a value deserves a JSON config field (cx's heuristic, adopted
   as the working rule): does it have more than one real supported
   deployment, OR does it have a genuine workspace/global owner who might
   reasonably need to change it? If neither, it's a Python constant, not a
   config field -- adding config surface without a real consumer is schema
   bloat, not flexibility.

### Converged Phasing (supersedes any single-pass reading of §1-11)

1. **Characterization tests first.** `RuntimeContext`/schema objects
   introduced with NO behavior change -- everything passes exactly as it
   does today. Standalone template initializer ships in dry-run mode only.
2. **Built-in-only adapter catalog** that reproduces cc/ag/cx's current
   command and session behavior exactly, via the hardcoded registry from
   concern #3 above. No plugin loading.
3. **Incremental RuntimeContext migration:** snapshot.py/diag.py's
   read-only paths first, then hub.py's config/action boundaries. Current
   workspace state layout (`.ai/`) is retained, not restructured, during
   this phase.
4. **Windows install-once / external-workspace support**, plus the
   explicit legacy-virtualizer compatibility mode from §7's SUBST decision.
5. **Only then**, platform-service abstraction + an actual Linux CI runner
   -- POSIX support is implemented and claimed after this, not before.
   macOS is its own later runner/phase.
6. **Third-party adapters/plugins deferred indefinitely** -- revisit only
   if a real second implementation genuinely requires the capability.

## 13. Ideal Target Architecture (North Star)

> **Final Review Status (2026-07-22):** Unlimited-round adversarial debate (4 rounds, ag.deepthink + cx.effort) converged on the architecture in §13.1-§13.7 below. A final ratification pass by each peer's highest-capability model (ag.opus, cx.deepthink, cc.fable) found no architectural flaws requiring redesign, but identified concrete specification gaps -- all patched into §13.8-§13.12 below. No further debate rounds are needed; this section is fix-and-frozen.

### 13.1 Five Stores + Five Planes

The §2 four-store model remains the migration target. The ideal target adds an independently versioned **Capability Bundle** store, preventing adapter and extension updates from conflicting with an immutable Core Engine.

*   **Stores answer "where":** The ideal physical stores are Core Engine, Shared Config, Shared Data, Workspace State, and Capability Bundle.
*   **Capability Bundle store:** Contains adapter and extension code, manifests, schemas, and bundle-local documentation. Bundles carry independent version NUMBERS from the Core Engine (a versioning/identity independence). This does NOT mean independent DISTRIBUTION or independent trust authorization in MVP -- §13.11 resolves that the trust catalog determining which bundle digest is actually authorized remains Core-release-coupled (fixed 2026-07-22, ag.deepthink finding: an earlier unqualified reading of "independently versioned" here contradicted §13.11's own resolution).
*   **Planes answer "what kind":** The following five orthogonal planes classify each artifact by its role:
    *   **Mechanism:** How work is done; kernel and Capability Bundle source code.
    *   **Policy:** What is allowed; permissions, thresholds, governance, and effective constraints.
    *   **Binding:** What exists where; peer-to-bundle mappings and logical-resource-ID-to-physical-location mappings, realized through the `ResourceRegistry`.
    *   **Evidence:** What happened; state, telemetry, lessons, audit records, and diagnostics.
    *   **Instruction:** Human-readable documentation, guidance, and operational procedures.
*   **Classification rule (corrected 2026-07-22, cx.deepthink finding):** Every Engram-OWNED artifact has both a Store classification and a Plane classification. Store and Plane are distinct axes and must not be used interchangeably. External resources Engram merely delegates to (e.g. the OS keychain via `CredentialResolver`, §13.5.5) are NOT artifacts and are explicitly outside this rule -- they are classified as dependencies, not stored content.

### 13.2 RuntimeContext as Dependency Injection (not Singleton)

The bounded Singleton in §2.5 is migration scaffolding and documented technical debt, not the end-state runtime model.

*   **Composition root:** `EngramApplication` is constructed once at process start and is the sole composition root for runtime services.
*   **Immutable runtime context:** `EngramApplication` creates one immutable `RuntimeContext` containing resolved roots, platform capabilities, and the resolved Policy revision.
*   **Workspace scope:** Each selected workspace receives a `WorkspaceScope` containing workspace-specific bindings and state.
*   **Explicit dependency injection:** Services receive `RuntimeContext` and, where applicable, `WorkspaceScope` explicitly. Services must not read a process-global `.get()` singleton.
*   **Concurrency consequence:** This permits a future daemonized hub to serve multiple workspaces or VS Code windows concurrently. A Singleton would structurally foreclose that model.
*   **Migration trigger:** Implementing `EngramApplication` as the composition root is the explicit milestone that retires the bounded Singleton.

### 13.3 Adapter Model: Protocol Contract + Capability Bundles + Narrow Declarative Tier

*   **Single contract:** All adapters conform to one `PeerAdapter(typing.Protocol)` contract, marked `@runtime_checkable`.
*   **Load-time screen:** `isinstance(adapter, PeerAdapter)` is used as a fast load-time shape screen.
*   **Important caveat:** `isinstance()` against a runtime-checkable `Protocol` verifies attribute and method presence only. It does not verify signatures, async behavior, or return schemas. It is therefore not sufficient contract enforcement by itself; §13.12 defines the required conformance enforcement.
*   **`python_bundle` adapters:** The general case. Complex peers, including current ag/cx behavior involving PTY lifecycle, asynchronous output, cancellation and process-tree cleanup, app-server session/resume behavior, and quota RPCs, implement `PeerAdapter` directly in Python and are packaged as versioned, integrity-checked Capability Bundles.
*   **`generic_cli` adapters:** A narrow declarative case, design-final but explicitly deferred from implementation. A single core-owned `DeclarativeCliAdapter` implements `PeerAdapter` and is parameterized by a JSON manifest for simple, stateless, one-shot CLI tools.
    *   **Allowed surface:** Structured `argv` list only; bounded stdin or file input; explicit deadline; plain-text output or JSON-pointer/anchored-single-match-regex output parsing.
    *   **Forbidden surface:** Shell strings, shell evaluation, arbitrary regex, general expression languages, PTY, streaming, sessions, and resume behavior.
    *   **Scope limit:** This adapter must not attempt to cover PTY, streaming, or session/resume peers.
    *   **Deferral:** No current peer (cc/ag/cx) fits this profile. Implementation is deferred until a real simple-CLI peer requires it.
*   **Zero-code exception:** The current Python adapter norm is a defensible, explicitly called-out exception to the zero-code goal under Constraint 5, not an unacknowledged violation.

### 13.4 Unified CLI Layer

*   **Canonical command:** The installed CLI is one `engram` command, exposed through standard Python packaging via `pyproject.toml` `[project.scripts]`.
*   **Command shape:** The command uses verb-subcommand form, for example `engram peer add`, `engram diag`, and `engram workspace init`.
*   **Legacy wrappers:** Existing `hub.py`, `agy_entry.py`, `diag.py`, `peer_console.py`, and per-tool `.bat` wrappers are replaced by the canonical command surface. `.bat` and `.sh` wrappers become thin, deprecated compatibility aliases with no operational logic.
*   **Namespace ownership:** Core owns root-level namespaces. A bundle contributes only through a declared extension point or through a collision-free namespace such as `engram extension <bundle-id> ...`. Bundles cannot shadow Core verbs.
*   **Lazy command discovery (Constraint 14):** Command discovery, `--help`, and shell completion read ONLY the Bundle Registry Index's cheap metadata (id/version/commands/compatibility/hash) without importing bundle code or parsing full manifests. This is a **staged validation** model, and the staging is by TIME not by re-checking: full manifest schema validation happens exactly once, during install/upgrade (the `verified` gate itself, §13.5/§13.11) and during any explicit `engram plugin verify --all` (§13.10) re-audit -- schema validation is never re-run at command-selection time. What IS deferred to selection is reading the specific selected bundle's already-verified metadata and lazily importing only its handler module.
*   **Invocation-time integrity check, NOT re-validation (TOCTOU fix, cx.deepthink finding, 2026-07-22):** "never re-validated at selection" governs manifest SCHEMA validation only, not integrity. On-disk content can change between an earlier `verified` pass and a later handler import (a time-of-check/time-of-use gap) -- "safe to delete at any time" (§13.10) is otherwise incompatible with help/dispatch silently depending on stale content. At the point of actually importing a selected handler, the engine verifies that the active lock entry, the index record, the manifest digest, and the installed bundle's content digest all still match. Installed bundles live in a content-addressed, immutable directory (keyed by digest) rather than a mutable in-place path, so a digest match guarantees byte-identical content, not just a plausible name match. Each index entry is bound to an `install_generation` that must equal the active lock's current generation; a mismatch, or an index that is missing/stale relative to installed bundles, fails closed with an explicit error directing the user to `engram plugin verify --all` (§13.10) rather than silently proceeding on unverified assumptions.
*   **Compatibility:** Bundles declare a range-based CLI contract using the same canonical `engine_api` field as §13.5's manifest, for example `engine_api: ">=2,<3"`. Incompatible bundles are disabled with an explicit user-visible reason. Silent compatibility shims are prohibited.
*   **Machine output:** Machine-readable command output uses a versioned result envelope. Consumers must not parse human-readable CLI text.

### 13.5 Capability Bundle: Package Layout, Lifecycle, Permissions

A Capability Bundle is a versioned package containing a peer implementation or extension.

```text
capabilities/
  io.openai.peer@1.2.0/
    bundle.json
    bundle.integrity.json
    src/
      engram_openai/
        factory.py
        adapter.py
        commands.py
        hooks.py
    schemas/
      config.schema.json
    docs/
      README.md
```

*   **Manifest:** `bundle.json` declares `bundle_id`, `version`, `engine_api` compatibility range, factory entry point, `requested_effects`, contributed commands, and subscribed hooks. (`engine_api` is the one canonical field name for this compatibility range across the whole document, fixed 2026-07-22 -- §13.4's CLI compatibility example previously used `engram_api`; that was an inconsistent alias for the same concept, not a second field.)
*   **`bundle.integrity.json` naming (fixed 2026-07-22):** named to match §13.11's MVP trust semantics exactly -- it is a digest/hash integrity record, not a cryptographic signature. A file named `bundle.sig` would imply an authenticity guarantee the MVP does not provide. Real publisher signing, if it lands with future PKI (deferred per §13.13), gets its own separately-named artifact rather than overloading this one.
*   **Requested effects:** Filesystem, network, and process access are requests only. A bundle never self-grants an effect.
*   **Lifecycle:** A bundle proceeds through `available -> verified -> installed-disabled -> enabled`, with `enabled <-> disabled`.
    *   **Pre-install candidate states, precisely (fixed 2026-07-22, cx.deepthink finding: the prior wording had `verified` -- already defined by §13.11 as HAVING passed schema -- somehow later "failing schema" to become `incompatible`, which is self-contradictory):** a bundle candidate passes through, in order: `available` (catalog-known, no local bytes yet) -> on materializing bytes locally, either `quarantined_candidate` (digest mismatch against the trust catalog -- a pre-install sibling of the `quarantined` state below, for a candidate that never became a real installed bundle in the first place) or `rejected_invalid_manifest` (schema-invalid manifest) terminate the attempt, or -> `verified` (both integrity AND manifest-schema passed). A bundle that reaches genuine `verified` and only THEN is found to declare an `engine_api` range incompatible with the running engine becomes `incompatible` -- this is the only path to `incompatible`, and it never overlaps with a schema or integrity failure (those are `rejected_invalid_manifest`/`quarantined_candidate`, both pre-`verified`). A staged UPGRADE candidate (§13.5's transactional upgrade, below) that fails any of these pre-install gates is isolated and the upgrade attempt aborts before quiescing/migration ever starts -- the currently active bundle, its lock, and its lifecycle state are untouched.
    *   **Quarantined is an interrupt state reachable from every installed state, not just `verified` (fixed 2026-07-22, cx.deepthink finding: §13.10's own integrity-verification rebuild can quarantine an already-`enabled`, `disabled`, or `installed-disabled` bundle, which the lifecycle graph as originally drawn didn't allow for):** `quarantined` is reachable via integrity failure (§13.10 sub-kind A's rebuild path) from `installed-disabled`, `enabled`, or `disabled` alike -- not only from `verified`. Entering `quarantined` from `enabled`/`disabled` also revokes the active lock (§13.10), so a quarantined bundle is never simultaneously enabled.
    *   **Emergency quarantine of an `enabled` bundle also has to address CODE ALREADY RUNNING, not just the lock (fixed 2026-07-22, cx.deepthink finding, HIGH: revoking the lock alone only blocks future starts -- it says nothing about an invocation already executing, especially an in-process adapter's later lazy imports from now-known-tampered bytes; this is a detected security event, not a planned upgrade, so §13.5's "let it finish naturally on the old generation" behavior for planned upgrades does NOT apply here):**
        *   New invocations/imports of the bundle are blocked atomically, at the same moment the lock is revoked.
        *   An out-of-process adapter (`python_bundle` running via subprocess/PTY, the current ag/cx shape) has its process tree cancelled and terminated -- its execution is stopped, not merely denied future starts.
        *   An in-process adapter cannot have its already-loaded code "safely revoked" -- there is no way to un-load compromised bytes from a running interpreter. The `EngramApplication` process itself is marked compromised and requires a controlled process termination and restart before anything in that process is trusted again.
        *   The specific invocation that was in flight when quarantine triggered fails explicitly (not silently) and its result is REJECTED, never delivered as if it succeeded.
        *   The integrity event that triggered the quarantine is durably recorded (Evidence plane, §13.6) regardless of which of the above paths applied.
    *   **Remediation:** `quarantined` is not terminal, but repair is not a shortcut back to wherever it was quarantined from -- the bundle must pass verification again (re-earning `verified`) and then pass back through `installed-disabled` before it can be re-enabled; a repaired bundle never jumps directly from `quarantined` back to `enabled`.
    *   **Removable property:** `removable` is a property of `installed-disabled`, meaning no dependents and no active locks exist. It is not a separate lifecycle state.
    *   **Uninstall:** A removable bundle may be uninstalled.
*   **Conformance gate before enablement (fixes a real disconnect, cx.deepthink finding, 2026-07-22):** `verified` (§13.11) means digest integrity + manifest-schema validation ONLY -- it says nothing about whether the bundle's code actually behaves per contract. §13.12 calls the `adapter-conformance/v1` fixture suite "mandatory," but nothing previously required it to run before a bundle could reach `enabled`, leaving "mandatory" toothless. Fix: `installed-disabled -> enabled` additionally requires a **conformance receipt**, keyed by `bundle_digest`, `contract_version`, `engine_api_version`, `platform`, the Python ABI/runtime, and `conformance_suite_version` -- a receipt is only valid for the exact combination it was issued against. A bundle without a matching receipt cannot be enabled. An upgrade must obtain a fresh receipt for the new version and pass it before its state migration runs (see below), not after.
*   **Upgrade and rollback -- transactional (sequencing clarified 2026-07-22, made transactional per cx.deepthink finding same day):** upgrade stages the new version's files on disk side-by-side with the current one (a content-addressed, immutable path per §13.4's TOCTOU fix), but this staged copy is NOT yet part of the active `enabled` configuration. It passes through the same `available -> verified` gate as any fresh install, then obtains its own conformance receipt (above) -- both before anything else happens. The engine then quiesces NEW invocations of the bundle via an exclusive maintenance lease (no new work is admitted against it), migrates state into a new, separate `state_generation` (never mutating the current generation in place -- a shadow copy, not an in-place edit), and validates the migrated result against that new generation. Only after migration validates does the engine atomically commit a single transaction record binding both the new `bundle_version` AND the new `state_generation` together, then switch the active lock. Nothing is ever `enabled` prior to passing `verified` and obtaining a conformance receipt; "side-by-side" describes on-disk staging, not an exception to the lifecycle or conformance gates. **Rollback** restores BOTH pointers in the transaction record (bundle lock AND state generation) together, never just one. If a migration is not reversible/backward-compatible, this must be determined and stated explicitly BEFORE execution -- rollback must never be silently promised and then found unavailable after the fact.
*   **Quiescing does not mean resuming against new state (fixes a real data-corruption path, ag.deepthink finding, 2026-07-22):** "quiesce" above governs admission of NEW work only, precisely because "No hot reload" (below) means an ALREADY-RUNNING process holds an immutable `RuntimeContext` built against the OLD bundle/state generation and cannot be made to observe the new one mid-flight. Any process already using the bundle when an upgrade transaction commits keeps running against the old generation until it exits naturally on its own -- the engine does NOT pause and later resume it against the new lock, since resuming against a `state_generation` its already-loaded code and RuntimeContext were never built for is exactly the V1-code-writing-V2-state corruption path this fix closes. The maintenance lease blocks new starts, not in-flight completions. Only a process's NEXT start picks up the new lock and state generation, consistent with "No hot reload" below.
*   **The migration snapshot must be taken AFTER draining, not concurrently with it (closes a remaining lost-write race, cx.effort finding, 2026-07-22):** blocking new admissions while in-flight processes merely "finish on their own in the background" is not sufficient by itself -- a write from an old-generation process that lands AFTER the state snapshot for migration was already taken, but BEFORE that process exits, would silently vanish (new invocations only ever see the new generation; the late write was never migrated and was never in the new generation either). The maintenance lease must actively DRAIN: wait for every in-flight writer against the bundle to actually exit before the state snapshot for migration is taken, not merely stop admitting new ones while migration proceeds in parallel.
*   **Stuck-writer timeout, fully specified (closes an underspecified transition, cx.deepthink finding, 2026-07-22):** a writer that does not exit within a bounded drain timeout transitions the UPGRADE ATTEMPT (not the bundle itself -- `blocked_stuck_writer` is a state of the in-progress upgrade transaction, never one of the bundle's own §13.5 lifecycle states) to an explicit `blocked_stuck_writer` state -- no snapshot is taken and no migration proceeds from this state. The default action on timeout is ABORT the upgrade attempt; this is not a silent hang and not a silent proceed. Only a Policy-authorized administrator may request a force-stop of the stuck writer (never automatic). If force-stop is authorized, the engine terminates the writer's process tree and then explicitly CONFIRMS every writer lease against the bundle is actually released before retrying the snapshot -- if confirmation fails (a lease is still held, e.g. termination was incomplete), the attempt aborts again rather than proceeding on an unconfirmed assumption.
*   **Every abort path has the same mandatory cleanup, not just the "old generation remains active" claim (closes a gap, cx.deepthink finding, 2026-07-22):** ANY abort of an upgrade attempt -- whether from a pre-install gate failure, a stuck-writer timeout, or a failed force-stop confirmation -- must, before the attempt is considered finished: release the maintenance lease; discard or explicitly mark the candidate `state_generation` inactive (it is never left in an ambiguous half-adopted state); and durably record the aborted attempt (Evidence plane, §13.6). Restoring normal admission of new work against the old bundle/generation is conditional, not automatic -- see the `lifecycle_epoch` rule immediately below, which is precisely what makes that condition well-defined instead of a race.
*   **`lifecycle_epoch` -- serializing emergency quarantine against a concurrent upgrade (closes a real HIGH race, cx.deepthink finding, 2026-07-22):** an unconditional "abort always restores admission to the old bundle" is unsafe if that old bundle was ALSO quarantined by an emergency integrity event (above) while the upgrade attempt was in flight -- naively restoring admission could reopen access to now-known-compromised code, or race against quarantine's own lock revocation. Fix: every bundle carries a monotonic `lifecycle_epoch`, incremented on every lifecycle-state mutation. An upgrade attempt captures its starting epoch when it begins. Emergency quarantine (triggered on either the active bundle or a staged upgrade candidate) atomically increments the epoch, sets the affected target's state to `quarantined`/`quarantined_candidate`, and revokes its admission/lock -- and if an upgrade attempt is concurrently in flight against the SAME bundle, quarantine also cancels that upgrade attempt outright rather than letting it proceed unaware. The upgrade attempt checks its captured epoch before each phase transition and does a final compare-and-swap check against it at commit time; any epoch change (meaning a concurrent quarantine or other mutation happened) aborts the transaction. On abort, restoring admission to the old bundle happens ONLY if the `lifecycle_epoch` is unchanged from what the upgrade captured AND the old bundle remains eligible (i.e., was not itself quarantined out from under it) -- if quarantine intervened, admission stays closed regardless of the upgrade's own outcome. Two concrete cases: if the STAGED CANDIDATE turns out compromised, it becomes `quarantined_candidate` and the unchanged, healthy, currently-active old bundle simply resumes normal admission (the upgrade just didn't happen). If instead the ACTIVE bundle itself is found compromised mid-upgrade, it is quarantined and the in-flight migration is aborted from its state (migrating state sourced from a bundle now known to be compromised would carry that compromise forward).
*   **Effective permission:** The Policy plane grants the intersection of bundle `requested_effects`, global policy, and workspace policy. Permissions use logical scopes, never raw filesystem paths.
*   **Trust boundary:** Core-trusted built-in bundles may run in-process. Genuinely third-party bundles are deferred; when introduced, they must run out-of-process behind a brokered filesystem/network/subprocess capability host. In-process checks alone are not sufficient isolation for untrusted code.
*   **No hot reload:** Enable, disable, and upgrade changes take effect at the next process start. The immutable `RuntimeContext` must not be mutated to simulate hot reload.

### 13.5.5 ResourceRegistry Schema & Credential Handling

The Binding plane (§13.1) is realized concretely as a `ResourceRegistry` -- this subsection gives it the schema the rest of §13 assumes but never spelled out (self-audit finding, 2026-07-22: this was agreed in the debate rounds behind §13.1-13.7 and seen by all three final-review models, but dropped during doc transcription).

*   **Registry entry fields:** every shared resource declares `resource_id` (the stable ID referenced from `traceability.json`, §13.7), `scope` (`core | shared | workspace`), `owner`, `schema_ref` (a JSON Schema reference for the resource's own content -- renamed from `schema` 2026-07-22 to avoid colliding with `traceability.json`'s unrelated `schema_id` field, per cx.deepthink's naming-consistency finding), `retention` policy, `sensitivity` (`normal | secret`), and a `logical_location`. For `sensitivity: normal` entries, the registry resolves `logical_location` to a physical path. For `sensitivity: secret` entries, `logical_location` is instead an OPAQUE locator in the form `credential://<provider>/<key-id>` (fixed 2026-07-22, cx.deepthink finding) -- it never resolves to, or implies, a physical filesystem path, which keeps the field's meaning consistent within a single registry entry type instead of silently switching semantics based on sensitivity. Bundles and workspaces reference resources by `resource_id` in both cases, never by composing a physical path or a credential locator themselves.
*   **Resolution authority:** Core resolves a normal-sensitivity `logical_location` -> physical path. A bundle or workspace config that composes or hardcodes a physical path instead of referencing a `resource_id` violates Constraint 6 the same way a hardcoded env var would.
*   **`CredentialResolver`:** the dedicated backend for any registry entry with `sensitivity: secret` (e.g. a `cx` or `ag` peer's vendor API key). It resolves the entry's `credential://` locator via OS-keychain / local-secret-backend access, performs in-memory redaction, and injects the resolved value into the adapter that requested it.
*   **Secret handling rule:** secret-sensitivity resources are resolved only through `CredentialResolver`, never materialized in Shared Config JSON, telemetry, logs, or `traceability.json` output. A normal-sensitivity resource resolves through the registry's standard file/path resolution; a secret-sensitivity resource never does.
*   **Dependency, not artifact (corrected 2026-07-22, cx.deepthink finding):** the OS keychain / local-secret-backend itself is not an Engram-owned artifact and therefore is not subject to §13.1's Store/Plane classification rule at all (§13.1's rule was corrected the same day to say "every Engram-owned artifact," precisely to remove this contradiction) -- it is an external dependency the registry's `credential://` locator points at, the same way a `python_bundle` adapter depends on a peer's own external vendor API without that API becoming a store. This is distinct from the derived/cache case in §13.10, which IS Engram-owned content that just doesn't fit an existing store's contract; secret backing storage is not Engram-owned content at all.
*   **Relationship to Policy:** the registry supplies scope/ownership/sensitivity classification; the Policy plane (§13.1, §13.5) is what actually grants a bundle's `requested_effects` access to a given resource. The registry does not itself authorize access.
*   **Constraint coverage:** `scope: core | shared | workspace` is the Binding-plane mechanism for Constraint 7 -- a `shared` entry resolves into the Shared Config/Shared Data stores, making "content usable outside any single workspace" an explicit registry classification rather than an implicit convention.
*   **No cross-workspace resource_id collision (fixes a real gap, ag.deepthink finding, 2026-07-22):** §13.8's split means one `EngramHome` can serve many `WorkspaceRoot`s, so a single central registry file would let two unrelated workspaces collide on the same `resource_id`. Fix: the registry is not one monolithic file. `scope: workspace` entries are recorded in, and only ever resolved relative to, the CURRENTLY ACTIVE workspace's own Workspace-State root (`<workspace>/.ai/`) -- physically local to that workspace, per §2's existing per-workspace store boundary. `scope: core` and `scope: shared` entries live in the one registry rooted at `EngramHome`. A `resource_id` is therefore only required to be unique within its own scope's registry (global for core/shared, per-workspace for workspace), never globally across all workspaces -- identical `resource_id`s in two different workspaces' local registries never collide because nothing ever reads them together.
*   **Fully-qualified key for cross-workspace reference (revised 2026-07-22, cx.deepthink finding: the original version of this bullet put workspace-instance keys INSIDE `traceability.json`, contradicting §13.10 sub-kind B's own CI/build-time-only, read-only-with-each-Core-release nature -- a static artifact generated before any workspace exists cannot contain per-workspace runtime resource instances created after install):** `traceability.json` itself stays restricted to STATIC definitions only (schema/manifest/command/event/policy declarations known at Core build time) -- it never contains actual per-workspace resource INSTANCES. Runtime resource instances and their provenance live in each workspace's own local registry and Evidence records (§13.5.5, §13.9's provenance requirement), addressed there by their plain, scope-local `resource_id`. When a resource must be referenced unambiguously from OUTSIDE its own workspace (e.g. a cross-workspace admin view, never `traceability.json` itself), the fully-qualified form is `workspace://<workspace_id>/resource/<resource_id>` -- built by dynamically aggregating each workspace's own registry/Evidence records at query time, not by any static file. `workspace_id` here is defined in §13.8 (added same day, see below); `core`/`shared` entries, having only one registry to begin with, may keep using the bare `resource_id`. `owner` and `retention` are likewise scope-relative for workspace entries: a workspace-scoped resource is owned and retained together with that workspace and does not outlive it unless something explicitly exports it into a `core`/`shared` entry.

### 13.6 Event/Hook Model

*   **Event bus:** A versioned, observe-only-by-default event bus replaces engine special-casing of individual bundles.
*   **Event naming:** Event names are versioned, for example `peer.health.changed.v1`, `consensus.before_finalize.v1`, and `session.closed.v1`.
*   **Invocation result:** Every handler invocation returns `ok`, `skipped`, `failed`, or `timed_out`, plus a correlation ID.
*   **Durable evidence:** Every invocation outcome is durably logged in the Evidence plane regardless of outcome. Errors must never silently disappear from the plugin surface.
*   **Observe hooks:** The default hook class. Observe hooks cannot alter the primary engine action. Their failures are logged and surfaced, but do not implicitly alter the action.
*   **Gate hooks:** Rare hooks that require explicit Policy authorization. A gate hook must declare `on_failure: fail_closed | continue_with_alert`, returns structured advice only, and cannot self-grant veto authority over engine state.
*   **Evidence-unavailable policy (resolved 2026-07-22, cx.deepthink finding: a "fix-and-frozen" document cannot leave this open):**
    *   **Gate hook whose result cannot be durably recorded:** fail closed -- the gate hook's outcome is treated as `failed`, and the primary action does not proceed on the strength of unrecorded gate advice.
    *   **Observe hook whose evidence sink is unavailable:** spool the outcome locally and let the primary action continue, but mark `evidence_degraded: true` in the primary action's result envelope (§13.4) so the degradation is visible to the caller, not silent.
    *   **Local spool ALSO unavailable:** the primary action may continue only if Policy explicitly permits continuing without any evidence trail for that action class; regardless of Policy's answer, a mandatory synchronous error/alert must surface to the user -- the invocation itself is never silently discarded, even when a downstream log write is.
*   **Constraint coverage:** The `ok|skipped|failed|timed_out` + correlation-ID + durable-log model is the concrete implementation mechanism for Constraint 13 on the plugin/hook surface specifically.

### 13.7 Traceability Graph

*   **Machine-checked graph:** `traceability.json` is generated and CI-validated. It is an actual resolvable graph, not merely a process-gate principle such as the existing `traceability_map.json` reference in §10.
*   **Traceability fields:** Every graph node -- not limited to bundle manifests, but also `core`/`shared` `ResourceRegistry` entries and workspace resource DEFINITIONS (the build-known schema/kind, e.g. from §13.5.5), policy documents, the Base Template (§13.9), and the schema catalog itself -- declares a stable ID (`bundle_id`, `adapter_id`, `command_id`, `event_id`, `policy_id`, `resource_id`, or `schema_id`, as applicable to its kind) plus `docs_ref`, `source_symbol`, and `test_ref` (scope expanded 2026-07-22, cx.deepthink finding: the original wording covered manifest objects only, leaving other §13 artifact kinds untracked by the graph they're supposed to be governed by; qualified again same day per §13.5.5's later fix -- per-workspace runtime resource INSTANCES are explicitly excluded from this static graph, only build-known definitions and core/shared entries belong here).
*   **CI enforcement:** CI generates and validates the graph and rejects dangling IDs: any referenced ID must resolve to a valid target.
*   **Constraint coverage:** This is the concrete implementation mechanism for Constraints 4 and 11.

### 13.8 Bootstrap Root Discovery

The `ResourceRegistry` resolves logical resources after roots are known. Bootstrap discovery defines how the engine finds those roots without hardcoding a repository-specific path.

*   **Sanctioned exception:** Bootstrap discovery is the one explicit exception to Constraint 6, under Constraint 5's requirement to call out genuine exceptions.
*   **Two distinct roots, resolved separately (corrected 2026-07-22, cx.deepthink finding):** the original single precedence chain conflated two roots that must never be conflated -- an untrusted workspace's `.ai` directory must never be able to redirect where Core, Shared Config, Shared Data, or Capability Bundle actually live. There are two independent resolution chains:
    *   **`EngramHome`** (Core Engine / Shared Config / Shared Data / Capability Bundle roots): explicit install/shared-home override (`ENGRAM_HOME`) -> installation metadata (e.g. a bootstrap manifest written at install time) -> platform-convention default directory.
    *   **`WorkspaceRoot`** (Workspace State root only): explicit `--workspace` CLI argument -> `ENGRAM_ROOT`/workspace-scoped override -> upward marker-file or `.ai` directory walk from the current directory.
    *   **Removed a self-contradiction (2026-07-22, cx.deepthink finding):** an earlier version of this section additionally required "`ENGRAM_ROOT` and `ENGRAM_HOME` to agree" and failed otherwise -- but `ENGRAM_ROOT` resolves `WorkspaceRoot` and `ENGRAM_HOME` resolves `EngramHome`; they are two DIFFERENT roots by design (one workspace, many possible workspaces per one shared home) and normally differ, so requiring them to "agree" would reject every ordinary valid configuration. There is no cross-check between them -- each env var governs only its own chain above.
    *   Before constructing `RuntimeContext`, both resolved roots are normalized and have symlinks/reparse points resolved to their real target -- a workspace cannot use a symlink to make its own `.ai` appear to satisfy the `EngramHome` chain.
    *   **`workspace_id` (added 2026-07-22, cx.deepthink finding: §13.5.5's `workspace://<workspace_id>/...` key referenced an undefined term):** every workspace has an immutable `workspace_id` (a generated UUID), assigned once at `engram workspace init` and persisted inside that workspace's own Workspace-State root -- it identifies the workspace itself, independent of its current path, so a moved or renamed workspace directory keeps the same identity. If a workspace directory is copied wholesale (e.g. a `git clone` of a repo that includes a committed `.ai/`), the duplicate `workspace_id` is detected at next use and refused with an explicit rekey/clone workflow (assign a fresh `workspace_id` to the copy) rather than silently letting two directories claim the same identity.
    *   **`WorkspaceCatalog` and init ordering (closes a discovery gap, cx.deepthink finding, 2026-07-22):** duplicate-ID detection and any cross-workspace aggregation (§13.5.5) require actually knowing which workspaces exist -- an arbitrary copied-then-abandoned workspace directory can't be discovered by magic. `EngramHome` maintains a `WorkspaceCatalog` -- a **Binding-plane artifact living in Shared Config** (given an exact home, 2026-07-22, cx.deepthink finding: "a Shared Data record" was too loose for an authoritative ID-to-path binding), atomically updated with compare-and-set semantics: a new `workspace_id` inserts; the same ID at the same canonical path is idempotent; the same ID reachable at a DIFFERENT path is a duplicate and is refused; an ID whose last-known path is no longer reachable requires an explicit relocate/rekey confirmation rather than silent removal. Duplicate detection is scoped to one `EngramHome` -- cross-machine duplicates (the same workspace directory copied to a second machine with its own separate `EngramHome`) cannot be guaranteed detectable and are out of scope. `engram workspace init`'s precise order, made crash-safe with two-phase registration (2026-07-22, cx.deepthink finding: a plain single commit could orphan a workspace if the process crashes between the local commit and the catalog registration): resolve `WorkspaceRoot` -> validate the Base Template (§13.9) -> generate `workspace_id` in a staging area (not yet committed) -> reserve that `workspace_id` in the `WorkspaceCatalog` as `pending` -> create any template-specified registry/Evidence entries using that `workspace_id` (still staged) -> atomically commit the whole Workspace State directory into place (§13.9's containment/staging rule) -> flip the `WorkspaceCatalog` reservation from `pending` to `active`. A `pending` entry whose Workspace State commit never completed (crash recovery) is reclaimable/retriable, never silently treated as a real workspace.
    *   **First-init vs. re-init catalog flows must branch, not share one path (fixed 2026-07-22, cx.deepthink finding: applying the pending-then-active two-phase flow unconditionally to re-init would incorrectly demote an already-`active` entry back to `pending`):** the two-phase `pending -> active` protocol above applies ONLY to a genuinely first `engram workspace init` (no existing catalog entry for this workspace). Re-running init against an already-`active` workspace does NOT touch its catalog entry's `active` status at all -- the entry stays `active` throughout, unaffected by whatever the template-application transaction (§13.9) is doing to the Workspace-State content underneath it. Moving a workspace to a new path is a third, separate, explicit catalog-relocate flow (not implied by either init path), which must complete before the entry's recorded path changes.
    *   **Pending-record recovery rule (closes a crash-recovery gap, cx.deepthink finding, 2026-07-22):** a crash after the Workspace State commit succeeds but before the catalog flip to `active` would strand a fully-valid, on-disk workspace as merely `pending` forever without an explicit reconciliation rule. Fix: every `pending` record additionally carries an `operation_id`, the canonical target path, and a lease expiry. On the next `init`/`open` attempt against that path: if a committed local `workspace_id` is found on disk that matches the pending record, CAS-promote it straight to `active` (the crash happened after the real commit, so this simply finishes the interrupted flip); if no committed local state is found and the lease has expired, the reservation is reclaimed (available for a fresh attempt); if there's a mismatch, or the lease is still live (another process may be actively working on it), the attempt fails visibly and requires manual repair rather than guessing. `pending` entries are visible in catalog listings/reporting but are excluded from ordinary cross-workspace aggregation queries (§13.5.5) until `active`.
    *   **First-init bootstrap ordering (closes a chicken-and-egg gap, cx.deepthink finding, 2026-07-22):** a brand-new workspace has no `.ai` directory yet, so the ordinary upward marker-file walk (above) has nothing to find on the very first `engram workspace init` -- "resolve `WorkspaceRoot`" cannot rely on a marker that doesn't exist until this command creates it. `engram workspace init` therefore resolves `WorkspaceRoot` differently from every other command: it REQUIRES an explicit `--workspace <path>` argument (or, if omitted, treats the current directory as the target for this command specifically) rather than attempting the upward-walk discovery that only works for commands run AFTER a workspace already exists.
*   **Failure behavior:** Unknown or unresolvable roots fail closed with an explicit error. Silent fallback is prohibited.
*   **Recommended refinement:** After bootstrap resolution, logical resources may use URI-style names such as `core://`, `shared-config://`, `shared-data://`, `bundle://`, and `workspace://`, resolved by the `ResourceRegistry`. This URI form is recommended but not mandatory.

### 13.9 Base Template — Full Specification

The Base Template is a first-class, versioned artifact for workspace initialization.

*   **Artifact identity:** A template is identified as `workspace-template@<version>`.
*   **Location and discovery:** It lives in Shared Config and is referenced through a stable `resource_id` in the `ResourceRegistry`; it is not an ad hoc file.
*   **Application command:** Templates are applied through `engram workspace init --template <id>@<version>`.
*   **Required behavior:**
    *   **Dry-run:** Preview without modifying disk.
    *   **Idempotency:** Re-running does not destroy existing state.
    *   **Conflict handling:** Preserve existing files and report conflicts, consistent with §3 `on_existing: preserve` and `on_conflict: report`.
    *   **Schema validation:** Validate the template before application.
    *   **Provenance:** Record the applied template ID and version in the workspace's Evidence-plane record.
    *   **Containment (added 2026-07-22, cx.deepthink finding: calling this "workspace initialization" does not by itself satisfy Constraint 9):** every destination the template generates or writes to MUST resolve beneath the workspace's own dedicated Workspace-State root (`<workspace>/.ai/`, per §2) as its FINAL LOGICAL DESTINATION (clarified 2026-07-22, cx.deepthink finding: "every destination" read too literally would conflict with the staging mechanism itself, since a staged copy necessarily exists somewhere else on disk before being committed into place -- containment governs where content ends up, not the intermediate mechanics of getting it there). The applier rejects, before writing anything: absolute destination paths, `..` traversal segments, and destinations that resolve outside the root after following symlinks/junctions/reparse points. A template entry that targets a path outside the allowed root, or an existing file outside it, is a hard error, not a warning. Dry-run and real application share the exact same path-normalization/resolution code path, so a dry-run preview cannot legitimately claim safety that the real run doesn't also guarantee.
    *   **Staging mechanics, first-init vs. re-init (fully specified 2026-07-22, cx.deepthink finding):** a secured sibling staging directory under the workspace's `WorkspaceRoot` (never itself inside the not-yet-committed `.ai/`) holds all generated content until every entry validates against containment. On a genuinely FIRST init (no prior `.ai/` exists), commit is a simple atomic rename of the staged directory into place. On a RE-init against an already-existing `.ai/` (idempotent re-application, e.g. a template version bump), a plain rename-swap would destroy existing workspace state and violate the `on_existing: preserve`/`on_conflict: report` rule, and an unspecified "merge" is not inherently atomic across multiple files either (fixed 2026-07-22, cx.deepthink finding: naming an actual mechanism, not just calling it "transactional"). Re-init instead uses the SAME immutable-generation pattern already established for bundle upgrades (§13.5's `state_generation`): the merge (staged entries compared against existing paths, applied per the preserve/report rule) is computed into a new, complete Workspace-State generation directory, and only the final step atomically replaces a single `current_generation` pointer to make it active -- a crash at any point before that pointer swap leaves the previous generation fully intact and active, never a partially-merged `.ai/`. Either way, a mid-template failure never leaves a partially-applied, partially-contained workspace. Complete §13.9 preflight validation (schema validation AND a full containment dry-check of every entry, not schema alone) finishes BEFORE §13.8's `WorkspaceCatalog` reservation is made -- a template that would fail containment never gets to reserve a `pending` `workspace_id` slot in the first place.
    *   **Scope exemption for registry entries (fixes a real conflict, ag.deepthink finding, 2026-07-22):** the containment rule above governs FILESYSTEM DESTINATIONS the template writes bytes to. A template entry that provisions a `ResourceRegistry` entry (§13.5.5) -- including a `sensitivity: secret` entry, whose `logical_location` is an opaque `credential://<provider>/<key-id>` locator, not a filesystem path at all -- is a registry WRITE, not a file write, and is therefore never evaluated against the path-containment resolver in the first place. Path containment and registry-entry provisioning are validated by separate, independent rules; a `credential://` locator must never be parsed as a path, absolute or otherwise.
    *   **The registry-write exemption is scope-bounded, not blanket (closes an overbroad exemption, cx.effort finding, 2026-07-22):** exempting registry writes from PATH containment does not mean a workspace-init template may provision ANY registry entry unchecked. `engram workspace init` may create ONLY `scope: workspace` entries, and only within the active workspace's own registry (§13.5.5) -- it can never create `scope: core` or `scope: shared` entries, which require a separate install/admin workflow with its own Policy authorization, outside template application entirely. A template also may never write `sensitivity: secret` material directly (a literal secret value) into any registry entry -- it may at most reference a `credential://` provider/key-id pair that is itself validated against schema and Policy, never carry the secret's actual value.
*   **Traceability:** Workspace origin remains discoverable through the template resource ID and recorded provenance.
*   **Constraint coverage:** This is the concrete implementation mechanism for Constraint 8, and the containment rule above is what makes it actually satisfy Constraint 9 rather than merely asserting it.

### 13.10 Derived Artifacts: the MECE Gap in the 5-Store Model

`bundle-index.json` and `traceability.json` are generated, non-authoritative artifacts. Only `bundle-index.json` fails to fit any ordinary store contract and needs a runtime-cache carve-out; `traceability.json` fits Core Engine's own contract (immutable, updater-owned) cleanly once correctly classified there (title and framing corrected 2026-07-22, cx.deepthink finding: calling this section "Derived/Cache Artifacts" and saying up front that NEITHER fits an ordinary store contract became stale the moment sub-kind B was reclassified into Core Engine below -- only sub-kind A is actually the cache/MECE-gap case). They are covered together here because both are DERIVED (neither is a primary source of truth) and that shared classification is worth documenting once, but they are NOT regenerated the same way, at the same time, or even in the same store -- treating them as one interchangeable "cache" was itself the original category error (fixed 2026-07-22, ag.deepthink finding), so this section covers two distinct sub-kinds under one shared DERIVED classification, only one of which is actually a cache.

*   **Classification:** Derived artifacts are an explicitly documented pattern (non-authoritative, atomically replaced rather than appended) applied across TWO different store homes, not a sixth store (corrected 2026-07-22, cx.effort finding: an earlier version of this section put both sub-kinds in Shared Data, which contradicted sub-kind B's own "ships with each Core release" description below -- Store answers "where," and the two sub-kinds do not share a "where"). The two sub-kinds' RECONSTRUCTION stories are deliberately different, not a shared "safe to delete at any time" claim (precision fix, 2026-07-22, cx.deepthink finding): sub-kind A is reconstructible locally, on the SAME machine, from installed manifests + the trust catalog, via `engram plugin verify --all`. Sub-kind B is NOT locally reconstructible at all on an ordinary runtime machine (it needs the full Core source tree, which runtime machines don't have) -- a missing/corrupted `traceability.json` is recovered only by re-obtaining it from the Core distribution (a Core repair/reinstall), never by any runtime command. "Derived, non-authoritative" is the shared classification; "how you get it back" is not.
*   **Sub-kind A -- `bundle-index.json` (runtime-regenerable cache, home: Shared Data):** rebuilt at runtime, on the installed machine. Checking only the installed manifest's digest is not sufficient to authenticate the bundle CODE itself (tightened 2026-07-22, cx.deepthink finding on top of cx.effort's original fix): the Core-release trust catalog (§13.11) binds `(bundle_id, version, manifest_digest, content_digest)` as one unit, and a rebuild must recompute BOTH the manifest digest and the content digest from the installed bytes and validate the full tuple against the catalog -- a matching manifest with tampered code content must still fail. A bundle whose digests don't match the catalog is not silently excluded from the rebuilt index (which would look identical to "never installed" and hide that something is actually wrong). The index is a REFLECTION of lifecycle state, not the authority for it (fixed 2026-07-22, cx.deepthink finding: the prior wording let the index itself "record" a status disconnected from §13.5's real lifecycle state machine): on a digest mismatch, `plugin verify --all` first atomically transitions the bundle's own authoritative lifecycle state (§13.5) to `quarantined` and revokes its active lock, THEN the rebuilt index publishes a record reflecting that already-transitioned state (`lifecycle_state: quarantined`, `enabled: false`, `reason: <mismatch detail>`) -- the index never invents its own separate status. Command/capability metadata for a quarantined entry is NOT copied from the mismatched (untrusted) manifest into the index; only the identity and quarantine reason are published. **`quarantined` is specifically for tampered/mismatched content, not merely absent content (fixed 2026-07-22, cx.deepthink finding: conflating these would reintroduce the exact ambiguity this fix was meant to close):** a bundle the trust catalog authorizes but that was never actually installed is `available` (per §13.5's normal lifecycle, not an error at all); a bundle with an authoritative install record whose backing bytes are missing (as opposed to present-but-tampered) is `quarantined` with reason `missing_content` and its lock is revoked, same as a digest mismatch; a bundle referenced by neither the trust catalog nor any install record simply has no index entry at all. Its regeneration is DELIBERATELY NOT automatic/lazy-on-miss despite being cheap to rebuild -- a missing/stale index fails closed (§13.4) rather than silently regenerating, specifically because this index is trust-relevant (it backs §13.4's TOCTOU integrity checks) and silently rebuilding trust state on every miss could mask real tampering or corruption instead of surfacing it. Regeneration requires the explicit `engram plugin verify --all` trigger.
*   **Sub-kind B -- `traceability.json` (CI/build-time artifact, home: Core Engine, NOT Shared Data):** requires `source_symbol`/`test_ref` references into the full Core Engine source tree and test suite (§13.7) -- inputs that do not exist on an ordinary installed/runtime machine, which typically has installed bundles and manifests but not the Core Engine's own source checkout. It is therefore generated once, during CI/the build-and-release pipeline that DOES have the full source tree, and ships as a read-only artifact WITH each Core release rather than being rebuilt on demand at runtime the way `bundle-index.json` is -- because it ships versioned with each Core release and is never locally regenerated, it belongs to the Core Engine store (immutable, updater-owned), not Shared Data. `engram plugin verify --all` (sub-kind A's regeneration path) does not, and cannot, rebuild it.
*   **Store contract:** Shared Data's normal append-only Evidence records, Shared Data's sub-kind-A derived cache, and Core Engine's sub-kind-B shipped artifact are three distinct contracts that must not be conflated with each other.
*   **Constraint coverage:** This classification is what keeps `bundle-index.json`'s cheap-metadata/staged-validation model (§13.4) satisfying Constraint 14 without also violating Constraint 2's MECE requirement.

### 13.11 "Verified" State: Explicit MVP Trust Semantics

*   **MVP meaning:** In MVP scope, `verified` means integrity plus manifest-schema validation only. It does not mean authenticity, publisher identity, or authorship verification.
*   **Built-in bundles:** Built-in bundles are distribution-owned and digest-pinned to the Core release.
*   **Trust limitation:** Without publisher key infrastructure, a hash proves post-distribution integrity but does not establish an independent third-party trust anchor.
*   **Forward compatibility:** The `verified` state name remains forward-compatible with future real signing and PKI, but the MVP must not claim guarantees it does not provide.
*   **Independent versioning vs. the trust anchor (resolved 2026-07-22, cx.deepthink finding):** §13.1/§13.5 describe Capability Bundles as independently versioned, but if built-in bundle digests are pinned to a Core release (as this section requires for MVP), a trusted digest change still requires a new Core release -- updates are not actually independently DISTRIBUTABLE, only independently VERSION-NUMBERED, which is a real tension worth stating rather than leaving implicit. Resolved rule: in MVP, bundles carry independent version numbers (for clarity and future-proofing), but the trust catalog that says which digest is currently trusted remains Core-release-coupled -- a new trusted bundle version ships as part of a new Core release, not as a standalone push. This is the option that best matches the stated MVP scope (no independent bundle distribution channel exists yet); true independent distribution is a later capability, gated on the same PKI work already deferred in §13.13.

### 13.12 Protocol Enforcement: Beyond `isinstance`

*   **Fast shape validation:** `isinstance(adapter, PeerAdapter)` rejects obviously wrong objects at load time.
*   **Contract version:** Every adapter declares a `contract_version`.
*   **Actual enforcement:** `adapter-conformance/v1` is mandatory. It is an executable universal fixture suite, not optional documentation.
*   **Coverage:** Both `python_bundle` and `generic_cli` adapter kinds must pass conformance fixtures covering command construction, output parsing, timeout and error behavior, capability declarations, and traceability-ID presence.
*   **Guarantee boundary:** The conformance suite is the actual contract enforcement mechanism; runtime Protocol checks are only an early shape screen.

### 13.13 MVP-Now vs. Explicitly-Deferred

*   **Worth designing/building now:**
    *   unified `engram` CLI and command-registry abstraction;
    *   `PeerAdapter` Protocol contract;
    *   built-in Capability Bundles for cc/ag/cx represented as real manifests;
    *   `ResourceRegistry` with logical scope and sensitivity;
    *   versioned observe-only event envelopes;
    *   explicit CLI major-version incompatibility behavior;
    *   Bootstrap Root Discovery (§13.8);
    *   Base Template artifact and initialization behavior (§13.9);
    *   Bundle Registry Index generation, atomic refresh, and consumption (§13.4/§13.10) -- load-bearing for the promised lazy help/completion/command discovery to function at all, not an optional optimization;
    *   `adapter-conformance/v1` fixture runner plus fixtures for the built-in `python_bundle` adapters (§13.12) -- `generic_cli` conformance cases become required only once that deferred adapter kind is actually implemented.
*   **Explicitly deferred:**
    *   third-party bundle downloads, marketplace, publisher PKI, and remote registries;
    *   dynamic untrusted Python loading and the required out-of-process broker/sandbox;
    *   arbitrary root-level plugin commands outside extension namespaces;
    *   mutating or veto-capable lifecycle hooks;
    *   per-workspace bundle version pinning and hot reload;
    *   `generic_cli` / `DeclarativeCliAdapter` implementation.

### 13.14 Additional Recorded Debt

*   **Windows atomic replacement:** Windows atomic replacement of `bundle-index.json` and the upgrade lock switch may encounter NTFS sharing violations under concurrent readers. The eventual implementation requires documented retry and backoff behavior; "atomic" alone is not a sufficient specification.
*   **Zero-code status:** Constraint 12 is aspirational in MVP. Python adapters remain the norm, while the actual zero-code path, `DeclarativeCliAdapter`, is deferred under §13.3 and §13.13. This is an explicit, defensible exception under Constraint 5 and must not be presented as already achieved.

### 13.15 Governed Mutation Protocol (cross-cutting mechanism, added 2026-07-22)

> **Why this exists:** a meta-level review (5-Whys + MECE + feedback-loop pass, cx.deepthink, 2026-07-22), run AFTER the 14-round concurrency audit had already made every individual mechanism internally coherent, asked a different question: is §13 organized at the right level of abstraction? It found that §13.5's bundle lifecycle (CAS-checked transitions + `lifecycle_epoch` + durable audit), §13.5.5's `ResourceRegistry` mutation, and §13.8's `WorkspaceCatalog` (CAS semantics + `pending`/`active` + durable provenance) had independently reinvented the SAME underlying transaction pattern three separate times across three separate debate rounds -- a real violation of Constraint 5 ("specific instances sharing the same pattern... should generalize further") at the cross-cutting MECHANISM level, even though each domain's own state machine remains genuinely distinct (rejected as over-generalization: forcing bundles/workspaces/registry-entries/hook-invocations into one universal FSM would erase real differences in consistency requirements, consumers, and failure semantics -- see §12's own warning against schema bloat without a real consumer).

*   **The shared contract:** any authoritative mutation across bundles, `WorkspaceCatalog` entries, or mutable `ResourceRegistry` entries is expressed as a `MutationRequest` -> `TransitionReceipt` pair:
    ```text
    MutationRequest:
      subject_kind, subject_id, subject_scope, operation,
      expected_revision, idempotency_key, correlation_id,
      actor, policy_revision, payload

    TransitionReceipt:
      status, previous_revision, new_revision, resulting_state,
      correlation_id, evidence_ref, failure_code
    ```
*   **Implementation contract (six steps, always in this order):** (1) authorize through Policy; (2) validate domain-specific invariants (the bundle/workspace/registry-entry's OWN state machine rules -- §13.5/§13.5.5/§13.8 keep authoring these, they are not replaced); (3) CAS against `expected_revision` (this is the generalized form of `lifecycle_epoch` in §13.5 and the CAS semantics already specified in §13.8's `WorkspaceCatalog`); (4) commit authoritative state plus a durable outbox receipt in one step; (5) publish that receipt into the Evidence plane; (6) return only after the durable receipt exists, never before.
*   **Domain state machines are preserved, not replaced:** §13.5's bundle lifecycle states (`available`/`verified`/`quarantined`/etc.), §13.5.5's registry entry fields, and §13.8's `WorkspaceCatalog` states (`pending`/`active`) are UNCHANGED by this section -- they now explicitly conform to and are implemented in terms of this shared transaction machinery, rather than each having separately reinvented CAS-checking, receipt semantics, and audit-commit ordering.
*   **Emergency quarantine's authorization step is PRE-authorized, not discretionary (fixes a real fit problem, cx.deepthink finding, HIGH, 2026-07-22):** step (1) "authorize through Policy" cannot mean waiting on discretionary/human approval for an integrity-driven quarantine -- that would dangerously delay a security response. Effective Policy must PRE-authorize the `integrity_failure -> quarantine` transition as a standing, non-weakenable Core safety invariant (lower policy layers may make it stricter, never disable it). Step (1) for this specific transition is then a synchronous evaluation against the already-resolved, immutable Policy snapshot -- not a wait. If the policy-evaluation infrastructure itself is unavailable, quarantine still fails closed (proceeds anyway rather than blocking a security response on infrastructure availability) and separately records that policy evaluation was degraded.
*   **Step 4 needs a richer plan than "state plus outbox receipt" for effects beyond pure state change (fixes a real gap, cx.deepthink finding, 2026-07-22):** quarantine doesn't just change state -- it also revokes admission, cancels an in-flight upgrade, and (per §13.5's emergency-quarantine bullet) may terminate a process tree. Step (4) is generalized to commit a `MutationPlan`: `state_delta` + `fence_or_lock_delta` (the durable admission fence/lock record) + `effect_intents` (e.g. "terminate this process tree") + the `outbox_receipt` -- the state, epoch, and fence/lock record commit atomically together; effects like process termination are POST-COMMIT, driven from the durable outbox after the atomic commit succeeds (never before, so a crash before commit never leaves an orphaned effect with no matching record). The `TransitionReceipt`'s `status` must be able to express `committed_enforcement_pending` (the authoritative record is safely committed, but a required effect like process termination hasn't been confirmed yet) distinctly from `completed` (both the record AND its required effects are confirmed) -- emergency quarantine specifically must never report `completed` before its required enforcement effect is confirmed.
*   **The protocol's atomicity boundary is per-record, not distributed (clarifies a real ambiguity, cx.deepthink finding, MEDIUM, 2026-07-22):** workspace initialization (§13.8) is not one atomic `MutationRequest` -- it is a SAGA of several: `WorkspaceCatalog` absent -> `pending` is one `MutationRequest`/receipt, the filesystem Workspace-State commit is a separate step outside this protocol's atomicity boundary entirely, and `pending` -> `active` is a third `MutationRequest`/receipt -- all three sharing one `operation_id`/`correlation_id` so they're traceable as one logical operation. §13.15 guarantees atomicity PER AUTHORITATIVE RECORD (one CAS-checked state transition, safely committed), never distributed atomicity spanning multiple stores or the filesystem at once -- §13.8's lease-and-reconciliation rules remain the real cross-step saga-recovery mechanism, not something §13.15 replaces. The generic `resulting_state` field does not hardcode per-domain fields; it carries or references a domain-typed `domain_result` -- for the `WorkspaceCatalog`'s `pending` transition specifically, that means `operation_id`, `canonical_path`, `lease_expires_at`, and `catalog_status`. The authoritative catalog record itself, not the receipt, remains the actual source used for crash recovery (per §13.8's own reconciliation rule).
*   **`AuditedOperation` -- the lighter envelope for non-lifecycle invocations:** event/hook invocations (§13.6) and adapter command invocations are attempts, not resumable stateful entities, and do NOT inherit the full CAS/revision machinery above. They use a lighter envelope: operation/attempt ID, correlation ID, subject reference, status, timing, and an evidence reference -- this is the formalization of §13.6's existing `ok|skipped|failed|timed_out` + correlation-ID model, unchanged in substance, just named as the general pattern it already was.
*   **Policy bootstrap ordering, made explicit (closes a real ordering gap, cx.deepthink finding, MEDIUM, 2026-07-22):** `MutationRequest.policy_revision` presupposes a resolved Policy revision exists, which (per §13.2) lives in the immutable `RuntimeContext` -- the explicit ordering is: resolve `EngramHome` (§13.8) -> load/validate the Core baseline + global Policy -> construct `RuntimeContext` (§13.2) -> resolve/create `WorkspaceScope` -> only THEN can any `MutationRequest` be issued. For the FIRST workspace initialization specifically, no workspace-level policy exists yet, so authorization uses ONLY Core/global Policy -- a template-provided workspace policy can never authorize its own creation (that would be circular). The initial Engram installation itself is the one true installer/root-of-trust bootstrap exception, trusted axiomatically since nothing pre-exists to authorize it; every LATER policy change is authorized by whatever policy revision is currently effective at that time.
*   **Constraint coverage:** this section is the concrete mechanism that makes Constraint 5's "generalize repeated patterns" hold at the cross-cutting mechanism level, without forcing Constraint 2's MECE domain separation to collapse.

### 13.16 Evidence Feedback Loop (added 2026-07-22)

> **Why this exists:** the same meta-level review found that most of §13's individual safety loops already close LOCALLY and IMMEDIATELY (a `traceability.json` dangling reference gets rejected by CI; a conformance failure blocks enablement; an integrity failure triggers quarantine-then-remediation; a stale `WorkspaceCatalog` entry surfaces as a diagnostic) -- but the accumulated Evidence-plane data these loops generate is otherwise WRITE-ONLY. Repeated quarantines, hook timeouts, conformance failures, and peer routing outcomes/costs never aggregate into anything that improves the system's own future decisions. Given this project's actual goal (a genuinely adaptive multi-peer system, not just a correctly-implemented static one), that one-way flow is a real gap, not an acceptable simplification.

*   **The loop:** `Evidence -> derived OperationalProfile -> declarative assessment rules -> Recommendation -> Policy authorization -> governed action -> new Evidence -> outcome evaluation` (which feeds back into the next `OperationalProfile`, closing the loop).
*   **`OperationalProfile`:** a non-authoritative, fully rebuildable Shared Data projection derived from accumulated Evidence -- classified under §13.10's derived-artifact pattern, generalizing that section's runtime-derived-cache category beyond `bundle-index.json` alone (§13.10 sub-kind A) to include Evidence-derived operational projections as a further instance of the same "regenerable, non-authoritative, atomically replaced" contract.
*   **Concrete consumers (illustrative, not exhaustive):** repeated hook timeouts for one bundle -> recommend circuit-breaking or disablement; repeated conformance failures for one `(contract_version, engine_api_version, platform)` tuple -> flag a compatibility regression; quarantine recurrence for the same bundle -> block automatic re-enable, require administrator review; stale `WorkspaceCatalog` entries persisting past a threshold -> recommend relocation or retirement, NEVER auto-delete; peer quality/cost/latency outcomes -> update measured-capability projections and canary allocation weighting.
*   **Authorization boundary (critical, not optional):** automatic ACTIONS taken from this loop are limited to pre-authorized, reversible responses only. Policy changes, deletion, privilege expansion, and permanent routing exclusion always remain RECOMMENDATIONS requiring explicit Policy/administrator authorization -- this loop proposes, it does not by itself get to decide, matching the same advisory-not-autonomous posture already established elsewhere (e.g. the Final Arbiter pattern that fires only on dissent/high-risk rather than routing every decision automatically).
*   **Selection-bias guard:** routing/outcome Evidence must record the full candidate set considered and the selection reason (including canary/exploration context), not just the outcome of whichever peer was actually picked -- otherwise the loop learns only from its own past choices and merely reinforces whatever was already being selected, never genuinely re-evaluating alternatives.
*   **`Recommendation` is itself a governed entity, expressed through §13.15 (closes a real gap, cx.deepthink finding, 2026-07-22):** leaving the recommendation's own lifecycle implicit risks duplicate actions or acting on a stale profile. A `Recommendation` proceeds through `proposed -> approved | rejected | expired`, and a separately `approved -> executing -> evaluated` -- itself a `MutationRequest`/`TransitionReceipt`-governed subject per §13.15, not a special case outside that protocol. It carries `recommendation_id`, `operational_profile_revision`, `policy_revision`, an `expected_revision` for CAS-checking, and correlation links. Before execution, the engine CAS-checks that the recommendation is STILL `approved` (not stale) and re-evaluates if the `OperationalProfile` or Policy revision it was based on has since changed. The eventual governed action's `TransitionReceipt` links back to the `recommendation_id`; the outcome evaluation links to that action's receipt -- forming one traceable chain from Evidence through Recommendation through action through outcome, rather than a Recommendation being actioned by some unspecified separate path.
*   **Explicitly NOT part of this loop:** `traceability.json` (§13.7/§13.10 sub-kind B) remains a static CI-time assurance artifact, not a runtime-learning input -- conflating "verify the build is internally consistent" with "learn from operational history" would be the same category error §13.10 already corrected once (sub-kind A vs. B).
*   **This is the abstraction ceiling (2026-07-22, cx.deepthink's own honest assessment after this round's fixes):** the remaining higher-order description of §13.15+§13.16 together is simply a governed closed-loop control system (Policy authorizes -> `GovernedMutation` changes state -> `AuditedOperation`/Evidence observes outcomes -> this feedback loop proposes improvements -> Policy authorizes again). Turning THAT into yet another named universal runtime abstraction would add naming and indirection with no new consumer -- this is the point where further "higher-level" searching would itself become the over-engineering §12 warns against. §13.15 and §13.16 deliberately remain two separate sections, not merged into one: §13.15 is the authoritative command path, §13.16 is the observational/advisory path, and merging them would risk letting evidence-derived recommendations authorize themselves. Further work from here moves to schemas, failure injection, and TDD (Phase 3), not another architectural layer.

## 14. Host Distribution, Packaging & User Lifecycle (added 2026-07-22, converged 2026-07-23)

> **Why this exists:** a user-scenario lifecycle audit (install/update/use/delete, cx.deepthink, 2026-07-22) asked whether §13 covers the FULL user lifecycle as a MECE set, and found it does not: §13 covers runtime operation, workspace initialization, and Capability Bundle lifecycle well, but has no host-level lifecycle for Engram itself. Nothing in §13 specifies how `EngramHome` gets created in the first place (§13.8's bootstrap discovery only locates an ALREADY-EXISTING `EngramHome`), how the Core Engine itself updates (distinct from a bundle upgrade -- Core owns the verifier, trust catalog, schemas, and built-in bundle pins that bundle upgrades are validated against), what happens to already-initialized workspaces when Core updates, or how to uninstall Engram (with a real distinction between removing the program vs. purging user data/credentials).
> **Review status:** 4 further rounds of cx.deepthink audit followed the initial draft -- 8 findings (3 HIGH), then 6 findings (2 HIGH), then a full end-to-end trace of both a combined Core-update sequence and an uninstall-then-`ReattachInstallTransaction` sequence, which returned an explicit **CONVERGED** verdict: "the structure survived the focused end-to-end traces, no new HIGH architectural flaw appeared, and the remaining questions are mechanically testable state/schema details." Remaining work (JSON schemas, state tables, fault-injection tests) is recorded under Phase 3 Next Steps below, not left as open architectural questions.

*   **Three separate lifecycles, not one (MECE correction):** the clean partition is **Host Distribution Lifecycle** (Engram Core, `EngramHome`, the trust catalog, repair/update/uninstall of Engram itself), **Capability Lifecycle** (§13.5's bundles, plus external vendor CLI dependencies), and **Workspace Lifecycle** (create, open, migrate, relocate, retire, export, destroy). Once Policy exists, all three reuse §13.15's Governed Mutation Protocol -- but, per round-2 fixes below, several host-level operations genuinely cannot, and must not pretend to. Forcing them into one lifecycle would repeat the exact over-generalization mistake §13.15/§13.16 already rejected.
*   **Bootstrap authority -- the first installation is NOT a Governed Mutation (fixes a real gap, cx.deepthink finding, HIGH, 2026-07-22):** §13.15's Policy authorization presupposes `RuntimeContext` already exists, which presupposes Policy is already loaded, which presupposes `EngramHome` already exists -- so the FULL first transition (`absent -> staged -> verified -> installed -> active`, below) must stay entirely OUTSIDE the Governed Mutation Protocol; it cannot switch into §13.15 partway through. This first install is a `BootstrapInstallTransaction`, trusted axiomatically relative to Engram's own future Policy -- but it is still AUTHENTICATED: the external bootstrapper validates the release manifest and publisher signature against an installer-embedded or OS-level trust anchor, never against the trust catalog that this very transaction is about to install (§13.11's digest-only bundle verification is explicitly NOT sufficient authenticity for the Core installer itself -- that mechanism was designed to verify bundles trusted BY an already-installed Core, not to bootstrap the Core's own trust). The FIRST `current_record` CAS needs an explicit absent sentinel, not an ordinary prior revision (fixes an overclaim, cx.deepthink finding, MEDIUM, 2026-07-22): bootstrap pointer creation is `CAS(current_record, expected=ABSENT, desired=record_revision_1)` -- an atomic create-if-absent primitive; if the pointer or an existing `engram_home_id` appears concurrently, bootstrap fails rather than silently overwriting it. The concrete mechanism: build the complete release unit, the first `InstallationRecord` generation, and the `current_record` pointer inside a SIBLING staging directory; verify everything; atomically publish that staging directory into the previously-absent `EngramHome` path in one step (only this home-publication step is genuinely atomic). PATH registration and the external installer-owned journal (below) are saga effects with their own idempotent recovery, not part of that one atomic step -- the earlier phrasing ("atomically installs the release unit... and writes an installer-owned journal") overclaimed filesystem atomicity spanning `EngramHome`, program files, PATH configuration, and an external journal all at once. It writes an `InitialInstallationReceipt` to that installer-owned journal, which the first successful `EngramApplication` start then imports into Evidence (§13.6) as the first entry a Governed Mutation history has to work with. (A retained `EngramHome` with no Core present is explicitly NOT this `expected=ABSENT` bootstrap case -- see the separate reattachment transaction under the uninstall-boundary fix below.) **A second bootstrap-adjacent boundary:** repair or uninstall when Core or Policy itself is CORRUPT cannot use §13.15 either, even though Policy files nominally still exist on disk -- define a `break-glass` route, distinct from normal Policy-authorized repair/uninstall below: the external bootstrapper authenticates the OS user/administrator plus signed recovery media, records an external recovery receipt, and never claims Policy authorization occurred. "Repair from the installation's own verified source" is unsafe precisely when that source or its trust catalog is what's damaged -- genuine recovery uses an independently signed archive, a package-manager cache, or the original installer, validated by the bootstrapper's OWN external trust anchor, never by asking the possibly-compromised installation to vouch for itself.
*   **`InstallationRecord` as immutable generations, not a record that's both immutable and mutated in place (fixes a real contradiction, cx.deepthink finding, MEDIUM, 2026-07-22):** an "immutable record" cannot itself be the thing whose `active_release`/`previous_release` fields get updated -- each host mutation instead writes a NEW immutable generation (carrying `installation_id`, `installation_revision`, `host_lifecycle_epoch`, `active_release`, `previous_release`, `rollback_target_record_revision`, `shared_state_generation`, `core_schema_version`, `runtime_version`, `trust_catalog_digest`, `builtin_bundle_set_digest`, `traceability_digest`, plus the channel-guarantee fields defined in §14.1) and CAS-switches a `current_record` pointer to it -- the same generation+pointer-swap pattern used everywhere else in §13/§14. The old generation remains the actual rollback/audit source.
*   **`aborted` is legal only BEFORE the activation CAS -- state and attempt are two different axes, not one shared vocabulary (tightened 2026-07-22, cx.deepthink finding, HIGH: the round-2 wording still let a host-state transition and an attempt-outcome word collide):** the authoritative `HostState` remains `active` continuously until an uninstall actually commits -- there is no `active -> updating` host-state transition at all. Separately, a `HostUpdateAttempt` moves through `staged -> preflighted -> quiescing -> migrating -> committing -> completed | aborted`. **Before** the `current_record` CAS succeeds, the attempt may `abort`: cleanup releases the admission fence and host-update lease, discards the staged release and shadow `shared_state_generation`, leaves `current_record` completely unchanged, restores admission to that unchanged tuple, and writes an `aborted` attempt receipt. **After** the `current_record` CAS succeeds, the update is COMMITTED -- a subsequent health or enforcement failure is NOT an abort and must never silently restore the old tuple; it requires a separate, explicitly GOVERNED rollback transition (see the rollback-linkage fix below) that writes a brand-new `InstallationRecord` generation and increments `host_lifecycle_epoch` forward, never backward. A failed Evidence publication after commit uses §13.15's own durable-outbox recovery path -- it does not retroactively turn a committed update into an abort. The exact same attempt-vs-state separation applies to repair and uninstall: `repairing` and `uninstalling` are attempt states (or admission modes) layered on top of the authoritative host state, never substitutes for it.
*   **Rollback needs an exact record reference, not just the display field `previous_release` (fixes a real gap, cx.deepthink finding, MEDIUM, 2026-07-22):** `previous_release` alone doesn't identify which `shared_state_generation` paired with it, especially after repair or other host mutations have created additional record generations without changing the active Core -- "the old generation remains the rollback source" doesn't say WHICH old generation once more than one exists. Fix: `InstallationRecord` carries a `rollback_target_record_revision` field pointing at one specific prior immutable generation, which supplies the COMPLETE prior tuple (Core release, shared-state generation, trust catalog, built-in bundle set, schemas, runtime, and all relevant digests) in one reference. On a GOVERNED rollback (per the committed-vs-aborted distinction above -- this only applies post-commit), the engine does NOT simply repoint `current_record` backward to an old generation (that would make `host_lifecycle_epoch` go backward, breaking its monotonic guarantee) -- instead it creates a brand-NEW record generation whose active tuple is copied FROM the rollback target, then CAS-activates that new generation forward. `previous_release` remains a convenient display field; `rollback_target_record_revision` is the actual authoritative link a rollback follows.
*   **Core update requires installation-wide quiescence, not just an atomic pointer (fixes a real gap, cx.deepthink finding, HIGH, 2026-07-22):** an atomic `active_release` pointer switch alone is insufficient, because OLD and NEW Core processes can both access the SAME mutable `EngramHome` state (Shared Config, global Policy, `WorkspaceCatalog`, Shared Data projections, capability bindings) -- the pointer controls which release a NEW process picks up, but does nothing to stop an ALREADY-RUNNING old-Core `EngramApplication` instance from continuing to write under an old schema after the pointer has already moved. Core update therefore needs its own installation-wide maintenance protocol, structurally identical to §13.5's bundle-upgrade drain/quiesce/migrate/commit sequence applied one layer up: each running Engram process holds a read lease identifying its `core_release` and shared-state generation; the bootstrapper stages and verifies the new release without disrupting anything yet; before any shared-state migration or activation, it blocks new process admission and obtains an exclusive host-update lease; it then DRAINS all old-Core processes by default (matching §13.5's actively-wait-for-writers-to-exit rule, not merely stop-admitting-new-ones); it migrates mutable `EngramHome` state into a shadow `shared_state_generation`; it then atomically switches the WHOLE TUPLE `(active_release, shared_state_generation, trust_catalog, builtin_bundle_set)` together, never `active_release` alone; an abort restores admission to the unchanged release/generation and durably records the failed attempt (per the state-vs-attempt split above). Old/new Core coexistence during the drain window is permitted ONLY if the new release's own manifest explicitly declares shared-state read/write coexistence compatibility -- it is never silently inferred from side-by-side installation. This is the Core-level instance of §13.5's own "no hot reload" rule: a running `EngramApplication` never mutates its immutable `RuntimeContext` into a new Core release out from under itself.
*   **Workspace compatibility across Core updates -- bounded, not open-ended (fixes an overclaim, cx.deepthink finding, HIGH, 2026-07-22):** Workspace State and the `WorkspaceCatalog` carry explicit `workspace_schema_version` and `compatible_engine_api` fields; a Core update migrates each workspace LAZILY, on that workspace's first open after the update (Constraint 14), via the same shadow-generation pattern as bundle-upgrade migration. The earlier claim that an incompatible workspace "remains openable under a matching older Core release if one is still installed" was broader than the record actually supports -- with only one `previous_release` retained, a workspace last touched two Core versions back would have no matching release to fall back to. `previous_release` therefore supports only IMMEDIATE installation-wide rollback together with its paired `shared_state_generation` -- restated precisely: "a failed lazy migration may trigger immediate rollback to the retained previous release and its matching shared-state generation," not an open-ended promise of arbitrary historical per-workspace Core execution. (If genuinely unbounded historical fallback is ever required, `previous_release` would need to become `retained_releases[]` -- deferred.)
*   **The compatibility preflight is a two-stage, TOCTOU-safe gate, not a single check "before replacing previous_release" (fixes a real gap, cx.deepthink finding, HIGH, 2026-07-22):** "before replacing `previous_release`" was too late and too imprecise -- replacement of the pointed-at release only actually happens at the final activation CAS, and workspaces/catalog revisions can change in the window between an early check and that CAS. The real order, composed with the installation-wide quiescence protocol above: (1) stage and authenticate the candidate release; (2) a CHEAP compatibility preflight against a captured `WorkspaceCatalog` revision; (3) build an immutable `WorkspaceCompatibilityPlan` (the captured catalog revision, every active workspace's recorded schema revision, the candidate's migration-path identifier/digest, and any approved stale-workspace waivers); (4) only THEN block new process admission and acquire the exclusive host-update lease; (5) drain old-Core processes; (6) re-read the catalog under the fence and CAS-check it against the revision captured in step 2 -- if it changed, this is exactly the kind of concurrent-mutation case `lifecycle_epoch`-style CAS-checking (§13.15) exists to catch; (7) revalidate the compatibility plan against the now-stable, re-read catalog; (8) if anything changed since the cheap preflight, ABORT before shared-state migration ever starts and retry from step 2 -- never proceed on a stale plan; (9) only then migrate the shadow `EngramHome` generation and atomically commit the activation tuple. This makes compatibility checking cheap and non-disruptive for the common case (step 2-3, before any user-visible disruption) while still being correct under concurrent catalog changes (the mandatory re-check at step 6-7, after the drain has actually stopped new mutations).
*   **Repair:** `engram repair` restores immutable release artifacts (Core code, schemas, trust catalog) while preserving Shared Config, Shared Data, credentials, and all workspaces by default -- repair fixes the Core installation, it does not touch user data unless a separate, explicit purge is also requested. As noted above, repair sourced from the installation's OWN verified copy only applies when that copy is trustworthy; a corrupted trust catalog or Core routes through the break-glass path instead, never through this normal one.
*   **Quiescence generalizes to an `InstallationMutationLease`, not just Core update (fixes a real scope gap, cx.deepthink finding, MEDIUM, 2026-07-22):** the installation-wide quiescence protocol above was worded only for Core update, but §14.1's bootstrapper claims to implement it more generally -- every operation that can invalidate a running Core's files or shared-state assumptions needs the SAME `InstallationMutationLease` (Core update, repair of the active release, plain uninstall, full purge, and retained-home schema migration during a `ReattachInstallTransaction`). Repair specifically stages a clean immutable copy and activates it through a new record generation -- it never overwrites files underneath an already-running process. Uninstall blocks new starts and drains existing processes before removing aliases or program files, same as update. Break-glass repair/uninstall may force-stop processes only through an explicit administrator decision, and must confirm lease/process release before deletion -- matching §13.5's stuck-writer confirmation rule exactly, one layer up.
*   **Workspace retire/destroy/export, and destruction specifically as a crash-recoverable saga (fixes a real gap, cx.deepthink finding, MEDIUM, 2026-07-22):** `workspace unregister`/`retire` removes a workspace from `WorkspaceCatalog` discovery while PRESERVING its `.ai/` on disk. `workspace destroy` is the actual data-deleting operation, and dry-run/confirmation/Policy-authorization/containment alone are not sufficient -- a crash between deleting `.ai/` and updating the catalog could leave either a live catalog entry pointing at nothing, or an unregistered-but-still-present state directory. `destroy` is therefore its own saga: (1) CAS the catalog entry `active|retired -> destroy_pending`, carrying an `operation_id`, canonical path, and lease expiry (mirroring §13.8's pending-record pattern); (2) atomically rename `.ai/` to a same-volume quarantine/tombstone location where possible, rather than deleting bytes directly; (3) re-confirm containment and identity against that quarantined location; (4) CAS the catalog entry to a `destroyed` tombstone (kept long enough to detect stale imports or replayed destroy requests, not deleted immediately); (5) only then permanently remove the quarantined data; (6) recovery reconciles any stuck `destroy_pending` using the catalog state plus whatever quarantined directory is actually present on disk. External credentials are untouched by `destroy` unless a separate, explicitly-authorized credential-revocation operation is also requested. `workspace export`/`import` preserves identity (`workspace_id`) and provenance across the move, with explicit collision detection against the destination `WorkspaceCatalog` (reusing §13.8's duplicate-detection/rekey flow).
*   **Uninstall boundary -- plain uninstall does not actually reach "absent" (fixes a real logical gap, cx.deepthink finding, MEDIUM, 2026-07-22):** plain uninstall by default preserves Shared Config, Shared Data, credentials, the `WorkspaceCatalog`, and every workspace -- calling its end state simply `absent` conflated "the Core binaries are gone" with "every trace of Engram is gone," which are genuinely different states. Fix: separate `engram_home_id` (the identity of retained Shared Config/Shared Data) from `installation_id` (the identity of one particular Core installation lineage), and distinguish at minimum `core_absent_home_retained` (plain uninstall's actual end state -- program removed, everything else intact) from `fully_absent` (only reached via a separate, explicit purge operation).
*   **Reinstallation onto a retained home is its own named transaction, decided not left as open questions (fixes a real gap, cx.deepthink finding, MEDIUM, 2026-07-22):** installing again after a plain uninstall (`core_absent_home_retained`) is neither a first installation nor a normal governed update -- it's a distinct `ReattachInstallTransaction`, with the v1 decision made explicit: reattachment PRESERVES `engram_home_id`; it creates a NEW `installation_id` (the prior one remains as provenance history, not reused); it validates the retained home's schema and compatibility BEFORE activation; migration into the new Core uses a fresh shadow shared-state generation, so retained data is never mutated in place; credential references remain present in the retained home, but peer readiness and vendor authentication (§14.2) must be revalidated before use rather than trusted as still-current; a schema-incompatible retained home fails closed and offers export, a compatible older installer, or explicit purge -- never a silent reset. Concretely: (1) the external bootstrapper authenticates the new Core through its external trust anchor (same as first install); (2) it stages the Core WITHOUT modifying retained data; (3) a compatibility validator loads the retained baseline/global Policy in a restricted validation context (not yet a full `RuntimeContext`); (4) it creates a candidate `InstallationRecord` generation plus the shadow home generation; (5) activation publishes both atomically together; (6) the first full `EngramApplication` start reconciles the external receipt into Evidence. This avoids the two wrong extremes -- pretending §13.15 governance was available before a runnable Core existed, or treating the retained home as fully ungoverned and ignoring its existing Policy.
*   **Identity/epoch scoping across uninstall and reattach (closes the final residual ambiguity, cx.deepthink finding, 2026-07-22, confirmed by full end-to-end trace):** `installation_revision` is scoped to one `installation_id` and legitimately restarts at `1` for a new installation lineage (e.g. after `ReattachInstallTransaction` creates a fresh `installation_id`). `host_lifecycle_epoch`, by contrast, is scoped to `engram_home_id`, NOT to installation lineage -- it continues monotonically ACROSS an uninstall and later reattachment, since the home itself (and its Policy/Evidence history) persisted the whole time even though the Core installation lineage changed. `current_record` CAS operations use a globally unique `record_id` (or composite ETag), never a bare installation revision, precisely so this doesn't get confused across lineages. A brand-new `EngramHome`'s epoch starts at `1` via the `BootstrapInstallTransaction`'s `expected=ABSENT` CAS. State-field invariants: `core_absent_home_retained` REQUIRES `active_release = null`; `active` REQUIRES a non-null, complete activation tuple; `fully_absent` has no `current_record` at all, because the `EngramHome` itself no longer exists to hold one.
*   **Multi-machine decision -- portable but single-writer for v1 (not concurrent multi-machine):** each machine installs Engram independently and maintains its own `WorkspaceCatalog`; the SAME `workspace_id` legitimately appearing in two different machines' `EngramHome`-scoped catalogs is NOT a duplicate (refining §13.8's duplicate-detection scope, which was already correctly limited to one `EngramHome`, with this explicit multi-machine framing). Portable workspace DEFINITIONS and provenance are kept separate from host-local paths, leases, running processes, and caches, so a workspace directory itself remains genuinely portable. Simultaneous mutation from unsynchronized copies on two machines is explicitly UNSUPPORTED in v1 and is detected (not silently allowed to corrupt) via a workspace generation/revision mismatch where possible. True concurrent multi-host use is deferred -- it needs distributed leases or a synchronization authority, a fundamentally different (and larger) problem than strengthening local CAS, out of scope here the same way third-party plugin distribution is deferred in §13.13. This is consistent with "install once, use from other apps" on ONE machine; it does not mean one installation serves unrelated machines concurrently.
*   **Offline boundary:** Engram's own control plane -- workspace operations, local Policy/trust-catalog validation, repair from local media, and any purely local-peer adapter -- must remain usable with no network access after initial installation. Initial installation and later updates support signed OFFLINE installation/update archives containing the complete release unit. Whether a given VENDOR AI CLI can itself authenticate/operate offline is vendor-specific and explicitly marked **TEST NEEDED per vendor and account type** here -- e.g. Anthropic's own Claude Code setup documentation currently states an internet connection is required for Claude Code operation specifically [declared, unverified, per vendor docs] -- but that vendor-specific limitation must never be allowed to make ENGRAM's own workspace/diagnostic functions unnecessarily fail offline too.

### 14.1 Packaging & Distribution Decision

*   **Primary distribution -- a signed native installer with an embedded, private Python runtime:** for the Windows-first MVP (per §12's phasing), a direct signed per-user installer (`.exe`/`.msi`), later exposing the SAME signed payload through WinGet as an additional discovery channel, not a second build. Versioned, side-by-side application directories with a small external bootstrapper handling install/update/rollback/repair/uninstall (this bootstrapper IS the implementer of the `BootstrapInstallTransaction`, installation-wide quiescence, and break-glass paths above). The Python runtime and all dependencies are bundled privately -- Engram never depends on, or conflicts with, whatever Python the user's own machine happens to have. A stable `engram`/`engram.exe` shim on PATH always points at whichever release is currently active.
*   **Why not a single frozen executable (PyInstaller/Nuitka) as the PRIMARY distribution:** freezing the entire Core into one opaque binary would work for a small bootstrapper or rescue/repair tool, but conflicts with the rest of this architecture -- Capability Bundles (§13.5) need to be independently installable Python packages, `adapter-conformance/v1` (§13.12) needs ABI-keyed conformance receipts tied to a real, inspectable Python/platform combination, and §13.4's lazy handler imports need an actual import mechanism, not bytes frozen into a single-file archive.
*   **Not every secondary channel provides the same host guarantees (fixes a real gap, cx.deepthink finding, MEDIUM, 2026-07-22):** the native installer's bootstrapper is what actually implements side-by-side releases, atomic activation, installation-wide quiescence, repair, and rollback -- an ordinary `pipx upgrade`, a Homebrew upgrade, or a distro package replacement does NOT automatically provide those same semantics just by being a secondary channel. `InstallationRecord` therefore also carries `installation_channel`, `update_authority`, `activation_mode`, and `rollback_capability` fields, and channels are explicitly tiered: the **managed/native channel** (the installer above) provides the FULL §14 host-lifecycle guarantees described in this section. The **package-manager channel** (future Homebrew/apt/WinGet) has the package manager itself own binary delivery -- its package must invoke the same bootstrapper if it wants to claim full atomic-activation guarantees; it cannot claim them just by being installed through a package manager. The **PyPI developer/automation channel** is explicitly UNMANAGED unless it separately installs the same bootstrapper/payload -- `engram update` run from a PyPI install reports the owning package-manager command (e.g. "run `pip install --upgrade engram`") and must never claim the native rollback guarantee it cannot actually provide. **npm is explicitly NOT a canonical channel at all** -- Engram is not a Node application; wrapping it in an npm package would add a second runtime and a second, competing update authority for no architectural benefit (distinct from Claude Code's own npm-distributed CLI, which is a vendor's own Node-based tool, not Engram's Python-based Core). Whichever channel a given installation came through, that channel's `update_authority` owns binary updates for that installation -- Engram must never race a package manager with its own competing self-updater.

### 14.2 Vendor AI CLI Boundary: Detect and Wrap, Never Bundle

*   **The rule:** Engram bundles its own adapters, manifests, schemas, and capability probes -- but NEVER the vendor AI CLIs themselves (Claude Code, Codex, Antigravity), their credentials, or their update mechanisms. This was already implied by §13.3's `python_bundle` adapter model and the current PortableDev precedent (`orchestration.json`'s `hub_nodes` reference externally-installed binaries hub.py invokes but never installs) -- this section makes it an explicit, binding architectural rule.
*   **Three separate receipts, not two conflated into one (fixes a real conflation, cx.deepthink finding, MEDIUM, 2026-07-22):** §13.12's `adapter-conformance/v1` proves the ADAPTER implementation satisfies `PeerAdapter` -- it is keyed by `bundle_digest`/`contract_version`/`engine_api_version`/`platform`/`python_abi`/`conformance_suite_version`, none of which a vendor CLI version bump changes. A vendor-CLI update is therefore a DIFFERENT question (does this particular external executable remain compatible with the adapter that wraps it) and must not automatically rerun or overwrite the adapter's own conformance receipt. Three distinct artifacts: (1) `AdapterConformanceReceipt` -- the existing §13.12 receipt, unchanged; (2) `ExternalDependencyReceipt`, keyed by `dependency_contract_id`, the canonical executable's identity, its observed version, its content digest, platform, the adapter bundle's own digest, the probe-definition version, and a probe-result digest; (3) `PeerReadinessReceipt`, which references one current receipt of EACH kind and is what actually gates invocation admission for that peer.
*   **What happens on vendor drift:** a vendor binary changing is an EXOGENOUS observation, not a §13.15-controlled mutation Engram initiated -- only the SUBSEQUENT change to Engram's own readiness/binding record is a governed mutation; the vendor-side change itself is merely audited Evidence. On detecting drift: invalidate ONLY the `ExternalDependencyReceipt` and `PeerReadinessReceipt` (never the `AdapterConformanceReceipt`); block new invocations of that peer while readiness is unknown; rerun the dependency capability/compatibility probe; keep the Capability Bundle itself `enabled` throughout -- vendor absence or incompatibility is a readiness problem, not a bundle-integrity `quarantined` condition (§13.5), and must not be conflated with one. Rerun `adapter-conformance/v1` itself ONLY if that fixture suite explicitly contains live vendor-integration fixtures -- and if it does, the vendor's identity becomes an explicit parameter of THAT integration receipt specifically, never silently folded into the universal adapter receipt's key. ("Reprobe/re-conformance-check," the prior round's looser phrasing, is replaced by: dependency reprobe and readiness recomputation, with adapter conformance rerunning only when its own declared fixture scope actually requires it.)
*   **The discovery/dependency model:** (1) the user installs each vendor CLI through that vendor's own official method; (2) `engram setup`/`engram doctor` discovers it through declarative locator rules (per-adapter, not hardcoded engine logic); (3) Engram records the `ExternalDependencyReceipt` above; (4) a missing or incompatible dependency produces an explicit diagnostic plus a link to the vendor's own official installation instructions -- never a silent failure or an Engram-authored workaround install; (5) authentication/login/logout for a vendor CLI remain entirely vendor-owned -- Engram's `CredentialResolver` (§13.5.5) stores only authorized credential REFERENCES, never re-implementing a vendor's own auth flow.
*   **Formalized in the adapter manifest:** an adapter's `bundle.json` (§13.5) declares an explicit external-dependency contract -- supported vendor-CLI version range, discovery strategy, capability-probe definition, a reference link to the vendor's own official help/install docs, and an explicit statement that install/update/auth for that dependency are vendor-owned. This rule applies equally to future `generic_cli`/`DeclarativeCliAdapter` peers (§13.3) once implemented.
*   **Evidence basis (declared, unverified -- vendor docs, not independently verified this session):** OpenAI documents Codex CLI installation through official scripts, npm, Homebrew, and release binaries; Anthropic documents native installers, WinGet, Homebrew, and npm for Claude Code, with installation-method-dependent update behavior; Google maintains its own separate Antigravity installation/authentication workflow -- three independent, self-owned installation/update authorities Engram deliberately does not take ownership of.

## Phase 3 Next Steps
This design is converged (architecture AND feasibility/phasing); Phase 3 is
exact schema/interface detail to pre-TDD level for phasing step 1 above
specifically (characterization tests + no-behavior-change RuntimeContext),
not further architectural debate:
*   Finalize the `PeerAdapter` interface contract version 1.0 in full (every
    method, not just the 5 named as examples in §6) against the real
    hub_peer.py implementation.
*   Write the actual JSON Schema files for `peers.json`, `init_workspace.json`,
    and the bootstrap manifest (this doc gives shape-by-example, not a
    formal schema yet).
*   Design the `RuntimeContext` construction code path itself (§2.5) and
    its unit tests -- CLI > bootstrap-manifest/env > cwd-discovery
    precedence, with explicit failure behavior at each tier.
*   Design the structured error/outcome model (§8) as an actual Python type,
    not just a prose description.
*   Scope the SUBST/junction legacy-migration backend's compatibility-mode
    behavior precisely (§7): what triggers it, what "destructive migration/
    unmount requires a separate confirmed action and rollback record" (per
    cx.effort's round-3 refinement) looks like as a real CLI flow.

**§14-specific obligations (cx.deepthink, added 2026-07-23, from the final
end-to-end trace pass that converged §14):** the architecture is ready to
move forward; the remaining work is schemas/tables/tests, not more prose:
*   JSON Schemas for `InstallationRecord`, `HostUpdateAttempt`,
    `WorkspaceCompatibilityPlan`, the bootstrap/repair/uninstall receipts,
    and lease/admission-fence records.
*   State tables covering: legal pre-commit abort points; the activation
    CAS as the one irreversible commit boundary; post-commit rollback;
    state-dependent required/null fields (e.g. `active_release = null` iff
    `core_absent_home_retained`); revision/epoch scopes (`installation_revision`
    scoped to `installation_id`, `host_lifecycle_epoch` scoped to
    `engram_home_id`); and successful lease/admission cleanup sequencing.
*   Fault-injection tests: concurrent first installers (exactly one
    `expected=ABSENT` CAS wins); catalog changes before vs. after lease
    acquisition; crash before the activation CAS; crash after CAS but
    before admission reopens; uninstall crash before vs. after the
    retained-home commit; reattach with a new `installation_id` while
    `host_lifecycle_epoch` stays monotonic; a stale `rollback_target_record_revision`;
    break-glass recovery never falsely recording Policy authorization.
*   One post-commit success-tail detail flagged as needing a real state
    table rather than more prose: after the activation CAS, the
    bootstrapper must durably record the commit, finish required
    post-commit checks/effects, release the mutation lease, and reopen
    admission against the new tuple before marking the attempt `completed`
    -- if a post-commit smoke check fails while admission is still fenced,
    rollback happens under that same lease.

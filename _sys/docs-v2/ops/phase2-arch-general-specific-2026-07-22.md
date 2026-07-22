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
> concrete spec gaps patched into §13.8-13.12. This does NOT change the
> §1-12 MVP migration path; it documents the further target §1-12 must not
> foreclose. Not yet implemented -- §1-12 is the architecture AND phasing to
> build Phase 3 (TDD prep) against, starting with §12's phasing step 1 only;
> §13 is the North Star those phasing steps must remain compatible with.
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
*   **Capability Bundle store:** Contains adapter and extension code, manifests, schemas, and bundle-local documentation. Bundles are versioned independently of the Core Engine.
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
    *   **Incompatible/quarantined branch:** `verified` may enter `incompatible` or `quarantined`.
    *   **Remediation:** `quarantined` is not terminal; remediation followed by re-verification may return the bundle to `verified`.
    *   **Removable property:** `removable` is a property of `installed-disabled`, meaning no dependents and no active locks exist. It is not a separate lifecycle state.
    *   **Uninstall:** A removable bundle may be uninstalled.
*   **Conformance gate before enablement (fixes a real disconnect, cx.deepthink finding, 2026-07-22):** `verified` (§13.11) means digest integrity + manifest-schema validation ONLY -- it says nothing about whether the bundle's code actually behaves per contract. §13.12 calls the `adapter-conformance/v1` fixture suite "mandatory," but nothing previously required it to run before a bundle could reach `enabled`, leaving "mandatory" toothless. Fix: `installed-disabled -> enabled` additionally requires a **conformance receipt**, keyed by `bundle_digest`, `contract_version`, `engine_api_version`, `platform`, the Python ABI/runtime, and `conformance_suite_version` -- a receipt is only valid for the exact combination it was issued against. A bundle without a matching receipt cannot be enabled. An upgrade must obtain a fresh receipt for the new version and pass it before its state migration runs (see below), not after.
*   **Upgrade and rollback -- transactional (sequencing clarified 2026-07-22, made transactional per cx.deepthink finding same day):** upgrade stages the new version's files on disk side-by-side with the current one (a content-addressed, immutable path per §13.4's TOCTOU fix), but this staged copy is NOT yet part of the active `enabled` configuration. It passes through the same `available -> verified` gate as any fresh install, then obtains its own conformance receipt (above) -- both before anything else happens. The engine then quiesces active users of the bundle via an exclusive maintenance lease, migrates state into a new, separate `state_generation` (never mutating the current generation in place -- a shadow copy, not an in-place edit), and validates the migrated result against that new generation. Only after migration validates does the engine atomically commit a single transaction record binding both the new `bundle_version` AND the new `state_generation` together, then switch the active lock. Nothing is ever `enabled` prior to passing `verified` and obtaining a conformance receipt; "side-by-side" describes on-disk staging, not an exception to the lifecycle or conformance gates. **Rollback** restores BOTH pointers in the transaction record (bundle lock AND state generation) together, never just one. If a migration is not reversible/backward-compatible, this must be determined and stated explicitly BEFORE execution -- rollback must never be silently promised and then found unavailable after the fact.
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
*   **Traceability fields:** Every graph node -- not limited to bundle manifests, but also `ResourceRegistry` entries (§13.5.5), policy documents, the Base Template (§13.9), and the schema catalog itself -- declares a stable ID (`bundle_id`, `adapter_id`, `command_id`, `event_id`, `policy_id`, `resource_id`, or `schema_id`, as applicable to its kind) plus `docs_ref`, `source_symbol`, and `test_ref` (scope expanded 2026-07-22, cx.deepthink finding: the original wording covered manifest objects only, leaving other §13 artifact kinds untracked by the graph they're supposed to be governed by).
*   **CI enforcement:** CI generates and validates the graph and rejects dangling IDs: any referenced ID must resolve to a valid target.
*   **Constraint coverage:** This is the concrete implementation mechanism for Constraints 4 and 11.

### 13.8 Bootstrap Root Discovery

The `ResourceRegistry` resolves logical resources after roots are known. Bootstrap discovery defines how the engine finds those roots without hardcoding a repository-specific path.

*   **Sanctioned exception:** Bootstrap discovery is the one explicit exception to Constraint 6, under Constraint 5's requirement to call out genuine exceptions.
*   **Two distinct roots, resolved separately (corrected 2026-07-22, cx.deepthink finding):** the original single precedence chain conflated two roots that must never be conflated -- an untrusted workspace's `.ai` directory must never be able to redirect where Core, Shared Config, Shared Data, or Capability Bundle actually live. There are two independent resolution chains:
    *   **`EngramHome`** (Core Engine / Shared Config / Shared Data / Capability Bundle roots): explicit install/shared-home override (`ENGRAM_HOME`) -> installation metadata (e.g. a bootstrap manifest written at install time) -> platform-convention default directory.
    *   **`WorkspaceRoot`** (Workspace State root only): explicit `--workspace` CLI argument -> `ENGRAM_ROOT`/workspace-scoped override -> upward marker-file or `.ai` directory walk from the current directory.
    *   If both `ENGRAM_ROOT` and `ENGRAM_HOME` are set and they disagree about where `EngramHome` should be, the engine fails with an explicit error rather than picking one silently.
    *   Before constructing `RuntimeContext`, both resolved roots are normalized and have symlinks/reparse points resolved to their real target -- a workspace cannot use a symlink to make its own `.ai` appear to satisfy the `EngramHome` chain.
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
    *   **Containment (added 2026-07-22, cx.deepthink finding: calling this "workspace initialization" does not by itself satisfy Constraint 9):** every destination the template generates or writes to MUST resolve beneath the workspace's own dedicated Workspace-State root (`<workspace>/.ai/`, per §2). The applier rejects, before writing anything: absolute destination paths, `..` traversal segments, and destinations that resolve outside the root after following symlinks/junctions/reparse points. A template entry that targets a path outside the allowed root, or an existing file outside it, is a hard error, not a warning. Dry-run and real application share the exact same path-normalization/resolution code path, so a dry-run preview cannot legitimately claim safety that the real run doesn't also guarantee. Real application writes to a staged temporary directory first and only commits (moves into place) after every entry in the template has been validated against the containment rule -- a mid-template failure never leaves a partially-applied, partially-contained workspace.
*   **Traceability:** Workspace origin remains discoverable through the template resource ID and recorded provenance.
*   **Constraint coverage:** This is the concrete implementation mechanism for Constraint 8, and the containment rule above is what makes it actually satisfy Constraint 9 rather than merely asserting it.

### 13.10 Derived/Cache Artifacts: the MECE Gap in the 5-Store Model

`bundle-index.json` and `traceability.json` are generated, regenerable, cross-bundle artifacts. They do not fit the ordinary contracts of Core Engine, Capability Bundle, Workspace State, Shared Config, or append-only Shared Data.

*   **Classification:** Derived/cache artifacts are an explicitly documented sub-area of Shared Data, not a sixth store.
*   **Contract:** Derived/cache artifacts are:
    *   regenerable from source-of-truth data;
    *   non-authoritative and never the only copy of a fact;
    *   atomically replaced rather than appended;
    *   safe to delete at any time.
*   **Regeneration:** The system must fully regenerate these artifacts. For example, `engram plugin verify --all` can rebuild `bundle-index.json` from installed bundle manifests.
*   **Store contract:** Shared Data documentation must distinguish its normal append-only Evidence records from this derived/cache sub-area.
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

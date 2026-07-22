# Phase 2 Architecture: No-Code, Config-Driven General-Specific MECE Structure
> **Status:** design, architecture AND feasibility both converged 2026-07-22
> (architecture: 5 rounds, ag.deepthink draft -> cx.effort reject-with-
> alternative -> ag concede+revise -> cx round-3 gaps -> ag apply-fixes ->
> cx catalog/conformance gap -> applied. Feasibility: independent parallel
> reviews by ag.deepthink + cx.effort, converged on §12's risk assessment
> and phasing despite different measurement methodologies -- real
> agreement, not rubber-stamping). User independently confirmed the §7
> SUBST/legacy-migration decision after the 260-char justification was
> verified empirically. Not yet implemented -- this is the architecture AND
> phasing to build Phase 3 (TDD prep) against, starting with §12's phasing
> step 1 only.
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

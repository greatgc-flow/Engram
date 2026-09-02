# Gate 2 design proposal: PeerHub AI-CLI autodetection (ag.deepthink, 2026-09-02)

**Status:** design proposal, one independent voice — not yet critiqued or
ratified. Produced by `ag.deepthink` reconciling
`docs/design/PHASE1-AUTODETECT-SIDECAR-2026-08-19.md` and its V2, against
today's explicit user requirement (peerhub must auto-detect installed AI
CLIs, fully independent of Engram). Two citations independently
spot-verified by the terminal against real files (`peerhub/adapters/
registry.py:84-90`, `OVERNIGHT-INFRA-LESSONS-2026-08-10.md:12-18`) — both
accurate.

## 1. Reconciled design (V1 vs. V2)

V2 explicitly overrode three parts of V1:

- **Discovery mechanism:** V1 proposed passively scanning `PATH` plus
  sibling `.peerhub-adapter.json` files (`V1:17-18`). V2 overrides this:
  no scanning arbitrary `PATH` executables — only manifests inside
  explicitly-configured, trusted adapter directories (`V2:25-27`).
- **Adapter extensibility:** V1 allowed a manifest to point at arbitrary
  Python code (`V1:18`). V2 removes that escape hatch; all behavior must be
  declarable via a strict JSON schema (`V2:30-31`).
- **Collision handling:** V2 adds fail-closed precedence — if multiple
  manifests claim the same peer alias, detection fails closed rather than
  guessing by directory order (`V2:32-33`).

**Final design:**

- **Trusted evidence:** a CLI counts as "installed" iff a valid
  `*.peerhub-adapter.json` manifest exists in a trusted directory (e.g.
  `%APPDATA%\peerhub\adapters.d\`). Bare `PATH` presence without a manifest
  is ignored. Conflicting manifests on the same alias -> fail closed.
- **Vendor list:** open/extensible, not a closed enum. `peerhub/adapters/
  registry.py:46-55` has 4 built-in factories (`fake`/`ag`/`cc`/`cx`); lines
  84-127 already expose `register_adapter_factory()` for runtime
  registration. Autodetected manifests get parsed and registered through
  that existing function via a new `GenericManifestAdapter`.
- **Stale-observation handling:** manifest presence proves intent, not
  current health. Cross-reference the manifest's target against the
  filesystem (same approach as `_resolve_executable_path()`,
  `registry.py:128-164`), then run a live readiness probe (`--version`) the
  same way peerhub already does for resolved targets. Results carry an
  explicit status so staleness is surfaced, never silently trusted.
- **Output DTO:**
  ```python
  @dataclass(frozen=True)
  class DetectedCLI:
      peer_kind: str
      cli_name: str
      manifest_path: Path
      executable_path: Path | None
      profiles: tuple[ProfileDescriptor, ...]
      status: Literal["READY", "BROKEN_LINK", "UNSUPPORTED_SCHEMA", "COLLISION"]
      error_context: str | None
  ```
- **Windows path/security:** no shell interpolation, ever. Per
  `OVERNIGHT-INFRA-LESSONS-2026-08-10.md` Incident 1 and the gap-analysis's
  commit `f8de373` finding, resolving a virtual SUBST path (`P:\`) down to
  its physical target (`D:\Engram&Peerhub\...`) exposes shell
  metacharacters like `&`. Two hard constraints: (1) never call
  `Path.resolve()` in a way that unwraps a safe virtual drive into a
  dangerous physical path; (2) always spawn subprocesses with a strict
  `argv` array and `shell=False` — manifests declare exec args as a string
  array (`V2:29-30`), never a shell command line.

## 2. Placement and integration

- **Library level:** `peerhub.adapters.discovery` — a pure reducer that
  scans trusted directories and yields `DetectedCLI` DTOs.
- **Application level:** a coordinator in `peerhub.application.adapters`
  consumes those DTOs, runs live readiness probes, and calls
  `registry.register_adapter_factory()` to bind valid discoveries into the
  runtime.
- **CLI verb:** `peerhub adapter discover` (or `peerhub adapter list`) —
  deliberately NOT `peerhub routing discover`, which already exists and
  does unrelated capability-matching (gap-analysis section 2.3). Naming
  matches the owning `adapters/` module.

## 3. Engram relationship (narrow scope)

**Recommendation: no hard runtime dependency either direction.** Engram
keeps its own dead-simple, independent "is the binary on PATH" check for
its own install/update/status-check flow (a package-manager concern —
"did the install put a working binary on disk"). PeerHub's autodetection
stays a fully separate capability serving a different purpose (mapping
binaries into its adapter/collaboration framework), and must work
identically on a host with no Engram present at all. Reasoning: a hard
dependency in either direction would violate today's explicit full-
independence requirement.

## 4. Test plan (MECE / real-measured E2E)

Split explicitly into two boundaries so a test never claims "measured" when
it's actually mocked:

**Fixture/mocked boundary** (exhaustive edge cases no real machine can
reliably reproduce): two temporary manifests both claiming `peer_kind="cc"`
-> assert `status="COLLISION"`; a manifest missing required `argv` ->
assert `status="UNSUPPORTED_SCHEMA"`; a manifest pointing at a nonexistent
path -> assert `status="BROKEN_LINK"`; a manifest whose target directory is
named e.g. `Test & Space` -> assert execution never goes through
`shell=True` and doesn't crash.

**Real/measured boundary**: deploy a genuine, controllable throwaway CLI
(a tiny real `.exe`/`.bat` shim) into the test runner's temp workspace with
a real, valid manifest in the trusted adapters directory; run the actual
`peerhub adapter discover` CLI command via `subprocess` (the same path a
real user takes); assert the shim is discovered, its `--version` probe
actually executed (not just a file read), and it reports `status="READY"`.
This is the boundary that proves the filesystem/CLI/subprocess integration
actually works end-to-end, not just that the reducer's logic is internally
consistent.

## Open items before this can be ratified

- Needs an independent critique pass (a second voice — ideally `cx`, since
  `ag` authored this) before treating it as unanimous, matching the
  standing dialectical-consensus rule.
- The exact trusted-directory location (`%APPDATA%\peerhub\adapters.d\` was
  proposed, not verified against any existing peerhub config convention —
  check whether `.peerhub/` (peerhub's existing per-workspace state
  directory, `peerhub/core/context.py:30-47` per the gap-analysis) is a
  better fit than a global `%APPDATA%` location, especially given peerhub's
  workspace-scoped design elsewhere.
- `GenericManifestAdapter`'s exact interface/contract with the existing
  `PeerAdapter` protocol was asserted, not designed in detail — needs a
  follow-up pass reading the real `PeerAdapter` protocol definition.
- No discussion yet of how a *removed* CLI (manifest still present, binary
  uninstalled) should be surfaced vs. `BROKEN_LINK` for a moved/renamed
  binary — may need a distinct status or may be fine as-is; flag for
  critique.

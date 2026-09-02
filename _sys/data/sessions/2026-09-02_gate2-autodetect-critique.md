# Gate 2 autodetection design — independent critique (cx.deepthink, 2026-09-02)

**Verdict: NOT ready for ratification. A revised design round is required.**

Critiquing `2026-09-02_gate2-autodetect-design-proposal.md` (ag.deepthink).
Two of the critique's most decisive citations independently spot-verified
by the terminal against real files — both confirmed accurate:
`peerhub/adapters/registry.py:84-127`'s `register_adapter_factory()` really
does raise `ValueError` on an already-registered `peer_kind` or an alias
owned by a different kind (so it cannot register the built-in cc/ag/cx
identities the proposal needed it to), and
`docs/design/PHASE1-MANIFEST-SCHEMA-V2-2026-08-20.md` really exists and
really is framed as resolving the exact manifest-vs-`PeerAdapter`-contract
mismatch this gate needs.

## What's sound and should survive into the next round

argv-only execution (no arbitrary Python), fail-closed collision handling,
live readiness probing, and the Engram/PeerHub independence principle.

## Four blocking problems found

1. **Manifest-only discovery silently narrows the user's actual
   requirement.** "Auto-detect installed AI CLIs" was quietly redefined as
   "detect CLIs that already have an opt-in PeerHub manifest" — but nothing
   shows Claude/Codex/Agy's real installers emit such a manifest today, so
   the proposal as written would detect nothing out of the box. Recommends
   a two-lane design: bounded built-in alias resolution (PATH search
   restricted to the already-known `claude`/`codex`/`agy` names) alongside
   trusted-manifest discovery for third parties.
2. **`GenericManifestAdapter` doesn't satisfy the real `PeerAdapter`
   protocol** (`peerhub/adapters/contract.py:628-657` requires
   `descriptor`, `prompt_policy`, `plan_invocation`, `new_decoder`,
   `interpret_output` — far more than "argv fields become a manifest").
   **Major finding: this exact problem was already solved.**
   `PHASE1-MANIFEST-SCHEMA-V2-2026-08-20.md` was written specifically to
   resolve this contract mismatch (manifest declares static shape, a
   bounded `engine_id`-selected engine implements the Turing-complete
   parts), `PHASE1-PROMOTION-SCHEMA-V1-2026-08-20.md` designates it
   normative, and `PHASE1-ARCHITECTURE-CONSOLIDATION-2026-08-21.md` is
   marked **ratified** and places a `ManifestAdmissionCoordinator` behind
   real dispatch admission. **Gate 2 may not need a from-scratch design at
   all for this piece — it may need "confirm this already-ratified design
   still holds and reconcile/implement it," which is a materially
   different (likely smaller) task than what was assumed going in.**
3. **The proposed registration path cannot register the primary target
   CLIs.** `register_adapter_factory()` rejects re-registering `cc`/`ag`/
   `cx` or their existing aliases — verified above. Needs a real
   discovery-vs-registration split: built-in discovery binds an observed
   install to an *already-existing* adapter kind; only genuinely new
   (third-party) kinds go through factory registration.
4. **DTO can't represent its own failure cases** (`UNSUPPORTED_SCHEMA`
   still demands a trustworthy `peer_kind`/`cli_name`/`profiles`, and
   `COLLISION` isn't a property of one manifest) — recommends discriminated
   result types instead of one flat `DetectedCLI`.

## Concrete resolutions to the 4 open items the proposal left open

- **Trusted directory:** `%LOCALAPPDATA%\PeerHub\adapters.d` (machine-local,
  not roaming `%APPDATA%`, and NOT workspace-scoped `.peerhub` — an
  installed CLI is a machine fact, not a per-workspace one; matches
  existing design precedent in `PHASE1-THIRDPARTY-DEFERRAL-AND-SHIMS-2026-08-20.md`).
- **Removed vs. moved CLI:** one neutral status is enough
  (`EXECUTABLE_NOT_FOUND` / `DECLARED_TARGET_UNRESOLVED`, not `BROKEN_LINK`
  which implies false certainty) unless relocation is independently proven
  via evidence; the proposal actually needs more than 4 statuses total, and
  they should map into peerhub's existing evidence vocabulary
  (`peerhub/core/evidence.py:17-24`: `MEASURED`/`ABSENT`/`UNAVAILABLE`/
  `ERROR`/`STALE`), not a disconnected new lifecycle.
- **Windows path/security:** the "never `.resolve()`" conclusion overreached
  — the real rule is never interpolate into a shell string, and keep the
  safe logical invocation path (e.g. `P:\...`) separate from a canonically-
  resolved security-identity path used only for symlink/reparse/replacement
  checks, revalidated at the dispatch boundary.
- **Engram independence:** the "no hard dependency" principle survives, but
  needs an explicit truthful-status boundary — Engram reports
  install/package facts only, never claims "PeerHub can use this," and may
  optionally invoke `peerhub adapter discover` as a non-authoritative
  post-install hint whose failure never rolls back an Engram install.

## Test-plan gaps flagged

A long list of missing cases (built-in-without-manifest, manifest
attempting to override a built-in, concurrent discovery, malformed/oversized
manifests, symlink/junction/reparse cases, PATHEXT edge cases, Windows
metacharacter edge cases in paths, failure atomicity, workspace allow/deny
policy over the global catalog, never writing to the real user profile
during tests) — see the full critique text for the complete list.

## Required next step

A revised design round that: reconciles with (or explicitly, with new
evidence, supersedes) `PHASE1-MANIFEST-SCHEMA-V2`/`PHASE1-PROMOTION-SCHEMA-V1`/
`PHASE1-ARCHITECTURE-CONSOLIDATION-2026-08-21` rather than inventing a
parallel contract; separates built-in bounded discovery from third-party
manifest activation; replaces the flat DTO with discriminated result types;
defines a neutral unresolved-target status mapped into the existing
evidence vocabulary; and specifies safe-invocation-path vs.
security-identity-path separately.

**Practical implication worth surfacing to the user immediately**: this
gate may be substantially cheaper than it looked, if the 2026-08-20/21
Phase 1 manifest/admission design is still sound — the remaining work could
be "verify and adapt an already-ratified design" rather than "design from
zero." That verification (reading PHASE1-MANIFEST-SCHEMA-V2 /
PHASE1-PROMOTION-SCHEMA-V1 / PHASE1-ARCHITECTURE-CONSOLIDATION-2026-08-21
end to end, and checking whether anything in the 441 peerhub commits since
2026-08-21 already implements or contradicts them) is the natural next
dispatch.

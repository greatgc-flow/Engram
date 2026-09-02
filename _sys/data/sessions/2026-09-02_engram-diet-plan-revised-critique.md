# Revised diet plan — second critique (cx.deepthink, 2026-09-02)

**Verdict: DO NOT RATIFY yet. Another focused design round is required.**

Terminal verification: 3 of the newly-found critical blockers independently
confirmed against real files (all accurate) — `provisioner.py`'s
`_resolve_peer_key()`/`ensure_peer_cli()` genuinely treat `peers.json` as
the install SSOT; Claude's `settings.json` genuinely still references
`check_contracts.py --hook`; `_sys/cli/launch` genuinely just sources
`_bat-shim`, which resolves and calls the matching `.bat` file. **The
SHA-256 digests in §2.4 were independently recomputed by the terminal from
scratch (BOM-stripped, CRLF-normalized, header-to-next-header block,
single trailing newline, UTF-8, SHA-256) and matched byte-for-byte** — cx
did not fabricate these; it correctly implemented its own stated method.

## Audit of the original 12 corrections: 3 pass, 7 partial, 2 fail

| # | Result |
|---|---|
| 1. Redraw increments around dependency edges | PARTIAL — A/B/C/D grouping is right, but "cut the peers.json dependency" is a result statement, not a file-level design (mount/unmount both reload peers.json; `register.state.json`'s junction list is recorded by `mount()` but ignored by `unmount()`). |
| 2. Atomic wrapper/registration/test slice | PARTIAL — dangling-route fix confirmed real; local-settings chain not concretely closed; ~13 more affected test files found beyond the named ones (`test_provisioner_autoinstall.py`, `test_system_lifecycle.py`, `test_managed_links.py`, `test_launcher.py`/`_log.py`, `test_migration_phase1.py`, `test_no_stray_health_files.py`, `test_routing_targets.py`, `test_check_c4.py`, `test_check_docs_mece.py`, `test_check_policy_constants.py`, `test_config_validator.py`, `test_doc_consistency.py`; `test_statusline.py` needs delete/move, not a vague rewrite). |
| 3. Staged + final boundary contracts | PARTIAL — staging present, but the final "no allowlist / no provider dependency" predicate contradicts intentionally-retained AI package records. |
| 4. Enumerate all omitted files | PARTIAL — `.bat` wrappers, `peer_console.py`, `console_runner.py`, `peerhub.bat`, `tidy_temp.py` (has provider cache rules), and critically `provisioner.py` itself still missing from any increment. |
| 5. Remove `local_settings` from migration | **PASS** — cleanup predicate itself still underspecified (current unmount deletes unconditionally; needs exact canonical-content-match rule for legacy installs). |
| 6. Retain optional AI lifecycle | **PASS as policy**, but not yet implementable — see the new critical finding below. |
| 7. Exact directives/lessons/statusline ledger | **FAIL** — no real schema, no statusline entries. Fixed below. |
| 8. Resolve generic launcher scope | PARTIAL — decision is right, but deleting `_bat-shim` while keeping `launch` breaks the launcher (verified). |
| 9. Uninstall/upgrade semantics | PARTIAL — principles present, no executable state machine (idempotence, rollback, junction/SUBST teardown ordering, proof-of-unmodified, what survives uninstall). |
| 10. Defer packaging to Gate 7 | **PASS.** |
| 11. Central version identity | PARTIAL — `version.json`-style is an example, not a spec (exact schema/owner/consumers/override rules still needed; current real duplication confirmed at `engram.cmd:118-125` hardcoding 2.1.0 and both Winget builders' independent `DEFAULT_VERSION = "2.1.0"`). |
| 12. Measured lifecycle validation | **FAIL** — only the upgrade test specified; clean-install/uninstall/idempotence/stale-artifact/full-suite-per-increment/package-content validation all still missing. |

## Real destination for DIR-001 through DIR-006 (replaces the fabricated §2.3)

PeerHub's real `LessonService` (`peerhub/governance/lessons.py:29-125`)
produces an advisory `peerhub.lesson.v1` `TargetState` — title/rule/
category/severity/scope/lifecycle/approval, with `source_evidence` empty
and enforcement defaulted `NOT_REQUIRED`. Its approval hash covers only
lesson ID/actor/authority/outcome, not the directive body. Injection
(`lesson_inject.py:28-115`) is advisory and lossy — severity-filtered,
capped at 8 items/1,200 chars, renders only `content.rule`, not
automatically attached to every dispatch. **This can hold an advisory
summary but cannot be the authoritative representation for DIR-001–006.**
The other candidate real type, `RatifiedInvariantRequestProjector`
(`peerhub/governance/invariant_requests.py`), only materializes an
immutable write *request* targeting `10-invariants.md` and explicitly
never writes the actual invariant — doesn't fit either.

**PeerHub needs a genuinely new domain** (proposed, not claimed to exist):
a `peerhub.governance-directive.v1` schema (directive_id, title,
body_markdown, body_sha256, lifecycle, effective/retired timestamps,
scope, source location, authority refs, supersedes, and a list of
`enforcement_bindings` each naming a real consumer + implementation status
`ENFORCED|ADVISORY_ONLY|PENDING|RETIRED` + evidence refs), owned by a new
`DirectiveService` with real proposal/activation/retirement/binding
validation — not a bare dict submitted to the governance broker (which
would just repeat the fabrication problem in a different form). A lesson
may optionally be *derived* from an active directive for prompt guidance,
but never become the authority itself.

**Per-directive disposition** (all six real, verified against
`user-directives.md`): DIR-001 (no matching PeerHub consumer found for the
ROI-gate/EXHAUSTIVE_COMPLETE logic — must land `PENDING`, not falsely
`ENFORCED`); DIR-002 (PeerHub has fail-closed evidence-source-tag machinery
but not the specific per-peer invocation-permission encoding — `PENDING`
until each adapter has measured bindings); DIR-003 (**retire at cutover**,
not migrate — it's specifically about `hub.py`'s API and
`test_contracts.py`, both gone); DIR-004 (PeerHub implements one bounded
evidence-validation subset, not a universal validator — binding must list
existing partial consumers + remaining gaps, not claim complete
enforcement); DIR-005 (real partial parity in `FinalArbiterPolicy`/
`arbiter_review.py`, but high-risk triggering + scoped-override semantics
still unimplemented); DIR-006 (real partial parity in `ProposalCoordinator`/
`.peerhub/proposals.json`, but the direction/tool-call classifier, override
phrase, unreachable-peer rule, and arbiter handoff aren't encoded as one
standing policy yet).

**Real, verified digest method**: UTF-8 read with BOM stripped, CRLF→LF
normalized, block from `### DIR-00N:` header through immediately before
the next `### DIR-` header, trailing-LF-normalized to exactly one, SHA-256
of the UTF-8 bytes. **The terminal independently recomputed DIR-001's
digest from scratch using this exact method and got an identical
byte-for-byte match** to cx's stated value
(`sha256:bd6a452ea5af1fab2653055ebdb52ac023d345ac8eaf3565fb23f6262c359f98`)
— confirms these are real computed values, not fabricated.

**Statusline is still entirely missing from the ledger** — needs its own
separate inventory (Engram's `_sys/ai/common/statusline/**`, provider
statusline scripts, Claude/Agy/Codex statusline config fields, any
usage/quota contract PeerHub genuinely consumes), each explicitly mapped
to a cited PeerHub implementation or waived/deleted — `test_statusline.py`
alone proves this is a substantial provider system, not one incidental
file.

## Three new critical/functional blockers (all independently verified)

1. **Retained AI installation breaks the moment `peers.json` is deleted.**
   `provisioner.py`'s `_resolve_peer_key()`/`ensure_peer_cli()`/`deploy()`
   treat `peers.json` as the install SSOT — but Increment B never touches
   `provisioner.py`, and Increment D deletes `peers.json` outright. The
   feature the revision explicitly said survives (correction 6) actually
   goes nonfunctional. Fix: add `provisioner.py` to Increment B; relocate
   the install-identity fields into a genuinely Engram-owned tool-catalog
   schema; make install/update/status resolve only from that catalog,
   never `node_ids`/peer profiles; rewrite `test_provisioner_autoinstall.py`;
   remove the stale pinned-PeerHub-version tool entry from
   `runtimes.json:250-264`.
2. **Increment A creates a dangling Claude hook.** Claude's project
   `settings.json` still invokes `check_contracts.py --hook`, but the
   vendor tree (where that config lives) isn't removed until Increment D —
   an existing host/project junction can keep invoking a removed/
   incompatible hook interface for 3 increments. Fix: either detach the
   hook config in the same transaction as the `check_contracts.py`
   replacement, or keep a compatibility shim until Increment D.
3. **`_sys/local.config.bat.template` is misclassified** — the revision
   deletes it whole, but it's mostly generic (SUBST settings, default
   workspace, custom tool path); only 2 lines are AI-specific (Claude
   Desktop/Gemini switches). Correct disposition: keep and narrow, matching
   the original gap-analysis's own conclusion.

## Four more major findings

- **"Zero AI ownership" is structurally too broad** given the retained
  package-lifecycle catalog — the real final invariant should read: "Engram
  may own declarative package-install metadata for independently
  installable tools, but owns no provider invocation, trust, profile,
  routing, collaboration, health, session, quota, governance, or PeerHub
  policy."
- **Ownership-matrix labels conflate capability ownership with file
  disposition** — "PeerHub owns `_sys/claude/**`" can be misread as
  authorization to copy vendor trust/config state, which the design
  explicitly forbids elsewhere. Needs separate columns: target capability
  owner / source artifact disposition / destination artifact-schema /
  migration gate.
- **The release command list isn't actually exact** — Engram currently
  also exposes help/version flags and `setup`/`doctor` aliases not
  accounted for in the "exactly ten commands" claim.
- **Uninstall's "provably Engram-generated and unmodified" predicate is
  undefined** — needs a concrete proof method (generation receipts for
  future installs, exact canonical-content match for legacy installs,
  preserve+report for anything unrecognized) and a full acceptance matrix
  per increment (files changed, test command, boundary-contract revision,
  expected package contents, forbidden stale paths, rollback proof) — none
  of which the revision currently specifies.

## Required for the next round (12 items, replacing the prior 12)

Replace §2.3 with the real directive design + per-directive ledger above;
add a separate statusline ledger; add `provisioner.py` + its tests to
Increment B and define the real tool-catalog schema; remove Engram's
pinned PeerHub-version catalog entry; expand Increment A with exact
`dispatch.json`/`virtualizer.py`/Claude-hook/existing-junction/cleanup-
proof changes; resolve `_bat-shim` (keep it, or rewrite `launch` inline);
keep-and-narrow `local.config.bat.template`; complete the affected-test
inventory + require a full-suite pass after every increment; replace "zero
AI ownership" with the precise package-metadata-allowed boundary; define
the exact version-SSOT schema+consumers; specify uninstall/upgrade state
machines with ownership receipts; add measured clean-install/upgrade/
uninstall/repeated-uninstall/stale-artifact/package-content tests.

## Overall verdict

The A-D restructuring direction is sound and should be kept. **Not ready
for ratification even with §2.3 fixed** — the `peers.json`-deletion-breaks-
the-installer blocker, the launcher-shim regression, and the dangling
Claude hook are real implementation-blocking gaps, not polish. Needs
another focused design round.

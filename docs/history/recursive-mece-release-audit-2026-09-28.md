# Recursive MECE release audit — 2026-09-28

## Decision

Engram 3.4.3 is release-candidate complete. Its scope remains deliberately
narrow: portable Windows developer-environment lifecycle management. Peer
collaboration, model routing, and token-consuming tests belong to PeerHub.

The planned **v3.4.4 patch follow-up** removes the last runtime configuration
bridge (`PEERHUB_CONFIG_HOME`) and corrects uninstall's link guard: ordinary
file reparse points used by Python virtual environments are safe to remove as
links, while directory junctions/symlinks that escape the allowlisted removal
roots remain fail-closed. No v3.4.4 tag or release artifact exists yet.

## Recursive traceability

| Capability | Implementation/config | Tests | Documentation |
|---|---|---|---|
| Bootstrap and portable runtime materialization | `_sys/core/`, `_sys/runtimes.json` | bootstrap, provisioner, path, lifecycle suites; Sandbox fresh install | README quick start and upgrade path |
| Tool/AI-CLI lifecycle | tool catalog, updater, provisioner | catalog, update, checksum, canary tests; real online discovery | README update scenarios |
| Doctor and path warnings | doctor/check modules | doctor, root hygiene, special-path tests | README command reference and warnings |
| Menu lifecycle | `engram.cmd`, registrar | command-surface and lifecycle tests | recursive per-verb `/?` help |
| Backup/restore/reset/uninstall | core lifecycle modules | round-trip, refusal, allowlist, cleanup tests | README safety and exit-code contracts |
| Packaging and WinGet | `tools/winget/build_package.py`, manifests | package-content and manifest tests; official WinGet validation | README installation guidance |

Root and nested help are side-effect free. `help`, `--help`, `-h`, and `/?` work
at the root and every current verb, including `menu status|enable|disable|clean`.
The root table documents behavior, flags, examples, and exit codes; tests prevent
new verbs from silently escaping this contract.

## History, structure, and loss audit

- Git history and migrated PeerHub provenance were reviewed before deleting old
  harnesses. The removed scripts duplicated or contradicted the canonical test
  route; no unique product behavior was present.
- The canonical source-test entrypoints are now `run-tests.bat`,
  `run-sandbox-test.bat`, `sandbox-unit-test.wsb`, and `wsb-entry.bat`.
- Development tests, tools, docs, caches, and mutable state are excluded from the
  release allowlist. The 3.4.3 archive has 47 entries including its generated
  release manifest and no test/docs/tool payload.
- Repository-root and folder-name assumptions were eliminated from canonical
  harnesses. Special characters that Windows batch or a third-party binary may
  reject are diagnosed as warnings rather than “fixed” with unsafe quoting hacks.
- AI collaboration history is retained under PeerHub; Engram retains only the
  package-separation pointer and product-relevant migration history.

## Simplification and no-code findings

Dead helpers (`build_env`, `load_json_env`, a duplicate downloader, unused receipt
path accessor, and the timestamp module) and their tests were removed. The full
unreferenced-function check now has zero findings and an empty baseline. Runtime
and tool specialization stays in JSON catalogs; Python handles generic download,
verification, materialization, and lifecycle mechanics.

## Verification

- Deterministic suite: **591 passed, 1 skipped**. The only skip is Windows
  symlink creation without the host privilege.
- Consistency checks: encoding, root hygiene, and unreferenced functions pass.
- Real local runtime: `engram doctor --json` passes.
- Real internet: `engram update --check --refresh` reaches declared providers and
  reports actual available updates without applying them.
- Package: `Engram-v3.4.3-portable-x64.zip`; SHA-256
  `283CD22708C0899A3DE4878E26774E152EE6AE4A35BD251DA7272595A672F017`.
  Official WinGet CLI manifest validation and extracted-archive CLI smoke tests
  pass. Rebuild the artifact if an included file changes after this record.
- Windows Sandbox release gate: **PASS** — fresh bootstrap, 591 tests, `doctor`,
  and forced online update discovery all passed. The gate exposed and closed two
  release-only defects: embeddable Python now augments verified TLS with the
  Python CA bundle and Windows ROOT/CA stores, and update discovery no longer
  proposes an older published version as an update to a newer local build.

## Feedback closure

Users can attach `engram doctor --json`, the failing command and exit code, and
the relevant log/update-proposal file to an issue without exposing `.engram/`
credentials. Confirmed failures close through a regression test plus a generic
implementation or declarative catalog correction. OS/provider limits close with
an explicit warning and documented workaround, not product-specific branching.

## Five-whys review and maintainer decisions

1. **Why remove `PEERHUB_CONFIG_HOME`?** The maintainer clarified after the
   v3.4.3 audit that Engram and PeerHub must be completely independent, including
   runtime configuration. The bridge was therefore removed: Engram no longer
   installs, invokes, configures, or includes PeerHub in its backup/reset schema.
   Explicit whole-tree operations still delete a user-confirmed `workspace/`
   regardless of which external tools created files below it.
2. **Why make Sandbox a release gate but not ordinary CI?** A fresh bootstrap is
   bandwidth-heavy and network-dependent. Deterministic CI remains mandatory;
   Sandbox is now a formal release gate and runs weekly on a dedicated Windows
   self-hosted runner because GitHub-hosted runners cannot provide the required
   nested virtualization.
3. **Why supersede the pending 3.4.2 WinGet submission?** 3.4.3 contains the
   audited package/help/test cleanup. Recommendation: publish 3.4.3 first, then
   submit its manifests and close or supersede the still-pending older PR.

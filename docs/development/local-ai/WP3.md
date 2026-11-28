# WP3 runtime lifecycle

## Extra-series patch transaction

`engram python update [SERIES ...]` targets the selected installed extra series. Omitting the series selects all installed extras. `--check` and `--dry-run` return the proposed result without applying it. Online mode queries the measured source and publisher inventories. Offline mode uses the reviewed archive pins in the current Engram copy. An offline no-change result means the available pin is no newer than the current build.

Updates admit a newer patch in the same minor and require matching implementation, provider, architecture, ABI and distribution flavor. The command refuses requests for new series, unavailable verified candidates and missing active executables. It prints the selected exact artifacts for confirmation and supports `--yes`. Every staged build passes the existing archive verifier and a temporary venv probe before the registry transaction commits. Build directories and already registered consumer bindings remain available. Existing exact app and project references keep their previous builds. The legacy default stays on the existing `engram update --only python` route.

The journal stores the exact before and after registry images and protects the atomic change to the active build. Staging failures leave the current registry image intact. After publication starts, staged paths remain available for resume and rollback. Cleanup of unregistered stages and retired builds requires reference-aware lifecycle verification before removal.

The Windows patch fixture uses a disposable root and the published Python Build Standalone 3.14.8 archive from the immutable 20261020 release. The public update handler consumes the reviewed offline 3.14.10 archive, preserves the project pin's exact bytes and selects 3.14.10 after unpinning. See the PR for the observed outcome.

T67 covers the extra-series patch transaction and exact reference retention. Compatible consumer rebinding remains open.

## Exact offline repair for missing extra build directories

`engram repair --only python-versions --offline --dry-run --json` checks all missing extra builds against the registered artifact identities and archives in `_sys/data/setup-files/python-archives`. File names use the original publisher version and tag. The registry digest anchors each archive. The command refuses an incomplete existing directory, unsupported provider identity or missing or mismatched archive. It uses only local files. Apply with `--apply` and approve at the prompt, or pass `--yes` for noninteractive use.

Repair preserves the existing build IDs, registry bytes and references. It verifies the private archive and probes the reconstructed interpreter in a temporary venv before an atomic directory rename. A marker identifies the operation's completed output for journal resume and rollback. Only a directory created by that operation is eligible for automatic undo. The ordinary repair scope and legacy Python remain on their original path.

The Windows fixture removes a retained build from the managed path inside a disposable root, proves the missing-cache blocker, and restores the exact older version under the existing build ID. It checks the active patched version and the registry bytes after recovery. Fault fixtures interrupt after the atomic rename, then exercise both resume and rollback with the archive unavailable. This covers exact reconstruction of registered interpreter directories. The following sections cover application venvs and managed relocation. The complete offline pack is documented below. Retention policy remains open.

## Offline reconstruction of registered environments

A managed environment can use a content-addressed `lock_ref` of the form `sha256-<64 lowercase hex>`. The lock is stored as `_sys/data/setup-files/python-locks/<lock_ref>.json` and the referenced wheels as `_sys/data/setup-files/python-wheels/<filename>`. Hash the exact UTF-8 lock file to derive its reference. The version 1 schema contains `schema` (integer 1), `build_sha256` (the registered interpreter archive digest), and `wheels` (a full dependency closure of objects with `filename` and `sha256`). Every wheel filename and digest must match the local cache. Resolve native wheel selection and editable application builds before producing this lock.

`engram repair --only python-envs --offline --dry-run --json` checks missing registered environments. Apply using `--apply --yes` or approve at the prompt. The build first verifies all private wheel copies, creates a venv at the final absolute destination, installs the exact wheel set without an index or dependency fetch, and verifies interpreter identity, SSL, SQLite, pip placement and installed dependency consistency. No registry revision is allocated. An operation marker supports resume and rollback of a newly created target. A venv already present at the expected path must have a matching base. A stale or incomplete directory is preserved for explicit handling.

The Windows test builds a fixture app venv on one writable volume, transfers its registry and caches to a second volume, and checks the copied venv's stale path. It restores at the new absolute root once the destination is clear and the old source path is unavailable. It exercises the missing-wheel refusal and verifies the native extension and pip launcher. It checks the original native extension, exact project pin and registry bytes. Existing app rollout and dependent-service orchestration require separate evidence.

[Python venv portability](https://docs.python.org/3/library/venv.html) · [pip secure installs](https://pip.pypa.io/en/stable/topics/secure-installs/).

## Relocate an owned stale environment

`engram relocate --only python-envs --offline --dry-run --json` previews stale managed environments that have a completed Engram ownership marker. Apply with `--apply --yes` or approve the plan interactively. The step verifies a private copy of the exact wheel set before moving the prior directory. This move stays on the destination volume, into a sibling named `.<environment>.previous-<operation>`. Engram rebuilds the environment at its final root and leaves the preserved directory available for recovery. If a check fails, the step returns the original directory to its original name. An unowned or incomplete prior directory stops the operation.

This component scope can follow the usual Engram relocation when a portable installation has both the legacy runtime and extra app environments. The Windows fixture exercises this scope on an actual cross-volume copy with Korean paths. It checks that the previous directory's configuration remains intact, the locked wheel's native extension matches its source digest, the generated pip launcher runs from the new installation, and the exact project pin uses the registered destination build. Retention and cleanup of preserved revisions need reference-aware lifecycle handling.

## Reference diagnostics before retirement

`engram python doctor [3.MINOR] --json` reports missing registered build or environment files, stale managed venv locations, an unusable caller project pin, and pending lifecycle recovery. The command reads local state and launches no interpreter, provider or repair operation. Each build reports active series, registered environments, consumer bindings, the current project pin and pending recovery as applicable. Known references produce PROTECTED. External project pins, backup references and live processes have unverified coverage, so a build with no known reference is UNVERIFIED. The diagnostic supplies evidence for a subsequent retention decision.

## Extra Python as a scoped Engram update

`engram update --only python-versions --offline --check --json` invokes the same patch planner as `engram python update` for all registered extra series. A preview is the default. Apply with `--yes`. The check has no install side effects, even when combined with `--yes`. Mixed component scopes and unsupported version overrides fail before discovery. With no registered series, the planner returns an empty plan without contacting the providers. The legacy default continues to use `engram update --only python`. Combined bare update and detached core handoff participation remain open in T69.

## Scoped Python runtime metadata backup

`engram backup --only python-runtime --out PATH.zip` writes the byte-exact
Python registry and its referenced content-addressed wheel locks to a new
ZIP. Export validates each lock against its registry reference and build
digest. It checks the same registry image again before publication. Treat
the metadata as private because its identifiers describe local consumers.

`engram restore PATH.zip --only python-runtime` previews after verifying the
bounded ZIP, registry, lock set and destination. Use `--apply` to restore
missing files into the same Engram installation identity. Existing identical
files are reusable. Conflicting live files and foreign identities stop the
operation. `--force` is unavailable for this scope. Copying an archive to a new
machine with a different Engram installation ID requires an explicit future
adoption contract.

The restore journal keeps the exact metadata and supports `engram repair
--resume` and `--rollback` even after moving the backup ZIP away. Rollback
restores the prior registry state. Verified content-addressed locks can
remain available to matching consumers. The lock set is published before the
registry. The archive carries metadata only. Preserve the exact offline
interpreter archives and wheels separately, then run the scoped repairs for
missing builds and environments. Older personal backup and restore paths
retain their existing scope.

This is a T71 metadata and recovery-chain slice. The optional artifact pack extends this slice. Disaster restore under a
replacement installation identity and coordinated application data backups
remain open.

The [Windows regression and native job](https://github.com/greatgc-flow/Engram/actions/runs/46143926894/job/140975706616)
passed against `8d373b6434ceda07da3755429080862936560244`.
It restored the registry and lock byte-for-byte on a different volume
using a Korean archive path. The preview made no destination writes. The
recovered registry and lock supported the existing offline venv rebuild,
including native MarkupSafe, the regenerated pip launcher and exact project
pin. A first Windows run found that echoing the archive path to redirected
CP1252 output could fail after a successful write. The scoped success
message now reports the revision, and a dedicated regression covers the
same output encoding. The final job passed 2,633 tests and 154 subtests.

## Complete offline Python recovery pack

Add `--include-artifacts` to `engram backup --only python-runtime --out PATH.zip`.
The pack contains the same registry and lock data, the exact archive for each
registered build, and every wheel named by a registered lock. Artifacts must
already exist in the standard cache. Missing, conflicting or modified
artifacts block export. Keep the completed ZIP in approved private storage.
Registry and lock hashes check consistency. Use a bundle from the original
trusted installation because the ZIP does not authenticate its producer.

The existing scoped restore command previews and checks each member before
apply. Apply restores only missing cache files, then publishes metadata under
the lifecycle lock. Verified cache files already published remain usable after
an interruption. Retry with the same ZIP if cache publication was interrupted.
A journal interruption after caching uses the existing resume and rollback
commands. Metadata-only ZIPs retain the same behavior.

The pack streams compressed source files as stored ZIP entries. This format
limits the cache to 4,096 artifacts and 32 GiB total, with the existing 256 MiB
interpreter archive limit and a 2 GiB wheel limit. It excludes unregistered
caches and the installed interpreter and venv trees. Restore reconstructs
missing builds through `engram repair --only python-versions --offline`, then
rebuilds environments through the corresponding repair or relocate scope.
Operator-owned project pins and the original installation identity must be
preserved separately. A pack does not copy or start any application.

The [Windows pack job](https://github.com/greatgc-flow/Engram/actions/runs/46151045848/job/140997543721)
passed at `e3c3e304f207b666cfa42320bc5ef737866c0268`. It recreated the
interpreter and the locked venv on a different volume after removing all
target caches and taking the original source path offline. The native
MarkupSafe wheel, regenerated pip launcher, prior venv and exact project pin
passed verification. The job passed 2,641 tests and 154 subtests. Metadata
and artifact names were validated before writes, and the input ZIP was
preserved.

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

The Windows fixture removes a retained build from the managed path inside a disposable root, proves the missing-cache blocker, and restores the exact older version under the existing build ID. It checks the active patched version and the registry bytes after recovery. Fault fixtures interrupt after the atomic rename, then exercise both resume and rollback with the archive unavailable. This covers exact reconstruction of registered interpreter directories. The following sections cover application venvs and managed relocation. Backup export and retention policy remain open.

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

## Observe running Python images before retirement

`engram python doctor [3.MINOR] --scan-processes --json` opts into a local
process snapshot through Engram's existing psutil dependency. An observed
exact registered interpreter or app venv launcher adds `LIVE_PROCESS` and
protects the build, including a retained patch whose old project pin has
been removed. Matching uses normalized executable paths and includes
managed windowed launchers. Results contain the build reference and
coverage; process IDs, executable paths and command lines stay out of the
report. The ordinary doctor avoids process enumeration.

A sample has partial coverage. Processes can race the snapshot, access can
be denied and aliases or unmanaged environments can evade matching. A
missing observation leaves retirement unverified. This evidence covers
observed live processes in T72. External project and backup reference
coverage, quiescence at removal and the destructive removal workflow remain
open.

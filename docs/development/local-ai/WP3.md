# WP3 runtime lifecycle

## Extra-series patch transaction

`engram python update [SERIES ...]` targets the selected installed extra series. Omitting the series selects all installed extras. `--check` and `--dry-run` return the proposed result without applying it. Online mode queries the measured source and publisher inventories. Offline mode uses the reviewed archive pins in the current Engram copy. An offline no-change result means the available pin is no newer than the current build.

Updates admit a newer patch in the same minor and require matching implementation, provider, architecture, ABI and distribution flavor. The command refuses requests for new series, unavailable verified candidates and missing active executables. It prints the selected exact artifacts for confirmation and supports `--yes`. Every staged build passes the existing archive verifier and a temporary venv probe before the registry transaction commits. Build directories and already registered consumer bindings remain available. Existing exact app and project references keep their previous builds. The legacy default stays on the existing `engram update --only python` route.

The journal stores the exact before and after registry images and protects the atomic change to the active build. Staging failures leave the current registry image intact. After publication starts, staged paths remain available for resume and rollback. Cleanup of unregistered stages and retired builds requires reference-aware lifecycle verification before removal.

The Windows patch fixture uses a disposable root and the published Python Build Standalone 3.14.8 archive from the immutable 20261020 release. The public update handler consumes the reviewed offline 3.14.10 archive, preserves the project pin's exact bytes and selects 3.14.10 after unpinning. See the PR for the observed outcome.

T67 covers the extra-series patch transaction and exact reference retention. Compatible consumer rebinding, cross-volume relocation, complete offline restore, reference-aware removal, and AI uninstall/reuse remain open in WP3.

## Exact offline repair for missing extra build directories

`engram repair --only python-versions --offline --dry-run --json` checks all missing extra builds against the registered artifact identities and archives in `_sys/data/setup-files/python-archives`. File names use the original publisher version and tag. The registry digest anchors each archive. The command refuses an incomplete existing directory, unsupported provider identity or missing or mismatched archive. It uses only local files. Apply with `--apply` and approve at the prompt, or pass `--yes` for noninteractive use.

Repair preserves the existing build IDs, registry bytes and references. It verifies the private archive and probes the reconstructed interpreter in a temporary venv before an atomic directory rename. A marker identifies the operation's completed output for journal resume and rollback. Only a directory created by that operation is eligible for automatic undo. The ordinary repair scope and legacy Python remain on their original path.

The Windows fixture removes a retained build from the managed path inside a disposable root, proves the missing-cache blocker, and restores the exact older version under the existing build ID. It checks the active patched version and the registry bytes after recovery. Fault fixtures interrupt after the atomic rename, then exercise both resume and rollback with the archive unavailable. This covers exact reconstruction of registered interpreter directories. Managed app venvs, dependency wheel packs, backup export, cross-volume lifecycle integration and retention policy remain open.

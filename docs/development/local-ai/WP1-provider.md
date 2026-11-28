# WP1 Windows Python provider admission

This increment implements R03/T59 and T60 on top of the registry in [PR #145](https://github.com/greatgc-flow/Engram/pull/145). It adds an opt-in source and binary check, admission of cached archives against an approved build identity, and a native consumer test. The repository's existing default interpreter continues to use the legacy resolver.

## T59 evidence contract

The shared resolver accepts `engram_python_candidates` as a discovery provider. It queries the existing CPython source feed and the latest stable, immutable Astral Python Build Standalone release. The adapter reads the public GitHub API at a fixed repository and checks the release ID, tag, publication date, asset API URL, download URL, uploaded state, size and SHA-256. Asset pagination uses the immutable numeric release ID. Duplicate identities, unreadable pages and missing advertised assets invalidate the inventory. A limit of 50 pages of 100 assets each bounds a check. Ordinary legacy discovery never contacts the new provider.

| Output | Evidence and interpretation |
|---|---|
| `source_version`, `support_phase` | Dated source feed, with stable numeric patch ordering and lifecycle boundaries. |
| `windows_binary`, `binary_identity` | Latest standard AMD64 MSVC install-only CPython archive for the minor in the sampled release. This is publisher inventory. Local archive admission is a separate check. |
| `binary_status` | AVAILABLE requires an exact source match. SOURCE_NEWER_NO_BINARY means the source patch has no matching build **in this complete publisher release**. A stale observation, incomplete relevant cycle, metadata failure or binary ahead of source gives UNVERIFIABLE. Older releases and other publishers are outside the inventory's scope. |
| `compatible_candidate`, `candidate_identity` | Newest eligible binary with a successful test for every requested consumer at the current lock digest. Receipts must identify the same immutable artifact and a SHA-256 of the evidence. An empty consumer set, a conflicting outcome, an unknown lifecycle or an EOL phase cannot authorize a candidate. |
| `installed` | The opt-in resolver reads the physical Engram registry separately. It reports the recorded active build and digest per series and the existing legacy inventory. Registry corruption gives UNKNOWN and blocks candidate selection. Download availability alone supplies no installation evidence. |

Call `core.version_resolver.resolve_latest("python", "engram_python_candidates", "", "python")` from the Engram Python environment to check published versions and the current registry. The lower-level `resolve_python_candidates(consumer_locks=..., receipts=..., registry_root=...)` accepts results from trusted in-process test runners. A receipt digest identifies evidence. Its authenticity comes from the runner and the controlled input path. This increment has no user-supplied receipt import. The source cache retains its own TTL. An explicit provider check enumerates fresh publisher metadata.

## T60 archive contract

The apply caller passes the selected publisher artifact and the independently approved plan identity to `core.python_artifact.open_verified`. The implementation compares implementation, exact version, ABI, architecture, flavor, provider, digest and asset reference before reading any file. It copies and hashes the cached archive into an operation-private temporary file. Consumers receive that exact stream after validation, so changing the original cache path cannot substitute different bytes. `verify_cached` returns the same receipt for inventory-only callers.

Admission validates gzip integrity and tar termination, bounded extents, ordinary files and directories, a single Python root and unambiguous Windows paths. It rejects linked or sparse members, case-insensitive collisions, file/directory conflicts, device paths and unsafe components. It checks AMD64 PE headers for the executable and versioned CPython DLL, the exact patch in the CPython header, and the venv/ensurepip layout. The native probe separately checks interpreter behavior, SQLite, OpenSSL, ctypes, pip, the installed native wheel and its location. The fixed profile accepts at most 256 MiB compressed, 512 MiB of expanded tar and 20,000 members. Temporary files are removed on success and failure.

Trust is rooted in the selected immutable publisher release over verified HTTPS or a reviewed repository fixture lock. The application must supply an approved plan, verified consumer locks, a fresh owned staging directory and a transactional publish before installation. Release attestation and redistribution clearance have separate evidence requirements.

## Evidence and reproduction

* RED on the registry parent produced 29 failures for the missing provider/admission implementation. The installed-inventory test subsequently identified a missing resolver input. The suite also exercises incomplete pagination, stale or conflicting evidence, numerical ordering, archived path metadata, identity mismatches and cache replacement after admission.
* A live, opt-in resolver check observed source and publisher matches for 3.11.18, 3.12.16, 3.13.18, 3.14.10 and 3.15.2 in release 20261124. Every compatible candidate was null with no consumer receipts.
* Local inventory-only admission verified the cached 3.14.10 release at SHA-256 `b062f2d8879a72b3d624697534aa8f736bf5eaf200ffbb1274602891a0e9e964`, including 2,311 regular files and 158,087,295 bytes of file content. Native execution is a separate workflow result.
* The Windows provider workflow uses a Basic User token and the pre-existing WP0 canary. After the offline wheel test it checks the fixed publisher release and joins a digest of the actual native receipt to the fixture consumer's lock. The workflow and PR record the observed native result and exact tested revision.

Run the source and registry regression from the checkout root with the development interpreter:

```text
python -B -m pytest -q -p no:cacheprovider _sys/tests/unit/test_python_provider.py _sys/tests/unit/test_python_registry.py _sys/tests/unit/test_version_resolver.py _sys/tests/unit/test_version_resolver_cache.py _sys/tests/unit/test_python_manager.py _sys/tests/unit/test_dispatcher_bool_result.py
```

Run the real artifact probe in an isolated Windows environment with the two pinned public inputs from `tools/feasibility/windows-python.lock.json`:

```text
python -B tools/feasibility/windows_python.py --archive ARCHIVE --wheel WHEEL --check-publisher
```

Use `--inventory-only` for archive inspection. Omit `--check-publisher` for fully offline verification against the reviewed fixture lock. The verified consumer in this probe is the pinned MarkupSafe wheel. Application-specific Hermes and Hindsight locks, managed installation, relocation/restore and RTX 3060 integration require their own gates.

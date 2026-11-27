# WP1 Python registry and legacy binding

R03, T58 and T64. [Draft PR #145](https://github.com/greatgc-flow/Engram/pull/145) continues [source discovery #144](https://github.com/greatgc-flow/Engram/pull/144). The PR timeline records the final Windows run and exact tested revision.

## Read and ownership contracts

The physical system directory is the caller's argument. Inventory uses the two existing Engram path resolvers for `env/python/python.exe` and `env/venv/Scripts/python.exe`. Zero, one or two files report ABSENT, PARTIAL or PRESENT. This shallow inspection does not execute either interpreter. An absent `data/state/python-registry.json` has logical revision zero. An existing registry must match the installation ID of the supported Engram environment manifest. A legacy installation can be inspected before it has such a manifest. The existing install/repair manifest path establishes durable ownership for an explicit future apply.

`engram doctor --json` adds a `python_registry` check when the registry exists. It reports invalid metadata as an error. Legacy-only check lists keep their existing shape. Discovery does not create the registry or acquire a write lock. Real executable, prefix and pip location checks are performed separately by the Windows test.

The supported schema 1.0 subset includes the protected legacy default, stable Windows x64 full CPython builds, one active build per series, retained builds and immutable locked environment generations. App and project bindings refer to the owning environment and its exact build. IDs, ABI, exact version, artifact SHA-256 and system-relative paths are checked. Paths follow the managed build, general environment or app environment layout. Directory junctions, symlinks, case-colliding keys, legacy AI directory collisions and duplicate JSON keys are rejected. Unsupported fields and nonempty external, vendor or rollback reference collections block this writer. Their future owners must extend validation before managing them. Existing builds and environments cannot disappear in a normal publication. This interface performs no file garbage collection.

## Publication and recovery

`core.python_registry.publish(system_dir, expected_revision, document)` is the WP1 apply interface for a caller with independently verified artifacts and consumer tests. Metadata validation does not authenticate an archive or prove that a runtime launches. Provider verification and the user-facing apply command belong to the following increments.

1. Validate the proposal and state paths. Acquire the existing lifecycle lock. Under the lock, require the expected revision and installation ID, then compare the old and new immutable records. An identical stale retry also conflicts.
2. Journal the exact old UTF-8 text (or absence) and the canonical new UTF-8 text before the first effect. The existing flush, fsync and replace helper publishes the file. Every successful update increments the revision by one. Encoded registry size is bounded to 1 MiB.
3. Recover through `engram repair --resume` or `--rollback`. Rebuild the fixed registry step and validate both images under the lock. A complete replacement with a missing acknowledgement is idempotent. A recognized partial new image can be completed, and a partial restoration can be retried. Undo restores the exact old bytes or removes the file created by that interrupted first publication. If interruption preceded intent capture, explicit rollback closes the empty operation.
4. A divergent file, future schema or changed installation ID blocks recovery. Acknowledged output must still match before commit. A corrupt file outside an active transaction is an error on read and on apply. Journal CRCs detect torn writes. The lock coordinates Engram writers. Neither mechanism authenticates a local OS user with write access to the installation.

## Evidence and reproduction

| Stage | Observation |
|---|---|
| RED | 29 registry and legacy tests failed on the parent at the missing module. The separate doctor assertion then failed on the missing public check. |
| GREEN | Registry, lifecycle journal/lock and environment manifest suites passed. A second RED fault test interrupted undo after a prefix of a noncanonical old image, and another interrupted before journal intent. Both recovery tests subsequently passed. |
| Local regression | 196 passed across registry, journal, lock, environment manifest, doctor, version resolver/cache, Python manager and dispatcher result suites. The extended Linux selection also hit six pre-existing Windows registrar assertions on the unavailable `winreg` backend. These six run natively in Windows CI. |
| Repository checks | Encoding, root hygiene, staged wiring and whitespace checks passed. Frozen Rev. 0.6 manifest and predecessor ID audit passed (8 entries, 150 cases, 50 ADRs, 28 risks, 9 requirement groups). |
| Native gate | Windows CI runs the full unit suite, release-contract checker and existing real-venv gate. The additional post-bootstrap check invokes the actual embedded executable, default venv and pip, and public offline repair/update dry-run JSON. It compares lifecycle state file bytes before and after. See the PR for job outcomes. |
| Hardware | Owner's Windows PC and RTX 3060 workloads remain NOT_RUN. These metadata tests make no GPU or throughput claim. |

From the checkout root:

```text
python -B -m pytest -q -p no:cacheprovider _sys/tests/unit/test_python_registry.py _sys/tests/unit/test_env_ops.py _sys/tests/unit/test_env_lock.py _sys/tests/unit/test_env_manifest.py _sys/tests/unit/test_doctor.py _sys/tests/unit/test_version_resolver.py _sys/tests/unit/test_version_resolver_cache.py _sys/tests/unit/test_python_manager.py _sys/tests/unit/test_dispatcher_bool_result.py
```

On a disposable, bootstrapped Windows checkout with the normal default installed and no extra registry:

```text
python -B tools/feasibility/windows_legacy_binding.py
```

The next WP1 tests cover trusted provider identity and artifact admission (T60) and the evidence join between dated source, available Windows binary and consumer compatibility (remaining T59). WP2 can then consume the registry from the public Python CLI. Cross-runtime lifecycle, coordinated backup/restore and GPU/application integration have separate gates.

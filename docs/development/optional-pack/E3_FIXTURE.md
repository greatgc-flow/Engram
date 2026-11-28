# E3 grouped publication fixture

This development probe uses the existing Engram lifecycle lock and journal with a fixed four-step group. It stages one immutable synthetic member, publishes a runtime pointer, publishes a package pointer and checks both together before commit. The same steps serve AI, ContentFlow and Gamma. An explicit initializer requires an empty test directory and marks it before any lifecycle operation. The program interprets the archive's sole admitted `app.txt` member as bytes. It checks the exact archive SHA-256 and caps both compressed archive and expanded member size. No package code is executed.

The runtime and package pointers are each bound to the same fixture revision and runtime ID. The package pointer also binds the staged member's digest. Publication rechecks the expected revision under the lifecycle lock. The activation snapshot uses that same lock, requires no active journal and validates both pointers and the materialized bytes. Recovery checks the requested package, expected old/new images and any acknowledged writes before replay. A divergent pointer is preserved and blocks activation. Rollback restores the previous pointer pair. Immutable staged bytes are retained and are unreachable through activation unless a committed pointer references them.

## Evidence

```sh
python -B -m unittest discover -s _sys/tests/unit -p test_pack_group_probe.py -v
```

Four initial RED cases failed at the missing module. The GREEN run installed the three synthetic descriptors independently, updated one, rejected a stale update, refused an unpinned or unlisted ZIP member, and exercised resume and rollback across both pointer boundaries. The next RED exposed entry into an uninitialized directory. GREEN requires the fixture marker and proves a real child process exit after the runtime pointer write and before journal acknowledgement. The parent checks activation fencing, stale-lock recovery and final pair coherence.

Targets EPP-009, EPP-014, EPP-015, EPP-016 and CFX-06/10 are partially covered at fixture scope. The probe uses fixture state files, a pinned digest, and returned fixture bytes. Production signatures, Python registry publication in the same transaction, installed app execution, uninstall and retention-aware garbage collection remain gated. Production implementation must bind the actual runtime provider's prepare and recovery interfaces before publishing its real registry. Current upstream WP2 draft #149 remains separate.

## Composing the Python registry

The same synthetic package coordinator can now opt into the actual `core.python_registry` publisher. `prepare_publication` captures compare-and-swap images under the lifecycle lock the coordinator already holds. `publication_step` uses the existing exact-image reconciliation and stores those images under the coordinator's own journal key. The standalone publisher keeps its original journal format and entry point. Recovery reconstructs and validates the registry step from those namespaced images under the same lock. An installed fixture's activation snapshot checks its exact app binding in the current Python registry.

The two RED cases initially failed because grouped publication had no registry interface. GREEN interrupts immediately after publishing the real Python registry and before package pointer publication. Activation sees the pending journal and rejects the mixed state. Resume publishes the package pointers and verifies materialized fixture bytes. Rollback restores the prior registry and pointer images. Removing a registered binding after commit makes subsequent fixture activation fail.

The current explicit Python runner branch performs separate journal and lock observations before resolving the executable. A real package activation and launch must use a common lifecycle fence across resolution and handoff. This increment exercises that fence only during fixture activation and has no product invocation path. Public dispatch and recovery routing, exact native binary/environment materialization, artifact signatures and production trust policy remain separate gates.

# WP0 feasibility and contract ledger

Reviewed 2026-11-28 KST. The only runtime eligible for the next foundation tests is a pinned extra CPython interpreter in a disposable directory. The AI profiles have no installation or execution approval in this ledger. All probes used public artifacts and synthetic fixtures.

## Baseline and traceability

| Observed remote | Commit and evidence |
|---|---|
| Engram main, v3.11.13 | `61076a4734d691fe917bee562a2e2bec9c7a9148`, [Windows CI 45899889659](https://github.com/greatgc-flow/Engram/actions/runs/45899889659). Unit tests, required release contracts, managed bootstrap and real venv proof succeeded. No open issues or PRs at intake. |
| Engram design | `c59c0e42bb6584bc873269b7128a1c94ecba3229` is a direct child of that main. Rev06 Git tree `cd18a540ea407a400dc637c46d8299f3d1ed12b9`. The handoff sits outside the package. |
| PeerHub main, v0.28.2 | `b1d877d689a9bc79d16054de7371b28b108049fd`, [CI 45983685529](https://github.com/greatgc-flow/peerhub/actions/runs/45983685529). No open PRs at intake. Open issues #498, #502, #503 and #504 cover diagnostics, attribution and refusal edge cases. |

Read the handoff and all nine files in [Rev06](../../design/local-ai-pre-tdd/rev06/). The audit recomputed eight SHA-256 values from Git blobs and verified the entire package tree against HEAD. The actual Rev05 ancestor matched the digest in SOURCES.md. Compared its T01–T86 and ADR-01–30 rows with the English rows. Rev06 contains exactly T01–T150, ADR-01–50, K01–28 and R01–09. The two CSVs agree in both directions, with one primary requirement per case. Every case's primary WP appears in the implementation-plan WP table, including cross-cutting rows. For example T74/T75 belong to R03 but run in WP0 even though the requirement's WP field describes the implementation span WP1–WP3. Use the catalog row for execution ownership. ADR-50 describes the historical pre-TDD stop. The owner's resume instruction authorizes feature development.

The package is immutable. T141 document/ID review passed for this revision. All other acceptance IDs retain their original unexecuted status until a scoped implementation has its own receipt. Individual probe assertions below support parts of cases. The historical CSV statuses are untouched.

## WP0 receipts and contract decisions

| Spike | Result and scope | Consequence / remaining gate |
|---|---|---|
| 01 baseline | PASS for exact refs, archived Windows baseline CI, dispatcher help and local unit fixtures. Linux CPython 3.12.14 targeted baseline run returned **206 passed, 133 failed**. 127 failures used Windows-only `mbcs`, six required `winreg`. `dispatcher.py update --help` returned 0. LF stdout SHA-256 `af37bdb2e33881700bf63fe800a91e88424b64a8629983745a2a59802a2435ae`. | Preserve the single default under `_sys/env/{python,venv}`, existing journal/lock, offline doctor and `update --only python`. Catalog pin 3.15.2 is distinct from installed version. The frozen CLI help lists 14 public verbs. Existing discovery data is notice-only and even retains EOL cycle patches. A new consumer cannot infer installability from that map. |
| 02 extra Python | **PASS for pinned native canaries**, including Windows Basic User token, effective admin false. [Job 140614575817](https://github.com/greatgc-flow/Engram/actions/runs/46031034950/job/140614575817) ran the same probe with elevated and limited tokens. On each, the fresh and rebuilt venv imported native MarkupSafe 3.0.3, SQLite 3.54.1, OpenSSL 3.5.9 and ctypes. Interpreter, ABI, base prefix, venv prefix, wheel location, x64 PE and offline pip check verified. Same-volume move through a Korean path with spaces. Sampled PEP 514, persisted environment and SUBST digests equal. | The exact archive and native wheel are WP0 fixtures, locked by publisher digest. 2,311 regular files, 158,087,295 uncompressed bytes, VC runtime DLLs, OpenSSL/SQLite extensions and bundled ensurepip. No installation through uv. Authenticity here uses the HTTPS immutable GitHub release metadata/PyPI digest and local byte comparison. No attestation verification or redistribution clearance claimed. The follow-up pair fixture below covers a cross-volume rebuild, two coexisting series and two negative wheel cases. Full registry/alias/reparse footprint, interrupted publication, coordinated Engram restore and the target workstation remain open. |
| 03 vendor dependencies | PARTIAL, metadata/source. At Hermes v0.23.4 the Windows PM provisions Python 3.14 and manages dependencies on invocation. Hindsight API 1.3.0 is a metapackage pulling `hindsight-api-slim[all]==1.3.0`. The MIT slim wheel requires Python >=3.11, asyncpg and pgvector. `all` also pulls pg0-embedded and local ML extras. OpenClaw 2026.11.10 declares Node `>=24.16.0 <25 \|\| >=26.1.0`. The catalog's Node 26.13.1 meets that range. | No PM override, fallback runtime, Hindsight metapackage install or OpenClaw activation. Need actual isolated app lock, native imports, launcher/update and write footprint. |
| 04 local model | BLOCKED on target driver, model, exact RTX 3060 allocation and quality dataset. Ollama v0.40.18 publishes a Windows AMD64 standalone ZIP. Hermes documents at least 64,000 tokens. | Hermes/64K and GPU profiles withheld. No measured VRAM, latency, tokens/sec, long-context or tool quality. |
| 05 memory / PostgreSQL | PARTIAL, upstream distribution inspection only. pgvector's Windows instructions build for a particular PostgreSQL installation with MSVC. The Python pgvector dependency provides no proof of server extension ABI. | Native PG binary pair, role/extension, local-only retain/recall, Knowledge Bank locator round-trip and isolated restore BLOCKED. No substitute database. |
| 06 hooks | NOT_RUN. No harness installed into private configuration, no history enrolled. | Capture off. Need a disposable supported harness, explicit local endpoint, install/undo, candidate-bank write constraints and no hidden writes. |
| 07 PeerHub | **PASS for synthetic ask preview and logical reads. FAIL for strict physical zero-write history on a closed WAL-mode fixture.** See contract below. Upstream CLI suites: **21 passed** in 1.70 s, Linux. Fake deliveries and process/socket guards cover replay and uncertain status. | A live source with a strict zero-filesystem-write policy is ineligible for these history CLI reads. Query an expendable copy of an explicitly supplied consistent closed snapshot. The replay fixture verified every original file digest remained equal. No assumptions about incremental export or native Windows CLI installation. |
| 08 policy | NOT_RUN for production OS enforcement. Synthetic dry-run guards observed no process launch or outbound connection. | This establishes a test witness for one path. Untrusted automation, external egress, privileged memory writes and bot dispatch remain disabled. |
| 09 staging / index | PARTIAL, static. The hash-verified slim wheel includes `hindsight_api/admin/reembed.py`. No shadow generation or safe independent KB migration executed. | Automatic model/encoder activation withheld. Need verified old generation, interrupted stage, shadow rebuild and restore gold. |
| 10 scheduler | PARTIAL, static. Slim wheel registers bank-scoped consolidation and operation status (GET), retry and deletion routes. | An operation identifier or deletion route does not establish safe interruption of running inference. Sleep and shared GPU admission remain unqualified pending actual foreground drain and recovery. |

The first native Windows run failed at the wheel-location assertion. The harness compared a resolved file against an unresolved Windows short-path directory and hid child stderr. Both paths now resolve before comparison, and failures name the specific invariant. The same command subsequently passed in both token contexts. [Initial run](https://github.com/greatgc-flow/Engram/actions/runs/46030535085) · [Corrected run](https://github.com/greatgc-flow/Engram/actions/runs/46030766815)

## PeerHub read contract at b1d877d

- Put explicit `--db PATH` before the subcommand. A missing store on `stream list --json` returns exit 5, an UNAVAILABLE object, and no created directory. A successful ask preview against some missing explicitly named stores can instead report `store_exists=false` with exit 0. Require a selected existing store.
- `stream list --json` and `session list --json` return objects with items and a continuation. `record read --stream ID --after POSITION --limit N --json` returns an **array**. Preserve stream and record IDs and positions. Do not assume the proposed Engram common envelope is native.
- Actual preview with `--prompt-file`, `--profile cc.standard`, `--workspace`, `--stream`, `--request-id`, `--timeout-seconds 180`, `--max-output-bytes 65536`, `--dry-run --json` returned a flat binding including peer/profile/workspace/stream/request, writable=false, fresh session and replay=false. It does not echo every limit or the packet digest. Bind these in Engram's approval receipt before future live use. The synthetic ask left the complete store directory byte-identical.
- On a separate history step the initial `stream list` created SQLite `-wal` and `-shm` sidecars. Existing file bytes and the Record stayed equal. Exit 3 in the feasibility script preserves the failed physical-write assertion. A live writable-source attachment cannot claim zero source-directory effects. The same stream, record and session assertions passed on a disposable working copy of the closed synthetic snapshot, with the original file tree byte-identical. An owner-supplied **consistent closed snapshot** may be queried in an expendable working directory. Never copy just the main file of a live WAL store. Defer missing outcome, late settlement and full history coverage, do not advance collaboration offsets or infer task success. No PeerHub patch requested or applied.

## Gates, risks and next RED

G0 document and mapping evidence is complete for the original scope. The new physical-read constraint is recorded here as an erratum. G1 is PARTIAL per profile. G2 is open for Multi-Python. G3 and G4 await integration and coherent recovery. G5 is BLOCKED for autonomous activity. G6 is BLOCKED on the actual GPU and quality fixtures. G7 is NOT_RUN. There is no releasable AI profile.

| Risk follow-through | Current handling |
|---|---|
| K01–05, K28 | Pin one fixture, test under effective non-admin Windows, keep unmeasured app/GPU/DB profiles unavailable. |
| K06–09, K19–22, K26 | Consent, scope and broker enforcement not exercised on target. No hook, remote tool, private source or approved-bank writer enabled. |
| K10–13, K27 | Existing records and source-owned execution receipts only. Read a consistent snapshot for a strict physical boundary. Attribution, late events and WAL pressure remain open. |
| K14–18, K23–25 | No mutable model activation, coordinated restore or sleep writer until rollback, generation fencing, and baseline regression are proven. |

Next independent RED for WP1/T59: provide a feed with a numeric patch past .9, a security-only series, an EOL series, conflicting lifecycle facts and an unreleased patch. The extra-runtime planning view must distinguish source/lifecycle evidence from Windows binary and compatibility evidence while preserving the existing `latest_patch_by_cycle` contract and legacy cache compatibility. T58/T64 registry publication and transactional acceptance require separate no-write, reference and fault oracles. After WP1, wire the public CLI in WP2. Keep WP3 lifecycle ahead of AI installation.

## Reproduction

From the Engram checkout, with existing Git objects and a Python 3.11+ test interpreter (3.12+ for native tar extraction):

```text
python -B tools/feasibility/rev06_audit.py
python -B tools/feasibility/rev06_audit.py --ancestor PATH_TO_ORIGINAL_REV05
python -B tools/feasibility/windows_python.py --archive LOCAL_ARCHIVE --wheel LOCAL_WHEEL --inventory-only
python -B tools/feasibility/windows_python.py --archive LOCAL_ARCHIVE --wheel LOCAL_WHEEL
python -IB tools/feasibility/peerhub_read.py --source PATH_TO_PINNED_PEERHUB_CHECKOUT
python -m pytest -q -p no:cacheprovider _sys/tests/unit/test_cli_help_contract.py _sys/tests/unit/test_env_manifest.py _sys/tests/unit/test_python_manager.py _sys/tests/unit/test_version_resolver.py _sys/tests/unit/test_dispatcher_bool_result.py
```

Use the dedicated PeerHub interpreter for its fixture. In the pinned PeerHub checkout the corresponding upstream regression command is:

```text
python -m pytest -q -p no:cacheprovider -o addopts= tests/communication/e2e/test_cli_ask_dry_run.py tests/communication/e2e/test_cli_readonly_core.py
```

The dedicated Windows [probe branch](https://github.com/greatgc-flow/Engram/tree/test/local-ai-wp0-windows) downloads exactly the two public inputs in [the fixture lock](../../../tools/feasibility/windows-python.lock.json). The probe stages and verifies them before use. For the target PC use the same native command from a normal Windows account with the two cached files. Capture the JSON plus the OS build. Managed registry restore, service recovery and target-PC validation require separate receipts.

### Cross-volume and side-by-side follow-up

[Windows Basic User job 140619836895](https://github.com/greatgc-flow/Engram/actions/runs/46032581127/job/140619836895) passed with effective admin false. Two isolated environments for CPython 3.13.18 (cp313) and 3.14.10 (cp314) built and ran concurrently, then rebuilt offline from the pinned artifacts on a second actual volume in a Korean path. The original base paths were unavailable during the second run. Both native extension imports resolved under the intended venv. Each environment rejected both a missing offline wheel and the other ABI’s wheel. Sampled environment/registry/SUBST digests remained equal. This is provider feasibility evidence for T62/T65/T66/T70/T71, ahead of managed install, registry, lifecycle and recovery acceptance.

The [pair harness and both fixture locks](https://github.com/greatgc-flow/Engram/tree/694dc70e0980d048802efffa9f5a5a9ac51ee0aa/tools/feasibility) live on the disposable Windows test branch. To repeat, place all four named inputs in one cache directory and run `python -B tools/feasibility/windows_pair.py --cache CACHED_INPUTS --second-temp-parent DIRECTORY_ON_ANOTHER_VOLUME` as a non-admin user. The harness creates its own temporary directories.

## Upstream evidence

- [Python Build Standalone 20261124](https://github.com/astral-sh/python-build-standalone/releases/tag/20261124) and [MarkupSafe 3.0.3 metadata](https://pypi.org/pypi/markupsafe/3.0.3/json). The legacy Engram embedded archive remains governed by its existing catalog.
- [Hermes v0.23.4 Windows](https://github.com/NousResearch/hermes-agent/blob/v0.23.4/website/docs/user-guide/windows-native.md), [PM](https://github.com/NousResearch/hermes-agent/blob/v0.23.4/website/docs/reference/package-management.md), [Ollama guide](https://github.com/NousResearch/hermes-agent/blob/v0.23.4/website/docs/guides/local-ollama-setup.md).
- [OpenClaw version metadata](https://registry.npmjs.org/openclaw/2026.11.10), [Ollama release](https://github.com/ollama/ollama/releases/tag/v0.40.18). GitHub reports SHA-256 `ca97292ac1e9acc77fcf473bb2741fa6acd12e3798f261b419680068b7cc4c16` for the plain Windows AMD64 ZIP. Metadata only, no model assets downloaded.
- [Hindsight API release metadata](https://pypi.org/pypi/hindsight-api/1.3.0/json) lists the wrapper wheel SHA-256 `bb68996c8834e28d27a676ae8fd4a8dd2a959cc860a923829f92b5a40527dc2d`. [Slim 1.3.0](https://pypi.org/pypi/hindsight-api-slim/1.3.0/json) wheel bytes matched `82232942f3819e5f9b685aa10be18358d1eb2b885457f703d768842b0d792448`; route observations came from its source without importing the server. [pgvector Windows build instructions](https://github.com/pgvector/pgvector/tree/v0.8.7#windows).

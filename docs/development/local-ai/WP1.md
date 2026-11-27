# WP1 Multi-Python source discovery

This first feature increment implements the source-feed portion of R03/T59. It uses the existing `version_resolver.resolve_latest` entry point and its existing Python HTTP request. The portable default, install path, public CLI and legacy latest-patch fields follow the original code. Review [WP0](WP0.md) for the independent artifact and native execution receipts.

## Source contract

A successful Python resolution adds `source_catalog`. It contains the UTC observation date, coverage and dated stable CPython 3 releases by minor, sorted numerically. Each row reports the source patch and its support phase. A parseable calendar date must place the patch on or after the cycle release and on or before the sample date. The documented boundary policy treats the support cutoff day as security-only and the EOL day as EOL. Missing, inverted or conflicting lifecycle boundaries give UNKNOWN. An undated patch is omitted and reduces coverage. A future patch cannot replace an already released patch in this view.

A source feed supplies no binary inventory or consumer test. Both `windows_binary` and `compatible_candidate` are null until later provider and dependency checks establish independent evidence. An EOL row remains visible for inventory. This result never installs it. Older caches give UNKNOWN coverage and an empty series map. A still-usable cache crossing a UTC date boundary retains its sample date with STALE coverage. Reading either cache does not rewrite it. A failed request retains the existing resolver error contract. Consumers must check the outer status, catalog coverage and row phase before using a result.

## Evidence

| Step | Result |
|---|---|
| RED | Eight new pytest cases failed with missing `source_catalog` against the WP0 tree. Tests invoked the public resolver and the cached Python provider. |
| GREEN | Resolver and cache suite, 35 passed. One synthetic EOL case was corrected to place the series release before the support cutoff. Separate negative cases still require UNKNOWN for inverted boundaries. |
| REFACTOR | Group dated patch observations, then classify a single consistent set of lifecycle boundaries. Resolver/cache, environment manifest, Python manager and dispatcher result tests, 96 passed. |
| Public feed smoke | Existing zero-cache resolver sampled the public feed on 2026-11-27 UTC. CPython 3.15.2 and 3.14.10 were BUGFIX, 3.13.18 SECURITY_ONLY, 3.10.22 EOL. Overall PARTIAL reflects incomplete lifecycle/release evidence elsewhere in the feed. No fetch of interpreter binaries by the resolver. |

Reproduce with the development interpreter from the repository root:

```text
python -m pytest -q -p no:cacheprovider _sys/tests/unit/test_version_resolver.py _sys/tests/unit/test_version_resolver_cache.py _sys/tests/unit/test_env_manifest.py _sys/tests/unit/test_python_manager.py _sys/tests/unit/test_dispatcher_bool_result.py
```

The remaining T59 work joins independently trusted binary/version and consumer-compatibility receipts and distinguishes a proven source-only patch from unavailable inventory. The next registry work covers legacy binding inventory, CAS/recovery, path ownership and reference validation (T58/T64). Provider publication, multiple-series selection and dependent AI installation stay behind their respective gates. No target-hardware benchmark has been performed.

The [registry implementation and recovery handoff](WP1-registry.md) records the subsequent T58/T64 increment, its supported schema and native Windows verification.

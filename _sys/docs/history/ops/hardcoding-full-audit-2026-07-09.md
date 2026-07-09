# Full Hardcoding + General Code Audit (2026-07-09)

Split two ways for parallel coverage: `ag` audited `_sys/core/*.py` (hub.py, hub_peer.py,
snapshot.py, config.py); `cx` audited `_sys/checks/*.py` and `_sys/cli/*.py` (35 files).
cc independently re-verified every HIGH finding and a sample of MED findings by reading
the actual code before including them here — 2 of ag's 5 findings turned out to be false
positives (see below); all of cx's spot-checked findings (3 HIGH + 1 MED) confirmed real
on first read. The remaining MED/low findings from cx are reported as-is (peer-verified,
not individually re-read line-by-line by cc) given the volume — flag if any look wrong
on a closer look.

## Confirmed HIGH severity (all independently verified by cc)

1. **`_sys/checks/check_sandbox_behavior.py:78`** — `parse_and_classify`'s `_classify()`
   treats `marker == "WROTE"` the same as `marker == "DENIED"` when the sentinel file is
   absent, both landing on `"enforced_denied"`. If a peer *claims* it wrote the file
   (`WROTE`) but the sentinel doesn't exist, that's an ambiguous/suspicious result (lie,
   race, wrong path, buffering), not evidence of enforcement — conflating it with an
   honest `DENIED` report produces false enforcement evidence for a security-measurement
   tool. **Did not corrupt B7's already-documented findings** — checked all 3 real runs
   from `sandbox-behavior-probe-b7-2026-07-08.md`; none hit this exact branch
   (`WROTE`+absent) by coincidence. Still a live bug for future runs.
2. **`_sys/checks/check_encoding.py:87,95`** — `_staged_paths()`/`_worktree_paths()`
   return `[]` on any `git` failure (non-repo, git missing, transient error), which the
   caller reads as "no files to check" → clean pass. The encoding/mojibake guard **fails
   open** on git errors instead of failing loud.
3. **`_sys/checks/self_care.py:131`** — calls `saturation_scan.py --quiet`, but
   `saturation_scan.py`'s argparse (checked `add_argument` calls) has no `--quiet` flag
   at all. Every invocation hits an argparse error (exit 2, message to stderr); `scan()`
   never checks `returncode` and only reads `stdout` (empty), so `self_care`'s "Scan"
   step has been a silent no-op every time it has run.

## Confirmed MED severity (cc-verified sample)

4. **`_sys/cli/diag.py:101,103,212,213,216`** — imports the config-sourced
   `QUOTA_WARN_FRAC`/`QUOTA_CRIT_FRAC` (line 25) but then compares against hardcoded
   literals `0.90`/`0.75` directly instead of using the imported constants. Exactly the
   class of drift CHK-CONST-1 already guards against for `snapshot.py` itself — `diag.py`
   bypasses it by hardcoding its own copies in the same file the correct values are
   imported into. If the config values ever change, the display would silently disagree
   with actual policy.
5. **`_sys/core/hub.py:3806`** (ag, verified) — arbiter subprocess `timeout=300` is a bare
   literal with no config lookup (unlike the two ag false-positives below, there's no
   fallback-from-config pattern here at all).
6. **`_sys/core/hub.py:2871`** (ag, verified) — `except Exception: pass` around
   `ask_history.jsonl` appends; silently swallows real IO errors (disk full,
   permissions) instead of surfacing them.
7. **`_sys/core/config.py:143,154`** (ag, verified) — same silent-swallow pattern for
   `runtimes.json`/`env.json` parse failures; corrupted config silently becomes `{}`.

## ag findings rejected as false positives (cc-verified)

- ~~`hub.py:6190` hardcoded path~~ — is a documented fallback default
  (`.get("path", "../_sys/data/operational_errors.jsonl")`) matching the actual value
  already declared in `protocol.json:835`. Already config-sourced at the real path;
  the literal is just a safety-net default, same accepted pattern used elsewhere.
- ~~`snapshot.py:1607` `switch_ratio=2.0` default~~ — the real call site
  (`hub.py:3465`) already passes `switch_ratio=ca.get("switch_ratio", 2.0)` sourced from
  `routing-config.json`'s `context_affinity.switch_ratio`. The function default is a
  fallback matching config, not a bypass.

## Remaining cx findings — reported as-is (not individually re-verified by cc)

Peer-verified, file:line given for each; see raw ag/cx replies for full reasoning if
needed.

**MED:** `saturation_scan.py:244` (`--sys-root` default resolves wrong root) ·
`check_cli_reality.py:302` (unchanged-hash refresh skip never rechecks server-side model
drift) · `check_cli_reality.py:321`/`check_cli_canary.py:396` (auto-refresh bypasses
budget cap via `all_profiles=True`) · `check_cli_canary.py:64,104` (budget defaults as
literals; failed persistence silently ignored) · `_common.py:169` (one auxiliary check
failure force-closes a peer's `gate_open`) · `_common.py:50` (hardcoded peer priority
`ag,cc,cx`) · `check_cli_reality.py:38` (`REAL_BINARIES` duplicates peer/path config) ·
`check_sandbox_behavior.py:199` (hardcoded `cc,ag,cx` instead of enabled-peer list from
orchestration) · `peer_console.py:113,134,147` (provider branches duplicate
orchestration's `required_effective_args`) · `peer_mgr.py:294` (missing provider template
falls back to invented Claude-style config instead of failing closed) ·
`check_health.py:60` (handoffs always claim `model_used=claude-sonnet-4-6` regardless of
actual model) · `check_health.py:78` (transcript discovery pinned to `P--` encoded dir) ·
`check_agents.py:27` (hardcodes `.claude/agents` instead of the configured agents tree) ·
`check_deps.py:16` (fixed/partly-legacy file list, silently skips missing entries) ·
`check_agents.py:75`/`check_risk.py:78`/`check_health.py:150`/`check_versions.py:52`
(malformed AI-backed check output still logged as success) · `ag_statusline.py:10,23,28`
(stdin dump written under source tree; subprocess has no timeout).

**LOW:** `check_health.py:94`/`check_docs_mece.py:326`/`check_policy.py:115` (governance
values duplicated, currently matching but driftable) · `batch_review.py:44,79`
(deprecated `config.json` read + hardcoded activation threshold `7`) ·
`saturation_scan.py:26,72,259`/`check_encoding.py:60` (assorted tuning literals) ·
`check_root_hygiene.py:20` (root allowlist embedded in checker) ·
`_common.py:81,121`/`check_cli_canary.py:165`/`check_cli_reality.py:183,255`/
`check_sandbox_behavior.py:145` (scattered probe timeouts/grace periods) ·
`check_agents.py:32`/`check_health.py:119`/`check_versions.py:31,41` (recovery messages
still point users at retired `gc`/Gemini commands) · `diag.py:258` (fable annotation
branches on literal peer/profile IDs).

## Confirmed clean

- No hidden TODO/FIXME/HACK/workaround comments anywhere in `_sys/core`, `_sys/checks`,
  `_sys/cli` (ag+cx both grepped independently).
- No hardcoded drive-letter paths across 35 files in `_sys/checks`+`_sys/cli` (cx,
  AST-parsed).
- No live "gc" branch logic outside the two already-tracked, deliberately-accepted P2
  items (`peer_console.py`'s `gc` branch, `batch_review.py`/`git_draft.py`'s
  `gemini_call()` shim) — remaining "gc"/Gemini mentions found are stale user-facing
  recovery-message text (see LOW list above), not executable routing logic.
- CHK-CONST's existing narrow scope (snapshot.py telemetry constants,
  telemetry-config.json schema, routing-config.json keys) was not itself circumvented.

## Not yet decided

This is an audit only — nothing has been fixed. Awaiting direction on which findings to
turn into backlog items / fix now vs. accept as known low-priority debt.

# Ops — agy.exe (Antigravity CLI) Known Bugs & Update Checkpoint

> Created: 2026-07-24 | Method: session-reproduced local evidence
> (ag.deepthink) + official issue-tracker research. **Part 2's external
> citations were independently re-sourced by the terminal after ag's first
> pass fabricated 6 plausible-looking issue numbers for the correct repo —
> see `feedback_verify_peer_citations` in the auto-memory system.** Every
> citation below was fetched and confirmed by the terminal directly.
> Purpose: run this checklist after every agy.exe version bump, before
> re-enabling unattended `hub.py` dispatch — this is exactly the failure
> mode that caused the 2026-07-23 ag model-ID incident.

Cross-ref: `ops/peer-cli-reference.md` (capability audit), `ops/cli-baselines/`
(verbatim `--help` captures), `ops/cli-update-checkpoints-codex.md` (sibling doc).

---

## Part 1 — Session-observed agy findings (`[verified]`)

### 1. Model-ID string format breaking change (v1.1.5 drift incident)
- **Status**: `[verified]`, observed & fixed 2026-07-23 (commits for
  `ag.opus`/`ag.gptoss` then `ag.standard`/`ag.effort`/`ag.deepthink`).
- **Finding**: agy.exe 1.1.5 stopped accepting Title-Case display names
  (e.g. `"Claude Opus 4.6 (Thinking)"`, `"Gemini 3.5 Flash (High)"`) as
  `--model` operands. It now strictly requires canonical lowercase-hyphenated
  strings (`claude-opus-4-6-thinking`, `gemini-3.5-flash-high`), with no
  back-compat fallback.
- **Impact**: old strings fail immediately with
  `Error: invalid model selection ... is not recognized as a known model`.
- **Evidence**: `orchestration.json`'s `ag.*` profiles all failed until
  converted to canonical form; live-confirmed against `agy.exe models`.

#### 1a. Model / effort resolution revalidation (2026-07-27)
- **Status**: `[verified]`, live minimal invocations for every configured
  `ag.*` profile.
- **Finding**: `agy models` continues to display materialized variants such as
  `gemini-3.6-flash-high`, but the current reliable profile form is the base
  slug plus explicit `--effort`: `gemini-3.6-flash --effort low|high`,
  `gemini-3.1-pro --effort high`, and `gpt-oss-120b --effort medium`.
- **Exception**: `claude-opus-4-6-thinking` is already an effort-specific
  Thinking variant. It must be passed without `--effort`; adding that flag is
  rejected as unsupported.
- **Operational rule**: retain lowercase/hyphenated identifiers, but do not
  infer from the catalog's suffixed display that all profiles should embed the
  effort in `--model`. Use the profile matrix in `specific/ag.md`.
### 2. Auth storage location & preflight mechanism
- **Status**: `[verified]`, inspected & tested 2026-07-23.
- **Finding**: credentials live exclusively in the OS keyring (Windows
  Credential Manager), never in files under `_sys/antigravity/config`.
  Credentials can expire/invalidate mid-session with no proactive warning
  and no dedicated `agy auth status` command.
- **Quirk**: `agy models` doubles as the de facto auth preflight — fails
  with `"Please sign in..."` (exit 1) when expired, returns the real catalog
  (exit 0) when valid. Directly reproduced both states this session
  (pre/post a manual relogin).

### 3. Windows Console API / PTY hard requirement
- **Status**: `[verified]`, A/B tested, documented since DIR-002.
- **Finding**: agy.exe requires a real Windows Console API context or PTY.
  A fully headless subprocess with no console hangs indefinitely — not a
  stdio-redirect or flag issue (A/B tested identical with/without
  `--dangerously-skip-permissions` and with/without stdout redirect).
- **Evidence**: `hub.py` solves this via `winpty` (`requires_pty=true`,
  `AgyAdapter`).

### 4. `--dangerously-skip-permissions` absolute override
- **Status**: `[verified]`, controlled deny-rule test, 2026-07-23.
- **Finding**: a project-level `settings.json`/`rules.json` with explicit
  `deny` entries (`{"permissions":{"deny":["read_file(...)", "command(...)"]}}`,
  precedence `Deny > Ask > Allow` per official docs) had **zero** effect
  once `--dangerously-skip-permissions` was passed — the denied action
  proceeded with no rule evaluation at all (confirmed via engine logs).
- **Impact**: there is no CLI-side defense-in-depth against this flag; any
  safety net must live at the hub/wrapper layer.

### 5. Untested plugin import surface
- **Status**: surface `[verified]` (via `--help`), execution impact
  `[declared, unverified]`.
- **Finding**: `agy plugin import (gemini|claude)` auto-imports existing
  Gemini CLI / Claude Code skill packages. Never mutation-tested — unknown
  side effects on existing config.

### 6. Sandbox filesystem confinement failure
- **Status**: `[verified]`, DIR-002, 2026-06-23.
- **Finding**: `--sandbox` does NOT enforce filesystem confinement on
  Windows. Do not rely on it for path-boundary security; the real boundary
  is git-diff guards + trust scoping.

## Part 2 — External known issues (verified by the terminal directly, 2026-07-24)

Repo: [google-antigravity/antigravity-cli](https://github.com/google-antigravity/antigravity-cli)
(confirmed real via WebSearch). Every issue below was individually fetched
and its content confirmed to match this summary — do not extend this list
without the same direct verification (see the memory-system lesson at the
top of this doc for why).

### 1. Hook `block` decision ignored for subagent spawning
- **Status**: `[declared, unverified]` (not reproduced locally)
- **Source**: [issue #640](https://github.com/google-antigravity/antigravity-cli/issues/640) —
  "PreToolUse hook `block` is ignored for `invoke_subagent`"
- **Finding**: a `PreToolUse` hook returning `{"decision": "block"}` correctly
  blocks normal tools (`write_to_file`, `run_command`) but is silently
  ignored for `invoke_subagent`/`define_subagent`/`manage_subagents` — a
  denied sub-agent spawns anyway. Reproduced on both 1.1.1 and 1.1.4, in
  non-interactive mode with `--dangerously-skip-permissions`, i.e. the same
  general area (permission enforcement gaps) as our own directly-verified
  Finding #4 above, but via a DIFFERENT mechanism (hooks, not rules.json).
  Open as of this checkpoint; assignee `manirajc`.
- **Relevance**: corroborates that agy's permission-enforcement surface has
  more than one hole — re-test hooks specifically, not just rules.json, on
  any version bump.

### 2. No token/env-var auth for headless/Docker environments
- **Status**: `[declared, unverified]` (feature request, not a bug fix we
  can test for)
- **Source**: [issue #632](https://github.com/google-antigravity/antigravity-cli/issues/632) —
  "Support Token-Based/Env Var Authentication for Headless/Docker
  Environments (Parity with Gemini CLI)"
- **Finding**: agy.exe has no `AGY_API_KEY`/env-var auth path; headless
  environments must either interactively log in once (keyring-based) or
  mount host config directories into the container (called out in the
  issue as "brittle, insecure"). Confirms our own Part-1-adjacent finding
  this session (no service-account/API-key/env-only auth mechanism found in
  official docs) is a known, currently-open upstream gap, not something we
  simply failed to find.
- **Relevance**: directly explains why `hub.py`'s ag dispatch has always
  had to rely on a pre-authenticated OS keyring rather than a portable
  credential — do not design future portability features assuming this
  will change soon.

### 3. 5-minute CLI freeze when an MCP server subprocess crashes during startup
- **Status**: `[declared, unverified]` (not reproduced locally)
- **Source**: [issue #657](https://github.com/google-antigravity/antigravity-cli/issues/657) —
  "bug: 5-minute CLI freeze when an MCP server subprocess exits/crashes
  during startup"
- **Finding**: if a configured MCP server dies immediately on startup, the
  client doesn't detect the process failure and blocks on the handshake
  until a hardcoded 5-minute timeout expires, on Windows. Root cause: no
  active subprocess-liveness check; the client waits even after stdio pipes
  close (EOF).
- **Relevance**: this is a DIFFERENT possible cause of a "5-minute hang"
  than the no-console/no-PTY artifact already documented in
  `ops/peer-cli-reference.md` §3 — if a future hang doesn't match the
  known console-requirement signature, check whether an MCP server is
  configured and crashing, before assuming it's the same old issue.

## Part 3 — Post-update verification checklist

Run mechanically whenever `agy.exe` is updated or replaced.

```
[ ] Step 1 — Model-ID schema diff
    Command: agy.exe models
    Verify:  diff the returned operand strings against
             `ops/cli-baselines/ag-1.1.5-help.txt`'s captured catalog.
    On fail: update `_sys/ai/orchestration.json`'s `ag.*` profiles
             (standard/effort/deepthink/opus/gptoss) to the new canonical
             strings — same fix pattern as the 2026-07-23 incident.

[ ] Step 2 — Auth preflight
    Command: agy.exe models
    Verify:  returns a real catalog, not "Please sign in".
    On fail: re-authenticate interactively (OS keyring — no headless path
             exists per external issue #632 above).

[ ] Step 3 — PTY/console requirement unchanged
    Command: python "_sys/core/hub.py" ask --to ag.standard --query-file <trivial-query.txt>
    Verify:  completes within ~15-30s, does not hang.
    On fail: check whether `requires_pty`/winpty wiring in `AgyAdapter`
             still matches the installed binary's console requirements;
             also check external issue #657 above (MCP-crash-triggered
             5-min freeze) as a possible different root cause.

[ ] Step 4 — Permission enforcement re-check (skip-permissions + hooks)
    Action:  re-run the deny-rule + --dangerously-skip-permissions
             controlled test from Finding #4 above.
    Verify:  confirm skip-permissions is STILL an absolute override (or
             note if a version finally adds defense-in-depth — that would
             be a meaningful, welcome behavior change to document).
    Also check external issue #640 above (hook `block` ignored for
    subagents) if hooks are ever adopted as an enforcement layer.

[ ] Step 5 — Sandbox confinement re-check
    Action:  re-verify `--sandbox` does/doesn't enforce filesystem
             confinement (DIR-002 test).
    On fail (regression) or pass (finally fixed): update Finding #6 above
             and `ops/peer-cli-reference.md` §3 accordingly.

[ ] Step 6 — External issue tracker sweep
    Action:  re-check issues #632, #640, #657 above for closed/fixed status;
             browse https://github.com/google-antigravity/antigravity-cli/issues
             for new items matching our own known-gap categories (PTY/hang,
             permission enforcement, model catalog, auth). Verify any NEW
             citation by fetching it directly before adding it here — do
             not trust a summary without opening the real URL.
```

## Audit record

```markdown
#### Agy CLI <version> — <YYYY-MM-DD>

- Binary: `_sys/tools/agy/agy.exe`
- Model-ID schema diff: `PASS | FAIL`
- Auth preflight: `PASS | FAIL`
- PTY/console requirement: `PASS | FAIL | CHANGED`
- Permission enforcement (skip-permissions + hooks): `PASS | FAIL | CHANGED`
- Sandbox confinement: `PASS | FAIL | CHANGED`
- External issues re-checked: `<#632, #640, #657, ...>` — status each
- Repository changes required: `<files or none>`
```

#### Agy CLI 1.1.5 — 2026-07-24

- Binary: `_sys/tools/agy/agy.exe`
- Model-ID schema diff: `PASS` (fixed 2026-07-23, all 5 profiles)
- Auth preflight: `PASS`
- PTY/console requirement: `PASS` (unchanged, winpty still required)
- Permission enforcement: `FAIL` (confirmed absolute override, by design — not expected to change)
- Sandbox confinement: `FAIL` (confirmed non-enforcing, DIR-002 still holds)
- External issues re-checked: #632 open, #640 open, #657 open (all as of this checkpoint)
- Repository changes required: none this pass (all known items already fixed/documented)

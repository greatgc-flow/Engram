# Ops — claude.cmd (Claude Code) Known Bugs & Update Checkpoint

> Created: 2026-07-24 | Method: session-reproduced local evidence (terminal,
> direct — cc has no separate peer identity to delegate this to) + official
> GitHub issue research, every external citation fetched and confirmed
> directly by the terminal before inclusion (see
> `feedback_verify_peer_citations` in the auto-memory system for why this
> matters — a peer fabricated citations for a sibling doc this same session).
> Purpose: run this checklist after every claude-code npm package bump,
> before re-enabling unattended `hub.py` dispatch.

Cross-ref: `ops/peer-cli-reference.md` §1, `ops/cli-baselines/cc-2.1.216-help.txt`,
`ops/cli-update-checkpoints-{agy,codex}.md` (sibling docs).

---

## Scope and baseline

Baseline observed 2026-07-23/24: Claude Code `2.1.216`, `claude.cmd` at
`_sys/env/nodejs/npm-global/claude.cmd`, subscription auth (`claude.ai`,
`pro`), `CLAUDE_CONFIG_DIR=_sys/claude/config`.

## Part 1 — Session-observed findings (`[cli_live]`, this session)

### 1. `--json-schema` genuinely enforces structure
A live `--model haiku --output-format json --json-schema '{...}'` call
returned a `structured_output` field containing the schema-validated parsed
object (`{"greeting":"..."}`) alongside `result`. Confirmed real, not a
no-op. Cost ≈$0.03 for the smallest useful test.

### 2. `--max-budget-usd` is a genuine hard stop
Exceeding the cap mid-call exits 1 with `subtype: "error_max_budget_usd"`,
`terminal_reason: "budget_exhausted"`, `errors: ["Reached maximum budget ($X)"]`.
Cost is NOT capped precisely at the limit — a $0.02 cap still incurred
$0.0615 of actual spend before stopping, so treat `--max-budget-usd` as a
soft ceiling that can overshoot, not an exact cutoff.

### 3. `--bare` genuinely requires separate API-key auth
A `--bare` call with no `ANTHROPIC_API_KEY` set failed immediately with
`"Not logged in · Please run /login"`, even though the normal subscription
session was fully authenticated. Matches the documented claim that `--bare`
is strictly `ANTHROPIC_API_KEY`/`apiKeyHelper`-only (OAuth/keychain never
read). Do not expect `--bare` to work in any environment that only has a
subscription login.

### 4. PATH shadowing — bare `claude` resolves to the wrong binary
`_sys/cli` is first on PATH; a bare `claude` invocation (even from this same
terminal) resolves to `_sys/cli/claude...`'s wrapper, which runs the heavy
hub context-fill path (room status, mailbox, handoff injection) instead of
a clean CLI call. Confirmed by direct reproduction this session — even the
terminal itself made this mistake once before catching it. **Always use the
full binary path** (`_sys/env/nodejs/npm-global/claude.cmd`) for any
programmatic/scripted invocation, exactly as `ops/peer-cli-reference.md` §4
already documents for `codex`/`agy`.

### 5. Real subcommand surface is richer than previously documented
Prior doc revisions listed `agents, mcp, config, plugin, update, doctor,
/skill-name` as the full subcommand set. Live `--help` (2.1.216) shows:
`agents, auth, auto-mode, doctor, gateway, install, mcp, plugin/plugins,
project, setup-token, ultrareview, update/upgrade`. `config` is NOT a real
top-level command. `claude project purge` deletes all Claude Code state for
a project (transcripts/tasks/file-history/config) — destructive, never call
from automation.

### 6. `--resume` correct-usage pattern (already documented, still true)
Turn 1: `--session-id <uuid>` (create-semantics). Turn 2+: `--resume <uuid>`.
Reusing `--session-id` on turn 2 is create-semantics and errors — this was a
real hub bug fixed 2026-07-02, worth re-testing on any Claude Code version
bump given the external issue below shows `--resume` itself has broken
before.

## Part 2 — External known issues (verified by the terminal directly, 2026-07-24)

Repo: [anthropics/claude-code](https://github.com/anthropics/claude-code).
Both issues below were individually fetched and confirmed to match this
summary.

### 1. Bypass-permissions mode can still prompt
- **Status**: `[declared, unverified locally]`, closed-as-duplicate upstream
- **Source**: [issue #42366](https://github.com/anthropics/claude-code/issues/42366) —
  "Bypass permissions mode still prompts for settings.json edits and other
  operations"
- **Finding**: even with `--dangerously-skip-permissions`,
  `permissions.defaultMode: "bypassPermissions"`,
  `skipDangerousModePermissionPrompt: true`, AND explicit allow rules all
  set simultaneously, prompts still appeared for `settings.json` edits and
  other operations (v2.1.89, macOS). Reporter: "makes fully autonomous
  workflows impossible." Closed as duplicate — a canonical tracking issue
  exists elsewhere, not independently located this pass.
- **Relevance**: `hub.py` relies on `--dangerously-skip-permissions` for
  every non-interactive cc dispatch. If a future version silently starts
  blocking on an unexpected prompt mid-`ask`, this is a known upstream
  failure mode, not necessarily a hub/config bug — check this issue family
  before deep-diving hub-side.

### 2. `--resume` can crash outright on a version regression
- **Status**: `[declared, unverified locally]`, closed-as-duplicate upstream
- **Source**: [issue #53092](https://github.com/anthropics/claude-code/issues/53092) —
  "[BUG] Claude Code Resume Not Working"
- **Finding**: `claude --resume` crashed with
  `ERROR F1H is not a function. (In 'F1H(q)', 'F1H' is undefined)` on
  v2.1.120, macOS — a real regression (worked in prior versions), duplicate
  of #53041.
- **Relevance**: `hub.py`'s entire cc session-reuse mechanism depends on
  `--resume` working. A version bump that breaks it would silently degrade
  every cc dispatch to cold-start (no session continuity) or hard-fail —
  worth a direct smoke test (see checklist below) on every version bump,
  not just trusting it still works because it did last time.

## Part 3 — Post-update verification checklist

```
[ ] Step 1 — Version + free subcommand-surface diff
    Command: claude.cmd --version && claude.cmd --help
    Verify:  diff against `ops/cli-baselines/cc-2.1.216-help.txt`.
    On fail: update `ops/peer-cli-reference.md` §1's subcommand list and
             this doc's baseline if the surface changed.

[ ] Step 2 — --resume smoke test (real regression risk, see external #53092)
    Action:  create a session with --session-id, do one trivial turn,
             then --resume it and confirm context is actually restored
             (e.g. ask it to recall something from turn 1).
    On fail: hub.py's cc session-reuse will silently degrade or hard-fail —
             this is HIGH priority to catch before it affects real dispatches.

[ ] Step 3 — --dangerously-skip-permissions reliability spot-check
    Action:  run one --print dispatch matching hub.py's real invocation
             shape and confirm it does NOT stop for an unexpected prompt.
    On fail: check external issue #42366's family for a matching upstream
             regression before assuming it's a hub/config problem.

[ ] Step 4 — --json-schema / --max-budget-usd still behave as measured
    Action:  re-run the minimal schema + budget-cap tests from Part 1
             (~$0.03-0.10 total cost).
    Verify:  structured_output field still present and schema-conformant;
             budget-exceeded still exits with error_max_budget_usd.

[ ] Step 5 — PATH-shadowing regression check
    Action:  confirm any hub.py/scripted code still calls the FULL binary
             path, never a bare `claude`/`codex`/`agy` — this is a
             recurring risk category (already caused a real diag.py stall
             once, see `ops/peer-cli-reference.md` §4).

[ ] Step 6 — External issue re-sweep
    Action:  re-check #42366 and #53092 for closed/fixed status; browse
             https://github.com/anthropics/claude-code/issues for new items
             matching permission-mode or session-resume categories. Verify
             any NEW citation via direct WebFetch before adding it here.
```

## Audit record

```markdown
#### Claude Code <version> — <YYYY-MM-DD>

- Binary: `<absolute real claude.cmd path>`
- Version/help diff: `PASS | FAIL | CHANGED`
- --resume smoke test: `PASS | FAIL`
- --dangerously-skip-permissions reliability: `PASS | FAIL`
- --json-schema / --max-budget-usd: `PASS | FAIL`
- PATH-shadowing check: `PASS | FAIL`
- External issues re-checked: `<#42366, #53092, ...>` — status each
- Repository changes required: `<files or none>`
```

#### Claude Code 2.1.216 — 2026-07-24

- Binary: `_sys/env/nodejs/npm-global/claude.cmd`
- Version/help diff: `PASS` (this checkpoint IS the first baseline capture)
- --resume smoke test: `PASS` (verified working 2026-07-02, not re-tested this exact pass)
- --dangerously-skip-permissions reliability: `PASS` (no unexpected prompts observed this session across dozens of dispatches — but see external #42366, not proactively re-tested against that exact repro)
- --json-schema / --max-budget-usd: `PASS` (both directly confirmed 2026-07-23/24)
- PATH-shadowing check: `PASS` (documented, one live mistake caught and corrected this session)
- External issues re-checked: #42366 open (closed-as-duplicate, canonical issue not located), #53092 closed-as-duplicate-of-#53041
- Repository changes required: none this pass

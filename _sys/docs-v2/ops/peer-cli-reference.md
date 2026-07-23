# Ops — Peer CLI Reference (execution-verified)

> Created: 2026-07-02 | Method: `--help` **plus actual execution** of each CLI.
> Legend: **✓run** = verified by running it this audit; **(help)** = documented in
> `--help`, not separately exercised. Binaries are the REAL ones under
> `_sys/env/nodejs/npm-global/` and `_sys/tools/agy/`, NOT the `_sys/cli` wrappers
> (which shadow bare names on PATH — see §4).

Cross-ref: `general/lifecycle.md` (session/heartbeat), `specific/{cc,cx,ag}.md`,
`ops/diag-telemetry-architecture.md`.

---

## 1. claude.cmd — Claude Code **2.1.215** (peer `cc`)

Path: `_sys/env/nodejs/npm-global/claude.cmd`. Default = interactive; `-p/--print`
= non-interactive one-shot.

### Modes & core flags
- `-p, --print` — non-interactive print. **✓run**
- prompt via stdin (`-`) or arg. **✓run** (hub uses stdin)
- `--dangerously-skip-permissions` — bypass permission prompts. **✓run**
- `--model <m>`, `--effort <level>` — model/effort for the session. **✓run** (hub profile_args)
- `--append-system-prompt <p>`, `--system-prompt-file` — inject system prompt. **✓run** (hub IPC frame)
- `--output-format <text|json|stream-json>`, `--input-format`, `--include-partial-messages`,
  `--json-schema <schema>` (structured output), `--max-budget-usd`. **(help)**
- `--agents <json>`, `--mcp-config <...>`, `--add-dir`, `--settings`, `--plugin-dir`. **(help)**
- `--bare` — minimal mode (skip hooks/LSP/plugin-sync/auto-memory; API-key auth only). **(help)**
- `--safe-mode` — used by hub invoke_args. **(help)**

### Session / resume — **the important part**
- `--session-id <uuid>` — **SET/create** a session with a known id. **✓run**
- `--resume <id>` — **RESUME** an existing session; **works with `-p` and RESTORES context**.
  **✓run** (created a session, `--resume` recalled the codeword end-to-end).
- `-c, --continue` — continue most recent conversation in the cwd. **(help)**
- `--fork-session` — on resume, branch to a new id. **(help)**
- `--no-session-persistence`. **(help)**
- **Scope:** sessions are **cwd(project)-scoped** under `CLAUDE_CONFIG_DIR`; `--resume`
  needs the same cwd + config dir. **✓run**
- **Correct reuse pattern:** turn1 `--session-id <uuid>` → turn2+ `--resume <uuid>`.
  (Reusing `--session-id` for turn2 is create-semantics and errors — this was the cc bug.)

### Subcommands (help): `agents`, `mcp`, `config`, `plugin`, `update`, `doctor`, `/skill-name`.

### Hub usage
`claude.cmd --safe-mode --append-system-prompt "<IPC frame>" -p {stdin} --dangerously-skip-permissions`
+ profile `--model/--effort`. Reuse now via `--resume` (fixed 2026-07-02). Env:
`CLAUDE_CONFIG_DIR=_sys/claude/config`.

---

## 2. codex.cmd — codex-cli **0.144.6** (peer `cx`)

Path: `_sys/env/nodejs/npm-global/codex.cmd`. Subcommand-based; bare = interactive.

### Subcommands (from `--help`, **✓run**)
`exec`(e), `review`, `login`/`logout`, `mcp`, `plugin`, `mcp-server`, `app-server`,
`remote-control`, `app`, `completion`, `update`, `doctor`, `sandbox`, `debug`, `apply`(a),
`resume`, `archive`/`unarchive`/`delete`, `fork`, `cloud`, `exec-server`, `features`.

### Non-interactive (hub path)
- `codex exec <prompt|->` — non-interactive run; `-` = stdin. **✓run**
- `codex exec resume <SESSION_ID|thread-name> [prompt|-]` / `--last` — **resume + RESTORES
  context**. **✓run** (recalled codeword; UUIDs take precedence over names).
- `--json` — JSONL event stream (`thread.started`, `token_count`, `item.completed`…). **✓run**
- `-c key=value` — TOML config override (e.g. `-c sandbox="workspace-write"`,
  `-c model_reasoning_effort="high"`). **✓run** (`exec resume` rejects `-s`, needs `-c`)
- `--ignore-rules`. **✓run** (available, not used by the hub W6 least-privilege path)
- `app-server` — JSON-RPC daemon; `account/rateLimits/read` returns 5h/weekly quota.
  **✓run** (diag consumes for live quota).
- `features list` — feature flags (`plugins`, `apps`, `workspace_dependencies` = stable/true…).
  **✓run** (note: `--disable plugins` does NOT stop skill loading — **✓run**).

### Session id
= codex's **real thread id** parsed from the `thread.started` JSONL event (not a hub uuid).
**✓run** (that is why cx reuse works reliably).

### Context source
Live context from the newest thread **rollout JSONL** `event_msg/token_count`
(`model_context_window` + `last_token_usage.total_tokens`); sqlite `threads.tokens_used`
is cumulative, NOT current occupancy. **✓run**

### Known quirk
Each `codex exec` loads the plugin/skill marketplace (~605 SKILL.md) → logs
`Exceeded skills context budget of 2% … 1352 skills not included` every call =
per-invocation startup overhead. Benign but slows first token. **✓run**

### Hub usage
`codex exec - --json -c sandbox="workspace-write"` (+ profile `--model`,
`-c model_reasoning_effort`). Reuse: `exec resume <thread-id> - …`. Env:
`CODEX_HOME=_sys/codex/config` (must be pinned — see specific/cx.md).

### cx — additional verified surface (2026-07-23)
- `codex exec --output-schema <FILE>` exposes JSON Schema-constrained final-response output.
  Installed surface confirmed live; schema enforcement itself not exercised. `[cli_live]`
- `codex debug prompt-input` renders the exact model-visible prompt context as JSON without a
  model call — use for directive-injection / context-bloat regression tests. **✓run**
- `codex doctor --json` returns a redacted install/config/auth/runtime/sandbox report. Took
  `31.7s` in this audit — periodic/on-failure diagnostic, not per-ask. **✓run**
- `--strict-config` rejects unrecognized `config.toml` fields — useful CLI-version-change
  canary. **✓run**
- `-p, --profile <NAME>` layers `$CODEX_HOME/<NAME>.config.toml`; explicit CLI flags still
  take precedence. **✓run**
- `--ephemeral` runs without persisting session files — suitable for disposable canaries. **✓run**
- `codex review --uncommitted` / `--base <BRANCH>` / `--commit <SHA>` — dedicated review
  routes when the target is already known. **✓run**
- `codex login status` — confirmed positive-path auth preflight (`exit 0`, "Logged in using
  ChatGPT"); logged-out negative path not tested. `[cli_live]`
- `codex debug models` vs `codex debug models --bundled` — refresh-vs-bundled drift signal
  (this audit: 7 refreshed vs 8 bundled, `gpt-5.2` bundled-only). Neither carries a freshness
  timestamp/provenance field — catalog freshness cannot be proven from either alone. **✓run**
- App-server `config/read` — 97 effective config keys + origin metadata, stronger
  effective-state evidence than reading `config.toml` directly. `[app_server]`
- App-server `thread/list` — recovers persisted exec threads from the state DB with
  pagination, avoiding raw SQLite/rollout-JSONL scanning. `[app_server]`
- Codex hooks can inspect/block Bash, `apply_patch`, MCP, prompt, and stop events; docs note
  some tool paths may opt out, so hooks alone are not a complete enforcement boundary. `[declared, unverified]`

> **Flagged follow-up — runtime MCP inventory drift:** `codex mcp list --json` returned `[]`,
> while app-server `mcpServerStatus/list` reported one effective server, `codex_apps`, with
> `192` tools and bearer-token auth. `codex mcp list` is NOT a complete runtime-capability
> inventory in this installation — hub capability checks should use `mcpServerStatus/list`
> instead. `[cli_live + app_server]`

> **Flagged follow-up — wrapper command drift:** `_sys/cli/peer_console.py::_CODEX_COMMANDS`
> omits the installed `delete` root subcommand (every other installed root command IS
> represented). Functional impact unprobed — hub invokes `codex exec` directly, not `codex
> delete`. This is a code follow-up, not a doc-only issue. `[empirical_probe]`

---

## 3. agy.exe — Antigravity **1.1.5** (peer `ag`)

Path: `_sys/tools/agy/agy.exe`. Go binary; Windows Console API (needs a real console/PTY).

### Modes & flags (`--help`, **✓run**)
- `-p, --print` / `--prompt` — single prompt non-interactively. **✓run** (requires a real console or PTY; see the console warning below)
- `-i, --prompt-interactive` — run an initial prompt, then continue interactively. **(help)**
- `--conversation <ID>` — resume an existing conversation by agy's own ID. **✓run**
- `-c, --continue` — continue the most recent conversation. **(help)**
- `--model <MODEL>` — select a canonical model operand listed by `agy models`. **✓run**
- `--effort <low|medium|high>` — select reasoning effort. **(help)**
- `--mode <accept-edits|plan>` — select execution or planning mode. **(help)**
- `--agent <NAME>` — select a named agent. **(help)**
- `--sandbox`, `--dangerously-skip-permissions` — permission-related controls. **(help)** Their effective enforcement in the hub's non-interactive invocation remains unmeasured; see "Known gaps" in §4.
- `--add-dir <PATH>` — add a directory to the working set. **(help)**
- `--project`, `--new-project` — select or create a project. **(help)**
- `--print-timeout <DURATION>` — non-interactive timeout; default `5m0s`. **(help)**
- `--log-file <PATH>` — write CLI logs to a file. **(help)**

### Subcommands (`--help`, **✓run**)
`models`, `agent`/`agents`, `plugin`, `install`, `update`, `changelog`, `help`. (No `--models`
flag — use the `models` subcommand.) **✓run**

- `agy agent` and `agy agents` list the available named agents. **✓run**
- `agy plugin` exposes `list`, `import`, `install`, `uninstall`, `enable`, `disable`,
  `validate`, and `link`. **✓run** for the live command surface; individual mutations were
  not exercised.
- `agy plugin import gemini` / `agy plugin import claude` import existing Gemini CLI or
  Claude Code skill packages. **(help)**
- `agy plugin validate [PATH]` performs pre-install manifest validation. **(help)**

### Models and live auth preflight (`agy models`, **✓run**) — DUAL model families
Canonical, live-current `--model` operands (2026-07-23), lowercase/hyphenated — **replaces**
the old display-name strings (`Gemini 3.5 Flash (Low)` etc.) that `orchestration.json`
previously stored and that Agy 1.1.5 now rejects (fixed same date):
`gemini-3.6-flash-{high,medium,low}`, `gemini-3.5-flash-{high,medium,low}`,
`gemini-3.1-pro-{high,low}`, **`claude-sonnet-4-6`**, **`claude-opus-4-6-thinking`**,
`gpt-oss-120b-medium`.
→ ag's `3p-*` quota = the non-Gemini (Claude/GPT-OSS) models. (Enables D3.)

`agy models` is also a confirmed zero-model-call **live authentication preflight**. Before a
2026-07-23 relogin it exited `1` with `Error: Please sign in to view available models. Launch
the CLI without arguments to sign in.`; after relogin the identical command exited `0` with the
full catalog above — the expired-token-fails / valid-token-succeeds pair that proves this. `[cli_live, cross-session evidence]`

### Changelog-revealed automation surface (2026-07-23)
`agy changelog` (**✓run**) declares additional automation controls; their behavioral effects
were not independently exercised in the hub yet. `[declared, unverified]`
- `AGY_CLI_DISABLE_LATEX` — disables LaTeX formatting, intended to prevent ANSI corruption in
  captured logs.
- `AGY_CLI_HIDE_ACCOUNT_INFO` — suppresses email/plan info from output headers.
- `UseG1Credits` — controls automatic fallback-credit use.
- Centralized project cache at `~/.gemini/antigravity-cli/cache/projects.json`.

Candidate hub wiring: `AGY_CLI_DISABLE_LATEX=1` + `AGY_CLI_HIDE_ACCOUNT_INFO=1` for cleaner,
less account-revealing automated output. Validate live effects before treating as enforced.

### Session / resume — verified reality
- agy assigns its **OWN conversation id** (the `conversations/*.db` filename) and
  **IGNORES an injected `--conversation <uuid>`** that doesn't already exist. **✓run**
  (the injected id never appears as a `.db`; agy makes its own).
- The real id is **not** surfaced to `-p` output or `status.json` (only in `brain/`/`log/`
  and the interactive `Resume: agy --conversation=<id>` hint). **✓run**
- ⚠️ **agy REQUIRES a console (real or pseudo).** Its Windows Console-API writes
  block when the process has **no console at all**. **✓run + user-confirmed:**
  - In a real interactive PowerShell, `agy -p "…"` returns fast **whether or not
    stdout is redirected** (`> file`) — so `-p`, stdout-redirect, and
    `--dangerously-skip-permissions` are **NOT** the cause (A/B: both flag variants
    identical).
  - In a **headless automation harness (no console)**, direct `agy -p` hangs
    indefinitely (my earlier "5-min hang" was this artifact, NOT an agy/hub defect).
  - The **hub uses winpty (pseudo-console)**, which satisfies this — short ag IPC
    asks complete in ~13–26 s. Long `ag.deepthink` slowness is a separate
    reasoning-latency/skill-load issue, not the console requirement.
- **Session reuse — WORKS (VERIFIED end-to-end 2026-07-02):** the hub CREATE turn omits
  `--conversation` (agy mints its own id); `AgyAdapter.extract_session_id` captures that
  id as the **newest `conversations/<id>.db` stem**; the next turn resumes via
  `--conversation <that-id>`. Verified: a 2-ask hub probe reused the same id
  (`df2f224b…`) and **recalled the codeword**. Caveat: "newest .db" relies on ag asks
  being serialized (lease) and the durable home not being churned by a concurrent
  interactive session.

### Hub usage
`agy.exe --dangerously-skip-permissions -p {query} --print-timeout 60m` driven via
**winpty PTY** (bypasses the `agy.bat`/`agy_entry.py` context-fill). Env:
`AGY_CONFIG_HOME`/`GEMINI_DIR=_sys/antigravity/config` (durable home; no active
`ipc_stateless_home`).

---

## 4. Cross-cutting

### Session reuse matrix (execution-verified 2026-07-02)
| Peer | CLI resume mechanism | Restores context in non-interactive? | Status |
|------|----------------------|--------------------------------------|--------|
| cx | `codex exec resume <real-thread-id>` | **Yes** | ✅ works |
| cc | `claude --resume <id>` (turn1 `--session-id`) | **Yes** (with `-p`) | ✅ fixed 2026-07-02 |
| ag | `agy --conversation <agy-own-id>` (hub captures the id from newest `conversations/<id>.db`) | **Yes** (verified) | ✅ works 2026-07-02 |

### Session create-vs-reuse scenarios (per peer)
Session scope key = `<explicit_scope | room_id | default>:<peer.profile>` (e.g.
`room-ce75:cc.effort`). The hub logic is **general** (same for all peers); the CLI
resume flag is peer-specific (matrix above).

**RESUME (reuse existing) — requires ALL of:**
1. peer `session_mode: reuse` (cc/cx/ag all are) and `--session-policy` = `auto`/`reuse`.
2. an **active** session stored for that exact `scope_key`.
3. **fingerprint matches** — `session_fingerprint` (invoke path + invoke_args +
   profile_args) unchanged since the session was created.
4. the CLI resume itself succeeds (cx `exec resume` / cc `--resume` / ag
   `--conversation <captured-id>`).

**CREATE (new session) — any ONE triggers it:**
| Trigger | Applies to | Note |
|---|---|---|
| First ask in the scope (no active session) | all | normal cold start |
| `--session-policy fresh` or `none` | all | explicit force-new |
| **Fingerprint drift** (model/profile/flags changed) | all | retires + recreates that scope |
| **Different scope**: different room, or different **profile** (`cc.standard` vs `cc.deepthink` are separate sessions) | all | scope_key differs |
| `new-topic` / `clear-room` | cx, gc, cc, **ag** (ag added 2026-07-02) | retires the peer's sessions |
| **resume failed** (permanent) | all | retire → fresh (e.g. cc pre-`--resume`; stale/missing id) |
| Different working directory (`cwd`) | **cc** | claude sessions are cwd(project)-scoped |
| newest-`.db` misidentified (concurrent interactive churn) | **ag** | capture assumes serialized asks |

**Per-peer id source (what gets stored/reused):**
- **cx** — codex's real `thread.started` id (parsed from JSONL).
- **cc** — the uuid the hub set via `--session-id` on turn 1 (claude honors it; `--resume` finds it), cwd+`CLAUDE_CONFIG_DIR`-scoped.
- **ag** — agy's own id, captured as the newest `conversations/<id>.db` stem.

**Resume-failure recovery (stale/invalid stored id) — same NET result, different site:**
- **cx / cc (non-PTY path):** the hub detects a failed resume (nonzero exit on a
  resume attempt), classifies it (`_classify_resume_failure`), and on *permanent*
  failure **retires the session and retries fresh**; *transient* keeps it for retry.
- **ag (PTY path):** the hub has **no** explicit resume-failure branch — and does not
  need one: agy **silently ignores an unknown `--conversation <id>` and starts fresh**
  (verified), so the ask still succeeds (exit 0) and `extract_session_id` re-captures
  the new `.db` id → self-heals. Net effect (failed resume → fresh + continue) matches
  cc/cx; only the mechanism differs (agy self-recovers vs hub-managed).
- The rest of the session policy (reuse-enable, scope key, fingerprint-drift retire,
  new-topic/clear-room clearing, persist lifecycle) is **uniform across all peers**.

### PATH shadowing (important for programmatic calls)
`_sys/cli` is first on PATH, so a **bare** `codex`/`agy`/`claude` (and Windows
`shutil.which("codex")` via PATHEXT → `_sys/cli/codex.bat`) resolves to **our wrapper**,
which runs the heavy `*_entry.py` (hub init-session + context-fill). This shadowing was
the real root of the `diag --json` stall. **Programmatic/host code must call the full
binary path**, never the bare name. **✓run** (diag fixed to use the real `codex.cmd`).

### Known gaps (2026-07-23)
Not yet measured — do not infer behavior from declarations/help output alone:
- `codex exec`'s effective approval policy under the hub's non-interactive invocation.
  `doctor` reports config default `OnRequest`; the hub supplies no override. `[cli_live context; behavior not yet measured]`
- Codex `fork`, `archive`, `unarchive`, `delete`, app-server `turn/steer`/`turn/interrupt`, and
  `--output-schema` enforcement — declared/help-visible, not behavior- or mutation-tested. **(help)**
- App-server `account/usage/read` — recognized, but live fetch failed via this session's
  proxy; unconfirmed, not unsupported. `[app_server; TEST NEEDED]`
- ag permission-rule enforcement under non-interactive `-p --dangerously-skip-permissions` —
  a prior probe (DIR-002, 2026-06-23) found `--sandbox` does not enforce filesystem
  confinement and `--dangerously-skip-permissions` is an absolute override; the combined
  allow/deny/ask-rule behavior itself remains untested. `[empirical_probe; TEST NEEDED]`
- The installed `claude.cmd` was not independently re-verified this round for
  `--json-schema`, `--output-format stream-json`, `--input-format stream-json`,
  `--max-turns`, `--no-session-persistence`, or `--mcp-config` — official-doc declarations
  even where already listed above. `[declared, unverified]`

### Common non-interactive invocation forms (verified)
- claude: `claude -p - --resume <id> --dangerously-skip-permissions`
- codex:  `codex exec resume <id> - --json -c sandbox="workspace-write"`
- agy:    `agy --dangerously-skip-permissions -p "<q>" --print-timeout <t>` — **requires a
  console**: fine interactively / via hub winpty; hangs only in a headless (no-console)
  harness. Not related to the flag or stdout redirect (user-verified).

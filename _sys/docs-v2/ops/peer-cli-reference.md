# Ops — Peer CLI Reference (execution-verified)

> Created: 2026-07-02 | Method: `--help` **plus actual execution** of each CLI.
> Legend: **✓run** = verified by running it this audit; **(help)** = documented in
> `--help`, not separately exercised. Binaries are the REAL ones under
> `_sys/env/nodejs/npm-global/` and `_sys/tools/agy/`, NOT the `_sys/cli` wrappers
> (which shadow bare names on PATH — see §4).

Cross-ref: `general/lifecycle.md` (session/heartbeat), `specific/{cc,cx,ag}.md`,
`ops/diag-telemetry-architecture.md`, `ops/cli-update-checkpoints-{cc,agy,codex}.md`
(known bugs + mechanical post-update verification checklists, 2026-07-24).

---

## 1. claude.cmd — Claude Code **2.1.216** (peer `cc`)

Path: `_sys/env/nodejs/npm-global/claude.cmd`. Default = interactive; `-p/--print`
= non-interactive one-shot.

### Modes & core flags
- `-p, --print` — non-interactive print. **✓run**
- prompt via stdin (`-`) or arg. **✓run** (hub uses stdin)
- `--dangerously-skip-permissions` — bypass permission prompts. **✓run**
- `--model <m>`, `--effort <level>` — model/effort for the session. **✓run** (hub profile_args)
- `--append-system-prompt <p>`, `--system-prompt-file` — inject system prompt. **✓run** (hub IPC frame)
- `--output-format <text|json|stream-json>` — **✓run 2026-08-08**: `claude.cmd -p "<prompt>"
  --output-format json` returns one flat JSON object on stdout, e.g.
  `{"is_error":false,"duration_api_ms":...,"stop_reason":"end_turn","session_id":"...",
  "total_cost_usd":...,"usage":{...},"modelUsage":{...},"result":"<response text>",
  "type":"result","uuid":"..."}` — the response text is in `"result"`, success is
  `"is_error": false`. Closes the prior `[declared, unverified]` gap noted below (§4 Known
  gaps). Used as the parse target for peerhub's `RealClaudeAdapter`
  (`peerhub/adapters/claude_adapter.py`). `--input-format`, `--include-partial-messages`
  remain **(help)**.
- `--json-schema <inline JSON string>` (structured output) — **✓run 2026-07-23**: takes the
  raw JSON Schema string directly (NOT a file path — passing a path errors
  `... is not valid JSON`). A live `--model haiku --output-format json --json-schema '{...}'`
  call returned a top-level `structured_output` field containing the schema-validated parsed
  object, alongside `result` (the same content as a JSON string). Confirmed real enforcement,
  not a no-op. `[cli_live]`
- `--max-budget-usd <amount>` — **✓run 2026-07-23**: a genuine hard stop. When the running
  cost exceeded the cap mid-call, the process exited `1` with
  `subtype: "error_max_budget_usd"`, `terminal_reason: "budget_exhausted"`,
  `errors: ["Reached maximum budget ($X)"]`. `[cli_live]`
- `--agents <json>`, `--mcp-config <...>`, `--add-dir`, `--settings`, `--plugin-dir`. **(help)**
- `--bare` — minimal mode (skip hooks/LSP/plugin-sync/auto-memory/keychain reads). **✓run
  2026-07-23**: confirmed it genuinely disables OAuth/subscription auth — a `--bare` call with
  no `ANTHROPIC_API_KEY` failed immediately with `"Not logged in · Please run /login"` even
  though the normal subscription session is authenticated. Matches the help text's claim that
  `--bare` is strictly `ANTHROPIC_API_KEY`/`apiKeyHelper`-only. `[cli_live]`
- `--safe-mode` — used by hub invoke_args. **(help)**
- `--effort <low|medium|high|xhigh|max>` — **(help)** (doc's "core flags" line already lists
  `--effort` generically; exact accepted values confirmed via `--help` 2026-07-23).

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

### Subcommands (`--help`, **✓run 2026-07-23**, free/no-API-call)
`agents`, `auth`, `auto-mode`, `doctor`, `gateway`, `install`, `mcp`, `plugin`/`plugins`,
`project`, `setup-token`, `ultrareview`, `update`/`upgrade`. (Doc previously listed `config`
and `/skill-name` as top-level — `config` is not a real top-level command in 2.1.216; skills
are invoked as `/skill-name` only inside a session, not a CLI subcommand.)

- `claude auth` — `login`, `logout`, `status`. `status --json` is the zero-cost live auth
  preflight (already used this session: `loggedIn`/`authMethod`/`apiProvider`/`email`/`orgId`/
  `subscriptionType`).
- `claude mcp` — `add`, `add-from-claude-desktop`, `add-json`, `get`, `list`, `login`,
  `logout`, `remove`, `reset-project-choices`, `serve`.
- `claude plugin`/`plugins` — `details`, `disable`, `enable`, `eval`, `init`/`new`,
  `install`/`i`, `list`, `marketplace`, `prune`/`autoremove`, `tag`, `uninstall`/`remove`,
  `update`, `validate`.
- `claude project` — `purge [path]` (deletes all Claude Code state for a project: transcripts,
  tasks, file history, config entry). Destructive — never call from hub automation.
- `claude doctor` — health check, reads settings without a trust prompt.
- `claude agents [--json]` — lists active/background sessions as JSON for scripting
  (`--json` does not require a TTY).
- `claude ultrareview [options] [target]` — cloud-hosted multi-agent review of the current
  branch or a PR/base branch; billed, user-triggered only (matches this assistant's own
  standing instruction to never launch it autonomously).

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

**Second known quirk (2026-08-08, ✓run):** `codex exec "<prompt>"` invoked from a plain
subprocess with an inherited/attached stdin (not redirected) prints
`Reading additional input from stdin...` and waits for stdin EOF before proceeding — appeared
as an indefinite hang in one investigation until stdin was explicitly redirected
(`stdin=subprocess.DEVNULL` in Python, `< /dev/null` in a shell), which resolves it
immediately with a clean exit 0. This is intentional design (lets you pipe extra context in),
not a bug — any real subprocess-based caller (e.g. a future peerhub `codex.cmd` adapter) must
close/redirect stdin explicitly, the same way the existing hub path already does via `-`.

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

### cx — Round 4: approval/mutation/schema live verification + nested command trees (2026-07-23)

**Approval policy.** With no `-a/--ask-for-approval` override (matching the hub's real
invocation), `codex doctor --json` resolves the effective policy to `OnRequest`; app-server
`config/read` returns `approval_policy = null` with no origin, confirming this is codex's
built-in default, not a config-file value. `[cli_live + app_server]` Values: `-a` accepts
`untrusted` (prompts outside the trusted-command set), `on-request` (agent decides when to
ask), `never` (fails instead of prompting).

**RESOLVED 2026-07-23 (forensic follow-up):** the earlier "TLS/env-blocked" classification was
incomplete. Root cause fully isolated: this is **Codex's own intentional Windows sandbox**, not
a hub.py restriction, not host-wide, and not domain-specific. `installed config.toml` declares
`[windows] sandbox = "unelevated"`; commands Codex itself spawns (not the outer inference
transport) run under a genuinely restricted Windows token
(`TokenElevationType=3/limited`, `TokenIsRestricted=1`, deny-only Administrators) plus
advisory proxy-poisoning env vars (`HTTP_PROXY=http://127.0.0.1:9` etc.,
`CODEX_SANDBOX_NETWORK_DISABLED=1`). Direct evidence: a zero-proxy Schannel curl from INSIDE a
dispatched cx session failed identically (`SEC_E_NO_CREDENTIALS`) against ALL five test targets
including a plain control domain, while Node's own TLS stack (which ignores those proxy vars)
reached every one of them with normal HTTP responses — proving general connectivity exists and
the restriction is specific to the sandboxed child-command TLS stack, not the network path.
Matches OpenAI's own documented design for this sandbox mode (network protection is explicitly
"advisory" since a program can ignore the env vars or open sockets directly) — see
[OpenAI's Windows sandbox engineering post](https://openai.com/index/building-codex-windows-sandbox/).
`[cli_live + empirical_probe + official design]`
**Disposition: correctly classified as security-intentional — do NOT weaken or bypass this to
"fix" it.** A live approve/deny/prompt event for a borderline command genuinely cannot be
observed from inside a nested peer-dispatched session (this execution context
also resolves to approval policy `never`, i.e. it would auto-fail rather than prompt anyway).
Closing this requires launching Codex directly from a normal, non-nested host process — not
another peer `ask`.

**`--output-schema` — confirmed not a no-op.** A malformed schema file is rejected locally
before any provider call (`... is not valid JSON: expected value at line 4 column 1`); a valid
schema is accepted and starts a real turn. `[cli_live]` End-to-end response-conformance
validation is blocked by the same Codex sandbox mechanism as the approval-policy test above
(security-intentional, not a bug) — needs a non-nested normal-host execution to close.
`[empirical_probe; blocked by Codex's own unelevated-sandbox design, see above]`

**Mutation surface — fully behavior-verified on a disposable, current-round-only session**
(never touched a real hub-managed room session): app-server `thread/fork` succeeded
(`forkedFromId` matched exactly); CLI `archive` → `unarchive` → `delete` round-tripped
cleanly on the forked child; app-server `turn/steer` returned a real `turnId`; `turn/interrupt`
returned success followed by `turn/completed status:"interrupted"`; post-delete reads on both
the fork and the disposable source correctly returned "thread not loaded". `[cli_live + app_server]`
Top-level CLI `codex fork` (not the app-server RPC) failed in this headless harness with
`Error: stdin is not a terminal` — a real-TTY requirement, the same class of environment
limitation as agy's console requirement (§3). Needs a real interactive terminal to close.

**`account/usage/read`** — recognized by app-server and attempts the real
`https://chatgpt.com/backend-api/wham/profiles/me` endpoint. **ROOT CAUSE CONFIRMED 2026-07-23**
(see the approval-policy entry above for the full forensic trail): this is Codex's own
intentional `[windows] sandbox = "unelevated"` restricted-token boundary applied to spawned
commands, matching OpenAI's documented design — not a hub.py restriction, not host-wide, not
domain-specific (a control domain failed identically). The endpoint itself IS reachable (a
direct terminal curl with no proxy vars got a real `HTTP 401`); only the nested sandboxed TLS
stack cannot complete the handshake. **Verdict: security-intentional by-design boundary, not an
absent/unsupported Codex capability and not something to bypass.** Real payload capture
requires running from a normal non-nested host process. `[app_server + empirical_probe + official design]`

**Corrected nested command trees** (supersedes any prior partial listing):
- `codex mcp`: `list`, `get`, `add`, `remove`, `login`, `logout`. (`add-from-claude-desktop`,
  `add-json`, `reset-project-choices`, `serve` do **not** exist in codex-cli 0.144.6 — do not
  document them as real subcommands.) `[cli_live]`
- `codex debug`: `models`, `app-server` (→ `send-message-v2`), `prompt-input`. `[cli_live]`
- `codex app-server`: `daemon` (Unix-only, see §2 above), `proxy`, `generate-ts`,
  `generate-json-schema`; transport flags include `--listen`, `--stdio`,
  `--analytics-default-enabled`, `--ws-*` auth options. `[cli_live help surface]`
- `codex plugin`: `add`, `list`, `marketplace`, `remove`.
- `codex features`: `list`, `enable`, `disable`.
- `codex cloud` (experimental): `exec`, `status`, `list`, `apply`, `diff`.
- `codex doctor` also has `--summary`, `--all`, `--no-color`, `--ascii`.
- `codex sandbox` also has `-P/--permission-profile`, `--include-managed-config`,
  `--sandbox-state-json`, `--sandbox-state-readable-root`, `--sandbox-state-disable-network`.
- Global/top-level flags not previously documented: `-a/--ask-for-approval`, `--search`
  (native live web-search tool), `--dangerously-bypass-approvals-and-sandbox`,
  `--dangerously-bypass-hook-trust` (both forbidden in hub-managed asks), `--remote <ADDR>` +
  `--remote-auth-token-env`, `-i/--image`, `--oss`/`--local-provider`, `-C/--cd`,
  `--no-alt-screen`. `codex exec` also has `--ignore-user-config`, `--skip-git-repo-check`,
  `--color`, `-o/--output-last-message`.

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
- `--sandbox` — does NOT enforce filesystem confinement (DIR-002, 2026-06-23, **✓run**).
- `--dangerously-skip-permissions` — **✓run 2026-07-23, CONFIRMED ABSOLUTE OVERRIDE**: a
  controlled test created a scratch dir + explicit `deny` rules (`read_file(secret-marker.txt)`,
  `command(echo DENIED_TEST_COMMAND)`) in a project-level `settings.json`/`rules.json` (schema:
  `{"permissions":{"deny":["action(target)", ...]}}`, precedence `Deny > Ask > Allow`, per
  official docs at `antigravity.google/docs/cli-permissions`). With
  `--dangerously-skip-permissions` passed, the denied action proceeded with **zero** rule
  evaluation (log evidence: no rules.json read, no prompt, immediate bypass) — the flag is a
  true unconditional override; declarative deny rules provide **no** defense-in-depth against
  it. `[cli_live]` This closes the prior "unmeasured" gap definitively.
- `--add-dir <PATH>` — add a directory to the working set. **(help)**
- `--project`, `--new-project` — select or create a project. **(help)**
- `--print-timeout <DURATION>` — non-interactive timeout; default `5m0s`. **(help)**
- `--log-file <PATH>` — write CLI logs to a file. **(help)**
- `--output-format <text|json|stream-json>` — **✓run 2026-08-08** (previously undocumented in
  this reference): `agy.exe -p "<prompt>" --output-format json` runs synchronously (does NOT
  block on stdin, unlike codex — see codex's Known quirk below), exits 0, and returns one flat
  JSON object, e.g. `{"conversation_id":"...","status":"SUCCESS","response":"<text>",
  "duration_seconds":...,"num_turns":1,"usage":{"input_tokens":...,"output_tokens":...,
  "thinking_tokens":...,"cache_read_tokens":...,"total_tokens":...}}` — response text is in
  `"response"`. No hub.py or ambient noise in the raw output when invoked directly (outside
  hub.py). Used as the parse target for peerhub's `RealAgyAdapter`
  (`peerhub/adapters/agy_adapter.py`).

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
The 2026-07-27 catalog still prints fully materialized lowercase/hyphenated model variants:
`gemini-3.6-flash-{high,medium,low}`, `gemini-3.5-flash-{high,medium,low}`,
`gemini-3.1-pro-{high,low}`, **`claude-sonnet-4-6`**, **`claude-opus-4-6-thinking`**,
`gpt-oss-120b-medium`. These replace the old display-name strings (`Gemini 3.5 Flash
(Low)` etc.), which Agy 1.1.5 rejects.

For the configured `ag.*` profiles, live invocation establishes the current argument
contract: use the base model plus `--effort` where supported
(`gemini-3.6-flash --effort low|high`, `gemini-3.1-pro --effort high`, and
`gpt-oss-120b --effort medium`). The exception is
**`claude-opus-4-6-thinking`**: invoke that Thinking variant without `--effort`; the CLI
rejects an effort flag for it. See `specific/ag.md` for the authoritative profile matrix.
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
`shutil.which("codex")` via PATHEXT → legacy `codex.bat` wrapper, removed in separation) resolved to **our wrapper**,

which runs the heavy `*_entry.py` (hub init-session + context-fill). This shadowing was
the real root of the `diag --json` stall. **Programmatic/host code must call the full
binary path**, never the bare name. **✓run** (diag fixed to use the real `codex.cmd`).

### Known gaps (2026-07-23, after Round 4 — resolved items removed, only genuinely open ones remain)

**Resolved this session (kept here only as a changelog, not open questions):** cc
`--json-schema`/`--max-budget-usd`/`--bare` real enforcement (✓run); ag
`--dangerously-skip-permissions` vs deny-rules (✓run, confirmed absolute override); codex
approval-policy *default value* (✓ `OnRequest`, cli_live+app_server); codex mutation surface
(fork/archive/unarchive/delete/steer/interrupt via app-server + CLI, all ✓run); codex
`--output-schema` *local parsing* (✓run — rejects malformed JSON pre-provider-call); codex
`account/usage/read` AND the live-approval-event / end-to-end-schema-conformance TLS failures
**root-caused with full forensic confirmation** (2026-07-23 follow-up): this is Codex's own
intentional `[windows] sandbox = "unelevated"` restricted-token boundary on spawned commands
(matches OpenAI's documented design), reproduced by a control-domain probe failing identically
inside the sandbox while succeeding via Node's TLS stack and a plain terminal curl outside it.
**Correctly classified as security-intentional — not a bug, not to be bypassed.**

**Resolved 2026-08-08 (separate incident, kept here as changelog):** cx's Windows sandbox
bootstrap failed on every dispatch with `windows sandbox: helper_unknown_error: apply
deny-read ACLs`, blocking any file read/listing/executable discovery (non-filesystem
operations like `Get-Location`/`Write-Output` still worked, which is what made this look like
a partial/intermittent failure rather than a hard block). Root cause: the persistent sandbox
state file (historically `.sandbox/deny_read_acl_state.json` under codex config) was 22 bytes of raw null
bytes (not valid JSON) — confirmed via the sandbox's own `setup_error.json` and dated log

(`.sandbox/sandbox.<date>.log`: `parse deny-read ACL state ... : expected

value at line 1 column 1`), likely from an interrupted/crashed write. Fix: move the corrupted
file aside (do not delete outright — keep as `.corrupted-backup-<date>` in case the exact
prior state mattered) and let Codex's setup binary regenerate a fresh one on next bootstrap.
Verified fixed same session (a follow-up dispatch read a real file with zero error). **Not**
caused by, and does not require changing, the `[windows] sandbox = "elevated"` mode setting in
`config.toml` — that setting was a red herring, the file was simply corrupted. Diagnostic
recipe for a recurrence: check `.sandbox/setup_error.json` for the current error → tail
`.sandbox/sandbox.<today>.log` for the full error chain and the exact failing file path →
inspect that file directly (`wc -c` + hex dump) for corruption before assuming a deeper cause.

**Still genuinely open — blocked by structural/environment limits that further peer-ask rounds
cannot close (each needs a normal non-nested host process or a real interactive terminal — the
peer itself correctly refused to weaken its own sandbox to "test around" it):**
- Live approve/deny/prompt event for a borderline codex command, and end-to-end
  `--output-schema` response conformance — both require running Codex directly from a
  non-nested host process, since the nested peer-dispatch context is intentionally
  network-restricted by Codex's own Windows sandbox. `[empirical_probe; needs non-nested host]`
- Top-level CLI `codex fork` (not the app-server RPC, which IS verified) — fails headless with
  `Error: stdin is not a terminal`; needs a real TTY, same class of limitation as ag's console
  requirement. `[cli_live; needs real terminal]`
- `claude.cmd --output-format json` was verified live 2026-08-08 (see §1 above, closes that
  part of this gap). Still unexercised: `--output-format stream-json`, `--input-format
  stream-json`, `--max-turns`, `--no-session-persistence`, and `--mcp-config` remain
  `[declared, unverified]` — help-surface confirmed, live behavior not yet exercised.

### Version baseline captures (for future version-diff audits)
Full verbatim `--help`/`--version` output for every peer CLI, captured 2026-07-23 at zero API
cost (help text never touches the model), stored under `_sys/docs-v2/ops/cli-baselines/`:
- `cc-2.1.216-help.txt` — top-level + `auth`/`mcp`/`doctor`/`plugin`/`project`/`agents` subtrees.
- `ag-1.1.5-help.txt` — top-level + `agent`/`plugin`/`install`/`update`/`changelog` subtrees.
- `codex-0.144.6-help.txt` — top-level + `exec`/`debug`/`review`/`mcp`/`app-server`/`doctor`/
  `archive`/`delete`/`fork`/`resume`/`plugin`/`sandbox`/`features`/`apply`/`cloud` subtrees.

**How to use for a future version bump:** re-run `<binary> --version` and `<binary> --help`
(+ same subcommand list) after any peer CLI update, diff against the matching file above, and
treat any flag/subcommand delta as a candidate `orchestration.json`/hub-adapter drift — this is
exactly the bug class that caused the 2026-07-23 ag model-ID incident (stale strings silently
rejected by a newer CLI). Version-string extraction for future audits: `claude --version`,
`agy.exe --version` (also in `agy --help`'s header), `codex --version` — all free, all `[cli_live]`.

### Common non-interactive invocation forms (verified)
- claude: `claude -p - --resume <id> --dangerously-skip-permissions`
- codex:  `codex exec resume <id> - --json -c sandbox="workspace-write"`
- agy:    `agy --dangerously-skip-permissions -p "<q>" --print-timeout <t>` — **requires a
  console**: fine interactively / via hub winpty; hangs only in a headless (no-console)
  harness. Not related to the flag or stdout redirect (user-verified).

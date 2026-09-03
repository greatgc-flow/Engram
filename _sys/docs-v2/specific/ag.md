# Specific — ag (AntiGravity)
> Delta-only from general/*. Status: ACTIVE (gc replacement).

---

## Permission Profile & Flags
```
agy --dangerously-skip-permissions -p {query} --print-timeout 60m
```
- **Inline prompt:** Uses inline `-p {query}`. `agy` ignores `-p -` (stdin).
- **`--print-timeout 60m`:** Child-process output ceiling so `agy` does not self-terminate before the hub's liveness guard fires. There is **no hard wall-clock deadline** (orchestration `timeout: 0`); liveness is governed by `zombie_timeout_sec` (silence-based; `protocol.json communication_policy.zombie_profile_map` — `standard`/`effort`=600s, `deepthink`=900s; corrected 2026-07-17, was stale at 7200s here). Since 2026-07-17, this window tightens to 300s once genuine PTY output has been observed past the init-noise floor (`_effective_zombie_timeout_sec()`, `hub.py`) — see `ops/closure-review-2026-07-17.md` Part B. The 300s `pty_lease_sec` is a lease-renew / orphan-cleanup window, **not** an execution deadline.
- **Windows PTY:** `agy` writes to Windows Console API. `requires_pty=true` is mandatory in `orchestration.json` (subprocess.PIPE hangs).

## Session & State (`session_mode: reuse`)
- **Durable home (verified 2026-07-01):** ag uses the durable config home
  (`AGY_CONFIG_HOME=config`). There is **no clean/stateless IPC home** —
  `ipc_stateless_home` is **not** configured in `peers.json` (an earlier design,
  now inactive; the `_prepare_ipc_stateless_home` code remains but is unused for ag).
- **A6 isolation via scoped id, not home-wipe:** `agy -p` auto-continues ambient
  state, so IPC asks are isolated by an explicit scoped `--conversation
  <room:ag.profile>` id (`AgyAdapter`), which pins the conversation instead of
  wiping the home. (Empirically a fresh scope does not inherit prior context.)
- **Session reuse — WORKS (VERIFIED end-to-end 2026-07-02):** agy owns its
  conversation id (the `conversations/<id>.db` filename; NOT stdout — confirmed by ag).
  So: CREATE turn omits `--conversation` (agy mints its own id) →
  `AgyAdapter.extract_session_id` captures the **newest `conversations/<id>.db` stem** →
  RESUME turn injects `--conversation <that-id>`. A 2-ask hub probe reused the same id
  and recalled the codeword. Caveat: "newest .db" assumes serialized ag asks (lease) +
  no concurrent interactive churn of the durable home.
  - **Console requirement (not slowness):** agy needs a console — fine via the hub's
    winpty (short asks ~13–26 s) and interactively; it only hangs in a **headless
    no-console harness** (an earlier "agy -p multi-minute" note was that artifact,
    retracted). `--dangerously-skip-permissions`/stdout-redirect are NOT factors.

## Runtime Profiles
| Profile | Runtime model | Effort |
|---|---|---|
| `ag.standard` | `gemini-3.7-flash-low` | embedded (no `--effort`) |
| `ag.effort` | `gemini-3.7-flash-high` | embedded (no `--effort`) |
| `ag.deepthink` | `Gemini 3.1 Pro (High)` | embedded (no `--effort`) |
| `ag.opus` | `claude-opus-4-6-thinking` (manual_only) | embedded (no `--effort`) |
| `ag.gptoss` | `gpt-oss-120b-medium` | embedded (no `--effort`) |

`agy`'s real `models` catalog (confirmed via `agy.exe models` and live prompt dispatches) only lists tier-suffixed slugs for every Gemini/gpt-oss entry (`gemini-3.7-flash-low/-high`, `gemini-3.6-flash-low/-medium/-high`, `gpt-oss-120b-medium`, etc.) — there is no bare `gemini-3.7-flash` or `gpt-oss-120b` entry, and none of these accept a separate `--effort` on top of the chosen slug. Every ag profile therefore passes a single `--model <exact catalog slug or display label>` with no `--effort` operand. **2026-08-17 update:** `ag.standard` and `ag.effort` bumped to `gemini-3.7-flash-low` and `gemini-3.7-flash-high` following live execution testing. `ag.deepthink` needs one further exception on top of this: `agy`'s `--model` flag requires the exact human-readable display label for that one catalog entry — `Gemini 3.1 Pro (High)` — not the slug form `agy models` prints (LL-20260731-001, incident 2026-07-31: the slug form silently fell back to agy's no-entitlement CCPA default with a clean exit code and no warning). Re-verify after any `agy.exe` update by grepping the freshest `cli-*.log` for `Propagating selected model override to backend` immediately after a live dispatch for each profile — a `defaulting to CCPA` line at process-startup, before auth completes, is normal transient noise seen on every profile's fresh server spawn and is not itself proof of a fallback; only a `Propagating...` line with the wrong label is. *(Note: `agy models` writes via Windows Console API. Model discovery requires a PTY).*

## Directory Layout & Entry
```
_sys/antigravity/
├── config/                 ← INTERACTIVE home (durable; never mutated by hub IPC)
│   ├── AGY.md              ← session instructions
│   ├── conversations/      ← durable session .db store (used by IPC too)
│   └── implicit/           ← durable implicit context
└── health.json             ← peer health (runtime-generated)
```
- **Entry:** `agy.bat` → `agy_entry.py` (peerhub package; removed from Engram in the Engram/peerhub separation)
- **Config Env:** `AGY_CONFIG_HOME`/`GEMINI_DIR` → `_sys/antigravity/config/` (durable; IPC uses the same home — no separate `ipc-config`).

## Context and Collaboration
*(Delta from general/protocol.md + general/lifecycle.md.)*
- **PTY transport:** ag is the only PTY peer — liveness is heartbeat-based (zombie timeout), not a hard process deadline; `ag.deepthink` may think silently for long stretches without being a hang.
- **IPC isolation via scoped id:** hub asks reuse the durable home but pin a scoped `--conversation <room:ag.profile>` id, so ag does NOT inherit prior interactive room context; collaboration context must travel in the ask envelope. (Actual history restore in `-p` mode is a pending CLI limitation — see Session & State.)

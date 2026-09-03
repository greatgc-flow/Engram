# ag Zombie Phenomenon — Deep-Dive & IPC Hygiene Fix (2026-07-18)

> Status: living | Follow-up to `ops/closure-review-2026-07-17-round2.md` Part B. Closes the investigation for now: origin of the specific incident is CONFIRMED, the causal mechanism remains UNRESOLVED, and a real, unrelated ~4-week-old bug was found and fixed along the way.

## Trigger

User asked to keep digging into the recurring zombie phenomenon, explicitly floating a new hypothesis: could a peer be recursively calling another peer/profile? Investigating that question surfaced a much bigger, unrelated finding first, then a second peer-dispatched round (cx.deepthink + ag.deepthink, explicitly instructed not to self-dispatch this time) resolved the immediate mystery's origin while leaving the deeper causal question open.

## Finding 1: peer-to-peer direct recursion — not supported

- `C:\Users\GREAT\.gemini\config\mcp_config.json` is empty — agy has no MCP server wiring that could let it invoke another AI system or `hub.py` directly.
- `GEMINI.md` (agy's equivalent of CLAUDE.md) explicitly instructs: "NOTE FOR IPC / SUBAGENT TASKS: ... SKIP THIS ENTIRE SECTION. Do NOT read these documents" — a deliberate guard against agy learning peer-call mechanics during a normal ask.

No evidence of ag directly self-invoking peer calls.

## Finding 2 (major, unrelated): the "single-use" IPC file design had been broken for ~4 weeks

While checking `ask_history.jsonl` for recursion evidence, found a 2-day-old staged file (`ag.opus-20260716011000-audit-c.txt`, from the 2026-07-16 mega-audit) had been silently re-dispatched, with zero visible indication it was a stale retry.

**Root cause**: `_is_ephemeral_query_file()` required the tag segment after the 14-digit timestamp to be EXACTLY 4 alphanumeric characters — matching only the literal `{rand4}` placeholder in `protocol.json`'s naming doc. In practice, essentially every dispatch all project (terminal and peers alike) used a descriptive tag instead (`r2a`, `zombie1`, `trial1`, `LP1`...), never exactly 4 chars. The "single-use, auto-deleted after read" design had silently never fired for most dispatches since 2026-06-20. Live count: 655 files accumulated in `_sys/ai/ipc/`.

**Fixed** (`c2f88e4`): broadened the tag-matching regex to any non-empty run; verified 302/655 existing files now correctly classify as ephemeral going forward, the remaining 353 genuinely lack a timestamp component and stay preserved by design (e.g. `ping-ag.txt`). Every staged-file reuse now prints an explicit console notice + telemetry (age-based warning). `diag`'s FRAME section now shows a live staged-file count. protocol.json and peer-rules.md docs corrected to match reality. The 655 pre-existing files were left in place (user's explicit choice), not bulk-archived.

## Finding 3 (statistically strong): reuse-after-failure is a much better zombie predictor than file age

Forensic pass (cx.effort) joined PTY telemetry to ask_history by timestamp+peer:

| Population | Zombie rate |
|---|---:|
| All PTY asks | 7/96 (7.3%) |
| Reused query-file PTY attempts | 5/9 (55.6%) |
| First-time/unique-file PTY attempts | 2/75 (2.7%) |

Odds ratio ~45.6, one-sided Fisher p=0.0000786. This revises the "ag intrinsic zombie rate" used earlier in the night's analysis (~5.7%, a blended figure that included repeat-failure reuses) down to a true first-dispatch rate of ~2.7% — ag is more reliable on a genuinely fresh ask than previously estimated.

**Fixed** (`0feb3f3`): `_staged_query_file_prior_failures()` scans `ask_history.jsonl` for prior failures against the exact file being reused and warns loudly (independent of age) — "this exact file has FAILED N prior time(s)... consider writing a fresh query file instead."

## Finding 4: the specific 2026-07-18 00:32/00:46 incident — origin CONFIRMED, mechanism NOT established

A second, more careful forensic pass (cx.deepthink, explicitly instructed not to self-dispatch this time — and it complied, no new dispatch errors) found:

- **Origin, confirmed via literal command logs (not inference)**: the two mystery dispatches were run by the terminal's own earlier `cx.deepthink` investigation session (`019f70a4-2f1d-7913-ae71-cca351863974`, launched from `cx-20260718001306-zombie1.txt`). Its Codex rollout transcript shows the literal shell command `python hub.py ask --to ag.effort --query-file 'ag.opus-20260716011000-audit-c.txt'` run twice (00:22:24 and 00:33:47 KST), both zombie-timing-out. This is the exact self-orchestration failure mode documented in round 2 (`closure-review-2026-07-17-round2.md`'s "Process / prompt-design lesson"), now doubly confirmed.
- **The "clean paired comparison" from earlier analysis was NOT actually clean**: the original failed run used `ag.opus`/Claude Opus 4.6 and resumed an existing session; the "identical content, fresh filename" successful retry used a *different profile* (`ag.effort`/Gemini 3.5 Flash High) and *also* resumed an existing (different) session — profile, model, and session all differed, not just the filename. The apparent controlled experiment from the prior night's analysis was confounded.
- **Session-reuse mechanism ruled out as the common cause**: the two July-18 failures both started genuinely NEW conversations (not resumed sessions), so stale-session reuse cannot explain them.
- **PTY/process pooling ruled out**: all four historical attempts used distinct PIDs; every ask spawns a fresh `PtyProcess`.
- **Content/path-addressed caching ruled out**: no cache in hub.py, Antigravity state, or CLI logs keys on the original query filename or its content hash.
- **Honest conclusion**: no causal filename/reuse mechanism was found. The reused-file population is inherently enriched for already-difficult prompts and adverse conditions (it's conditioned on having already failed once), so the strong correlation found in Finding 3 may be confounded rather than causal. A decisive test would require randomized trials holding profile/model/session-policy/prompt bytes/timing constant while varying only whether the file is reused — not yet done.

ag.deepthink's self-report (one data point, explicitly caveated as introspective/unverifiable): it reported that when context makes it aware a request resembles something already attempted and failed, it does genuinely behave differently — "actively second-guessing... generating alternative, often increasingly convoluted workarounds... deep internal re-planning loops." This is a plausible contributing mechanism for the correlation in Finding 3, but is a self-report, not independently verified, and doesn't explain the July-18 pair specifically (both used fresh sessions, so the model may not have had the prior-failure context available to react to). Separately, this exact ask (a short, low-risk question) itself ended with agy stopping output cleanly at 790 characters mid-sentence (`success: true`, no timeout) — not a zombie, but a related, unexplained premature-completion behavior worth noting for future investigation.

## Current state / what remains open

- **Fixed and shipped**: IPC single-use enforcement (`c2f88e4`), prior-failure warning (`0feb3f3`), post-progress zombie window tightening (`e1e35e2`, from the prior round).
- **Not implemented**: automatic retry-on-zombie (deferred in round 2, still not built — the correct design is documented there).
- **Genuinely unresolved**: the root cause of why ag occasionally stalls mid-stream on a fresh, first-time dispatch (the true ~2.7% baseline). No mechanism was established after two dedicated forensic passes. Further progress would need controlled trials (see Finding 4's proposed test) rather than more historical-log archaeology — logs have now been examined about as thoroughly as they can be for this question.

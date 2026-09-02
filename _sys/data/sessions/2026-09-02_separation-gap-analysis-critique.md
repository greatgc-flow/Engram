# Terminal critique of the 2026-09-02 separation gap-analysis (cx.deepthink)

**Status:** critique-track ratification note, not a peer round — `ag` was
unavailable for the whole of this research (G-pool 97% CRIT, ~2d22h to
reset) so the terminal performed the critique directly, matching the
precedent set for the Gap 6 capability-matching design earlier this session
(`docs/design/PEERHUB-BACKLOG-2026-08-27.md`, "Gap 6 capability matching
research resolution"). This note does not replace a real second independent
peer critique — if `ag` recovers before implementation starts, its critique
should still be sought before treating this as fully ratified.

## Citations independently spot-verified against real files/commits

All of the following were checked directly (not taken on cx's word) and
confirmed accurate:

- `PEERHUB\pyproject.toml`'s `[project.scripts]` registers only
  `peerhub = "peerhub.cli:main"` — no `hub` entrypoint, confirming the
  README's "registers `peerhub` and `hub` entrypoints" claim is stale.
- `peerhub --help`'s subcommand list has no autodetect/scan/inventory
  command; `routing discover` is capability-matching over already-registered
  targets, not host executable discovery — confirms the core AI-CLI
  autodetection gap finding.
- `PHASE1-AUTODETECT-SIDECAR-2026-08-19.md` and its V2 both exist and are
  genuinely marked DRAFT in their own headers.
- `ENGRAM_MAIN\_sys\cli\peerhub.bat` hardcodes Engram's own venv path
  (`%~dp0..\..\_sys\env\venv\...`) with a `P:` fallback — confirms "couples
  PeerHub to Engram's venv, P-drive fallback, and PATH."
- `ENGRAM_MAIN\_sys\cli\manage.py` still contains `_workspace_init_legacy`
  at line 104, called at line 96 — confirms it's still present, not already
  dead code.
- `ENGRAM_MAIN\_sys\tests\unit\l1_core\test_contracts.py`'s
  `test_interactive_console_launchers_still_exist` genuinely asserts
  `console_runner.py`/`peer_console.py`/`claude_entry.py`/`codex_entry.py`/
  `agy_entry.py` must exist — confirms the boundary test does encode the
  "keep interactive vendor-CLI launching in Engram" decision cx flagged as
  needing to change.

## One citation error found (minor, doesn't change any conclusion)

Section 2.3 cites the V2 autodetection draft as
`PHASE1-AUTODETECT-SIDECAR-V2-2026-08-19.md`; the real filename is
`PHASE1-AUTODETECT-SIDECAR-V2-2026-08-20.md` (one day later). The document's
existence, DRAFT status, and content summary are otherwise accurate — this
is a transcription slip in the date portion of a filename, not a
substantive error.

## One nuance worth flagging before this becomes a ratified gate input

Section 2.4's "PeerHub's README also needs reconciliation" reads
`PEERHUB\README.md:28-38`'s "Formal multi-peer consensus... deferred" next
to the TDD paragraph's "gap-2 (consensus)... in full" as a self-contradiction.
Independently re-checked: these are two different things wearing the same
word. The deferred item is specifically Primitive B — formal voting
machinery for *external* decisions routed into peerhub — while the
implemented `ConsensusService` covers propose/vote/resolve for peerhub's
*own* governance rounds (already disambiguated in
`docs/design/PEERHUB-BACKLOG-2026-08-27.md`'s Tier 5 section, which this
report's author did not have reason to have read). Not a logical
contradiction, but the wording genuinely invites the misreading cx made —
worth tightening when PeerHub's own README gets its next pass, independent
of this separation effort.

## A design tension worth surfacing, not yet a decision

Section 3.5 recommends deleting `console_runner.py`/`peer_console.py`/the
vendor `*_entry.py` launchers, which the existing (2026-08-19-era) boundary
test intentionally protects (`test_interactive_console_launchers_still_exist`,
docstring: "Launching a vendor AI CLI interactively stays an Engram
feature"). This looks like a real tension between two decisions made two
weeks apart — but re-reading today's user directive resolves it cleanly:
"AI CLI wrapper 등은 전혀... (설치,제거,업데이트,현황 파악 외 모든 코드는
삭제해도 됨) 필요없어" explicitly scopes Engram down to
install/uninstall/update/status-check only, with interactive launch
excluded. cx's recommendation to delete these launchers (and update the
now-obsolete test) is correct under today's more specific instruction; the
2026-08-19 test encoded a decision that today's directive has since
superseded, not a bug in this report.

## Verdict

The research holds up under independent spot-checking. Treat the report's
four answers and eight-gate list as sound INPUT to the next phase (gate-by-
gate design work), with the two corrections above folded in. Still pending
before any of this is truly unanimous: a real second peer (`ag`, once its
quota recovers) reviewing the same material independently.

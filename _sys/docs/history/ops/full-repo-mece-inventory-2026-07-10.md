# Full-repository MECE inventory — 2026-07-10

Exhaustive, MECE (+exceptions) inventory of every source file, config file, and
governing instruction/document across this repo, unanimous after 5 rounds
(ag + cx + cc.fable), per the user's explicit request to iterate "until
nothing is missing." Two intermediate rounds contained real regressions that
were caught and corrected before ratification — see the process note at the
end.

## Categorization rule (ratified)

Classify by **WHO writes a thing and WHEN** — not by whether git tracks it:

- Human/consensus-authored, design-time policy → **Configuration** or
  **Instructions & Documentation**
- Hand-authored executable logic → **Source**
- Installer-produced binaries/runtime payloads → **Provisioned Components
  & Scaffolding**
- Machine/session/runtime-mutated data → **Generated Runtime State**,
  regardless of whether git tracks it
- Historical/descriptive knowledge records → **Instructions &
  Documentation** (descriptive sub-kind)

This tie-breaker rule is what resolves every edge case below (most notably
`_sys/ai/backlog.json`: git-tracked, but machine-mutated → State, not
Configuration).

## 1. Source

Hand-authored executable logic and orchestration scripts.

- Root: `INSTALL.bat`, `CLEANUP.bat`, `register.bat`, `unregister.bat`,
  `wrapper.cs`
- `_sys/start.bat`
- `_sys/core/` — the orchestration engine (`hub.py`, `dispatcher.py`,
  `provisioner.py`, `scrubber.py`, `version_resolver.py`, etc.)
- `_sys/cli/` — peer CLI entry wrappers (`claude.bat`, `codex.bat`,
  `agy.bat`, `msg.bat`, etc.)
- `_sys/checks/` — invariant/health/pre-flight scripts (`check_*.py`)
- `_sys/hooks/` — lifecycle scripts (`ctx_save.py`, `ctx_end.py`,
  `collab_log.py`, `ai_check.py`, `memory_compactor.py`, `raw_log.py`)
- `_sys/tests/` — unit/integration/live test suites

`wrapper.cs` belongs here (hand-authored C# source); its compiled output
`Engram.exe` does **not** — that's a build artifact, filed under Provisioned
Components below. Keeping them apart is what the WHO/WHEN rule produces
mechanically (author vs. build product), not a value judgment.

## 2. Configuration & Maps

Design-time config, maps, schemas, registries — parameterizes behavior,
never mutated by a running process.

Root: `.gitattributes`, `.gitignore`, `.vscode/settings.json`

`_sys/` top-level: `config.json`, `context_menu.json`, `dispatch.json`,
`env.json`, `local.config.bat.template`, `paths.json`, `runtimes.json`,
`core/hub_config.json`, `config/environment.json`

`_sys/ai/` top-level config (17 files, enumerated — no "etc."):
`collaboration_loop_bindings.json`, `collaboration_policy.schema.json`,
`config.json`, `error-taxonomy.json`, `governance_params.json`,
`infra.json`, `lifecycle_policy.json`, `logging-config.json`,
`model-registry.json`, `orchestration.json`, `peers.json`, `protocol.json`,
`room_policy.example.json`, `routing-config.json`, `status_checks.json`,
`telemetry-config.json`, `traceability_map.json`

`_sys/ai/` nested config/scaffold: `common/agents/*.json` (9 agent-role
definitions: architect, cross-reviewer, implementer, lesson-extractor,
portability-auditor, proposer, researcher, risk-scanner, verifier),
`common/mcp/catalog.json`, `common/statusline/statusline-schema.json`,
`config/environment.json`

`_sys/ai/backlog.json` is **deliberately excluded** from this category
despite being tracked — it's machine-mutated operational state (peers flip
items to `done` with evidence commits, as this very session did repeatedly
today). See Generated Runtime State.

## 3. Instructions & Documentation

Split into two sub-kinds, since "prescribes rules" alone doesn't cover
`_sys/docs/history/`'s design-record content.

**Prescriptive (governs — MUST/MUST-NOT rules):**
`AGENTS.md`, `CLAUDE.md`, `GEMINI.md`, `PROTOCOL.md`, `CONVENTION.md`,
`README.md` (root); `_sys/ai/user-directives.md`,
`_sys/ai/common/peer-rules.md`, `_sys/ai/common/skills/*.md` (6 skill docs:
consensus-vote, context-fill, health-check, lesson-add, peer-propose,
reflect)

**Descriptive (records what was decided, doesn't govern):**
`_archive/`, `_sys/docs/` (only contains `history/`), `_sys/docs-v2/`,
`_sys/docs/history/`, `_sys/ai/knowledge/` and its full contents
(`enforcement/LL-009.json`, `LL-011.json`, `LL-012.json`,
`LL-20260703-005.json`; `general/active-lessons.jsonl`,
`general/lesson-taxonomy.json`; `knowledge.config.json`;
`logs/approval-log.jsonl`; `peer-specific/peer-bindings.json`;
`schemas/collaboration_policy.schema.json`)

## 4. Provisioned Components & Scaffolding

Installer-produced payloads, build artifacts, reusable scaffolds — not
hand-authored, not runtime-mutated.

- `Engram.exe` — compiled launcher artifact (compiled from `wrapper.cs`,
  see Source)
- `_sys/tools/` — installed CLI tools + themes: `agy`, `apps`, `bat`,
  `delta`, `fd`, `fzf`, `gh`, `jq`, `oh-my-posh`, `ripgrep`, `sqlite`
- `_sys/env/` — installed base runtimes: `git`, `nodejs`, `pwsh`, `python`,
  `venv`, `vscode` (`ffmpeg` remains as stale residue — see Exceptions)
- `_sys/templates/`
- `_sys/git-config/.gitconfig`
- `_sys/claude/` tracked/scaffold portion: `claude-gate.bat`,
  `claude-status.bat`, `config/CLAUDE.md`, `config/settings.json`,
  `config/statusline-command.sh`, `project/agents/`, `project/settings.json`,
  `project/skills/`, `templates/workspace.md`
- `_sys/codex/` tracked/scaffold portion: `codex-status.bat`,
  `config/CODEX.md`, `config/rules/default.rules`, `templates/workspace.md`
- `_sys/antigravity/` tracked/scaffold portion: `agy-status.bat`,
  `config/AGY.md`, `config/statusline-command.sh`, `templates/workspace.md`

## 5. Generated Runtime State

Machine/session-mutated state, caches, IPC, temp, user workspace data —
regardless of git-tracked status.

Root: `.agents/`, `.ai/` (state.json, `consensus/`, `broker/`, `sessions/` —
this is the ACTIVE runtime directory this very conversation uses all
session; distinct from `_sys/ai/`, do not confuse the two), `.claude/`
(session/settings caches: `settings.local.json`, `scheduled_tasks.lock`),
`.git/`, `.pytest_cache/`, `tmp/`, `workspace/`

`_sys/`: `.pytest_cache/`, `ai/backlog.json`, `ai/runtime-directives.jsonl`,
`ai/ipc/` (this conversation's own peer-query transport), `ai/proposals/`,
`ai/snapshots/hub_api.json`, `data/`, `mock_peer/` (machine-written
`health.json` only — confirmed not hand-authored scaffolding),
`pytest_local/`

Peer-home runtime sub-trees (homogeneous by directory — declared as State
in full, not enumerated file-by-file since every file under these is
machine-written): `_sys/claude/config/projects/` (session transcript
JSONLs), `_sys/claude/config/file-history/`, `_sys/claude/health.json`,
`_sys/claude/session_state.json`, `_sys/codex/config/sessions/` (rollout
JSONLs), `_sys/codex/health.json`, `_sys/codex/session_state.json`,
`_sys/antigravity/config/brain/`, `_sys/antigravity/config/scratch/`
(its `temp_sys/` child is separately flagged as cruft below — the parent
directory itself is legitimate runtime scratch space), `_sys/antigravity/health.json`,
`_sys/antigravity/session_state.json`, `_sys/antigravity/ipc-config/`.

`.agents/` and `.claude/` stay here, not Configuration, despite superficially
looking like "peer config" — they hold session-local runtime caches, not
design-time policy.

## Known exceptions / cruft

- `_sys/antigravity/config/scratch/temp_sys/` — a stale mirrored copy of
  `hub.py`/`snapshot.py`/`tests` (hit repeatedly by greps this session).
  Disposition: delete if accidental, or document exactly why a scratch
  mirror needs to persist.
- `_sys/env/ffmpeg/` — stale empty directory (dated 2026-06-11, predates
  today's FFmpeg-removal work) left on disk despite FFmpeg being fully
  purged from `runtimes.json`/`env.json`/`provisioner.py` today. Disposition:
  delete.
- `_sys/test_valid2.out` — a git-**tracked** zero-byte file with no apparent
  code reference. Disposition: likely orphan, remove or document why it's
  kept.
- `cleanup_tiers.json` — genuinely does not exist anywhere in the repo, yet
  `_sys/core/scrubber.py`'s own module docstring claims "Tier definitions
  driven by cleanup_tiers.json (falls back to defaults)." All tier
  definitions are actually hardcoded in Python; the JSON-driven fallback
  pattern described in the docstring was never built. Doc/code drift —
  either build the file or fix the docstring.
- Confirmed absent, not a gap: `_sys/gemini/` does not exist (gc's peer home
  is correctly absent — gc is a suspended/removed peer per prior backlog
  decisions, not a missed inventory item).

## Root allowlist cross-check

Every one of `_sys/checks/check_root_hygiene.py`'s 24 allowlisted root
entries maps to exactly one place above:

| Entry | Category |
|---|---|
| `.agents` | Generated Runtime State |
| `.ai` | Generated Runtime State |
| `.claude` | Generated Runtime State |
| `.git` | Generated Runtime State (VCS metadata) |
| `.gitattributes` | Configuration |
| `.gitignore` | Configuration |
| `.pytest_cache` | Generated Runtime State |
| `.vscode` | Configuration |
| `_archive` | Instructions & Documentation (descriptive) |
| `_sys` | Container — contents span all 5 categories, see above |
| `AGENTS.md` | Instructions & Documentation (prescriptive) |
| `CLAUDE.md` | Instructions & Documentation (prescriptive) |
| `CLEANUP.bat` | Source |
| `CONVENTION.md` | Instructions & Documentation (prescriptive) |
| `Engram.exe` | Provisioned Components & Scaffolding |
| `GEMINI.md` | Instructions & Documentation (prescriptive) |
| `INSTALL.bat` | Source |
| `PROTOCOL.md` | Instructions & Documentation (prescriptive) |
| `README.md` | Instructions & Documentation (prescriptive) |
| `register.bat` | Source |
| `tmp` | Generated Runtime State |
| `unregister.bat` | Source |
| `workspace` | Generated Runtime State |
| `wrapper.cs` | Source |

## Process note

Round 1 (ag) proposed a workable 4-category split but made two real factual
errors in its exceptions list: it flagged `Engram.exe`/`wrapper.cs` as
"rogue"/"anomalous" and `_sys/config.json` vs `_sys/config/environment.json`
as a "duplication" — both false (the former are explicitly allowlisted
sanctioned artifacts; the latter are two files with unrelated single
purposes that happen to share the word "config"). Both were caught by
independently reading the actual files before passing to cx for cross-review.

Round 2 (cx) confirmed those corrections, confirmed the real `cleanup_tiers.json`
doc/code drift, and correctly identified the 4-category split wasn't MECE —
added the "Provisioned Components & Scaffolding" 5th category — plus found
`_sys/test_valid2.out` (tracked, zero-byte, orphaned) and stale
`_sys/env/ffmpeg/` residue.

Round 3 (ag, folding in round 2) still had two errors caught independently:
`_sys/data/` misbucketed under Configuration (it's pure runtime state), and
the entire `_sys/ai/` directory collapsed into one "Instructions" bullet
despite demonstrably spanning Config/Instructions/State at once.

cc.fable's first ratification pass (after round 3) found further gaps round
1-3 all missed: `_sys/ai/knowledge/` uncategorized, root `.ai/` (distinct
from `_sys/ai/`) missing entirely, `backlog.json` misclassified as pure
Config, `_sys/antigravity/config/scratch/temp_sys/` cruft unflagged — plus
ratified the category rename to "Instructions & Documentation" with a
prescriptive/descriptive split and the explicit WHO/WHEN tie-breaker rule.

Round 4 (ag, attempting to fold in fable's findings) **regressed badly**:
it collapsed almost the entire `_sys/` tree into a single "_sys/ (Partial:
..., etc.)" bullet — directly violating fable's own explicit "no etc., no
trailing ellipsis" instruction from the prior round — and completely
dropped the "Source" category and cx's "Provisioned Components &
Scaffolding" content entirely, while also incorrectly moving `.agents/`/
`.claude/` into Configuration. This was caught before being passed to fable,
and cx was asked to redo the merge from scratch rather than forward a
degraded inventory.

Round 5 (cx, merging round 3's granularity with round 4's genuine new
content while rejecting round 4's regressions) is what's documented above.
cc.fable's final ratification pass caught one more real gap — the peer-home
runtime-state enumeration was under-inclusive (missing `projects/`,
`file-history/`, `sessions/`, `brain/`, `scratch/` as homogeneous
directories) — folded into the final version above, and confirmed the
`.vscode` entry (independently caught missing from cx's own final
cross-check tally by the terminal) as `Configuration`.

Five rounds, two of which were substantive regressions rather than
progress, both caught before being carried forward. This is the process the
user's "반복 점검" (iterate until nothing is missing) request was actually
asking for — not just running more rounds, but verifying each round
independently rather than trusting either peer's "complete" self-assessment.

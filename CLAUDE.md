# Portable Sandbox Dev Environment
> Last updated: 2026-06-01
> This file lets Claude Code resume from where the setup conversation left off.

## What This Project Is

A fully portable Windows development environment that lives in a single folder
(USB drive or cloud). Right-click any folder -> open VS Code + Claude Desktop
with all tools (Python, Node.js, FFmpeg, Git, etc.) pre-configured.

## Final Folder Structure

```
[PortableDev]/              <- ROOT (3 docs + INSTALL.bat + register.bat + unregister.bat + workspace + .claude + _sys + _workspace + _archive)
????? INSTALL.bat             <- double-click entry (calls _sys\setup.ps1)
????? register.bat            <- register this PC: context menu + SUBST drive (once per PC or USB move)
????? unregister.bat          <- permanently remove context menu + SUBST from this PC
????? CLAUDE.md               <- this file
????? README.md               <- user documentation
????? CONVENTION.md           <- coding standards (agents reference this)
????? workspace/              <- default project folder (can also be external)
????? .claude/                <- harness: agents/ + skills/
????? _workspace/             <- agent session workspace (auto-managed, not user content)
??  ?遺??? state.json + 02_*.md / 03_*.md / 04_*.md per session
??  (backed up as _archive/workspace_{YYYYMMDD_HHMMSS}/ on new session start)
??????? _archive/               <- ALL rolling historical data (logs, sessions, workspace backups)
??  ????? logs/               <- start.bat execution logs (LOG_DIR)
??  ????? sessions/           <- ctx-save / ctx-end session files (SESSION_DIR)
??  ????? collab-log/         <- Claude-Gemini collaboration logs (YYYY-MM-DD.md per day)
??  ????? CHANGELOG.md        <- full change history (moved from CLAUDE.md for token efficiency)
??  ?遺??? workspace_{YYYYMMDD_HHMMSS}/  <- _workspace backups per session
???遺??? _sys/                   <- ALL system files (tools, config, data)
    ????? start.bat           <- main launcher (restores SUBST on reboot; warns if not registered)
    ????? launch.ps1          <- relay: registry -> start.bat (path safety)
    ????? manage.ps1          <- unified manager: Register/Unregister SUBST + context menu (called by register.bat / unregister.bat)
    ????? setup.ps1           <- zerobase bootstrapper (download + install all)
    ????? cleanup.ps1         <- temp/cache/log cleanup (space optimizer)
    ????? local.config.bat.template  <- per-PC config template (copy & edit)
    ??    ????? context/            <- session management scripts
    ??  ????? ctx-save.bat    <- mid-session checkpoint (session log -> _archive\sessions\)
    ??  ????? ctx-end.bat     <- full session summary + session log to _archive\sessions\
    ??  ????? CLAUDE_project.md  <- template for per-project CLAUDE.md
    ??  ?遺??? CLAUDE_global.md   <- template for _sys\claude\config\CLAUDE.md
    ??    ????? git_config/         <- portable git settings
    ??  ?遺??? .gitconfig
    ??    ????? env/                <- runtime binaries
    ??  ????? python/         <- portable Python (embeddable)
    ??  ????? nodejs/         <- portable Node.js + npm-global (Gemini + Claude CLI here)
    ??  ??  ?遺??? npm-global/ <- code.cmd (VS Code wrapper), claude.cmd, gemini.cmd
    ??  ????? ffmpeg/         <- portable FFmpeg (bin/ subfolder)
    ??  ????? git/            <- portable Git
    ??  ????? vscode/         <- portable VS Code (data/ enables portable mode)
    ??  ????? pwsh/           <- portable PowerShell 7 (optional, setup.ps1 installs)
    ??  ?遺??? venv/           <- Python venv (auto-created by start.bat)
    ??    ????? tools/              <- optional CLI + GUI tools (auto-detected)
    ??  ????? ripgrep/ rg.exe    [installed]
    ??  ????? fd/      fd.exe    [installed]
    ??  ????? jq/      jq.exe    [installed]
    ??  ????? bat/     bat.exe   [installed]
    ??  ????? delta/   delta.exe [installed]
    ??  ????? fzf/     fzf.exe   [installed]
    ??  ????? sqlite/  sqlite3.exe [not installed]
    ??  ????? oh-my-posh/        [installed]
    ??  ?遺??? apps/             <- GUI apps (Bruno, etc.)
    ??    ????? claude/             <- Claude Code CLI
    ??  ????? config/         <- CLAUDE_CONFIG_DIR (auth + global CLAUDE.md, portable)
    ??  ?遺??? agent/          <- agent state (CONTEXT.md)
    ??    ????? gemini/             <- Gemini CLI (binary in nodejs/npm-global)
    ??  ?遺??? config/         <- placeholder; Gemini CLI auth portable via Junction ??%USERPROFILE%\.gemini\
    ??    ????? test/               <- test suite
    ??  ????? sandbox-test.bat   <- unit tests (~100 cases, WSB-ready)
    ??  ????? host-test.ps1      <- host-side tests (31 cases: settings, statusline, VS Code, npm)
    ??  ????? test-runner.ps1    <- orchestrator (Layer 1+2, WSB auto-detect, report)
    ??  ????? launch-wsbtest.ps1 <- WSB launcher (SUBST-aware, maps P:\ ??C:\PortableDev)
    ??  ?遺??? results/           <- test reports (last-run.txt + timestamped archives)
    ??    ?遺??? data/               <- persistent data
        ????? temp/           <- isolated temp files
        ?遺??? setup-files/    <- installer archives & download links
```

## Architecture Decisions

| Decision | Reason |
|----------|--------|
| Everything under `_sys/` (except docs + workspace) | Root clean: 3 docs + workspace + .claude + _sys only |
| Workspace at root or external | Multiple workspaces, nested or outside BASE_DIR |
| Registry key = `SandboxRun_[FolderName]` | Multiple envs on same PC without conflict |
| HKCU for context menu (not HKCR) | No admin required; register.bat handles initial and re-registration |
| register.bat for explicit PC registration | Assigns fixed SUBST drive; calls manage.ps1 to store state and register menu |
| unregister.bat for permanent removal | Calls manage.ps1 for global cleanup (SUBST + Registry + State) |
| Unified manage.ps1 manager | Single Source of Truth for naming, SUBST mapping, and Registry state |
| State-aware Cleanup | Registration auto-cleans orphaned keys from previous folder names/paths |
| No USERPROFILE/APPDATA override | Preserves Git, SSH, host credentials |
| Tool-specific env vars (NPM_CONFIG_*, etc.) | Precise isolation without broad side effects |
| `CLAUDE_CONFIG_DIR = _sys\claude\config\` | Claude Code CLI auth/config travels with USB |
| Gemini CLI via npm-global (nodejs/npm-global) | `gemini.cmd` auto-in-PATH via existing npm-global PATH entry; no separate PATH line needed |
| Gemini auth in `%USERPROFILE%\.gemini\` (host) | Gemini CLI v1.x does not support `GEMINI_CONFIG_DIR` override; re-auth required per PC |
| `_archive/` for all rolling data | logs + sessions + workspace backups in one place for easy cleanup |
| `LOG_DIR = BASE_DIR\_archive\logs` | Logs beside workspace backups, not buried under _sys |
| `SESSION_DIR = BASE_DIR\_archive\sessions` | Session files beside logs; ctx-save/end fallback-derives from script location if SESSION_DIR unset |
| `ENV_DIR`, `TOOLS_DIR`, `CLAUDE_DIR`, `DATA_DIR` in start.bat | All paths relative to SYS_DIR |
| Individual `if exist` lines (not for-loop) | for-loop expands %PATH% once -> bug |
| `-LiteralPath` in all registry PS1 ops | `HKCU:\Software\Classes\*\shell\...` wildcard hang prevention |
| `launch.ps1` as registry intermediary | Direct bat execution from registry breaks on space/Korean paths |
| `.bat` files: English only, no Korean | chcp 65001 doesn't fix cmd.exe parser for multi-byte chars |
| No Rust toolchain | Removed; not used |
| `local.config.bat` for per-PC overrides | start.bat auto-loads it before CONFIG defaults; not tracked in Git |
| `CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS=1` auto-set | Harness (agent teams) requires this env var; start.bat sets it on every launch |
| `setup.ps1` component-level try/catch (Run-Component) | One component failing does not abort the whole bootstrap; failures listed in summary |
| `INSTALL.bat` at root | Single double-click entry for first-time setup; relays to `_sys\setup.ps1` |
| `code.cmd` in `npm-global/` | VS Code portable wrapper; Claude Code IDE integration requires `code.cmd` in PATH |
| `start.bat` syncs `statusline-command.sh` to `~/.claude/` | statusline script must be at `~/.claude/` on every host PC; start.bat copies it on each launch |
| WSB (`launch-wsbtest.ps1`) as default test env | True OS isolation; sandbox-test.bat runs unmodified inside WSB; local fallback for CI |
| `_archive/CHANGELOG.md` for change history | Keeps CLAUDE.md stable (better prompt-cache hits); history accessible but not loaded every session |
| `pwsh/` in `env/` | Portable PowerShell 7; optional component via `setup.ps1 -Pwsh` |

## Key Bugs Fixed (for reference)

1. **HKCR wildcard hang**: `Test-Path` / `Set-ItemProperty` on `HKCR:\*\shell\...`
   treats `*` as wildcard -> enumerated all HKCR keys. Fixed: `-LiteralPath`.
   Same applies to `HKCU:\Software\Classes\*\shell\...`.

2. **for-loop PATH accumulation**: `for %%T in (...) do (set "PATH=...;%PATH%")`
   expands `%PATH%` once before loop. Fixed: individual `if exist` lines.

3. **Korean in .bat call args**: `call :LOG "???..."` - cmd.exe parser splits
   multi-byte UTF-8 chars into tokens. Fixed: English only in all .bat files.

4. **Registry command quoting**: `cmd.exe /c ""path"" "arg""` -> empty command error.
   Fixed: `launch.ps1` as relay, uses `cmd /c call "bat" "arg"` pattern.

5. **FZF_HISTORY_DIR**: invented env var that fzf doesn't recognize. Removed.

6. **BAT_CONFIG_DIR**: wrong name. Fixed: `BAT_CACHE_PATH`.

7. **`for /f` wmic in for-loop block with `!VAR!`**: needed `setlocal EnableDelayedExpansion`.

## Current State
Last ctx-save: 2026-06-01 16:35 -- see _archive/sessions/ for snapshot
Last ctx-save: 2026-05-31 (see _archive/sessions/ for snapshot)

2026-06-01 揶쏆뮇苑??袁⑥┷:
- VS Code ????: `npm-global/code.cmd` ??묐쓠 ?곕떽? ??/status "code.cmd not found" 野껋럡????욧퍙
- start.bat: `statusline-command.sh` ??`~/.claude/` ?癒?짗 ??녿┛??(筌???뽰삂 ??
- WSB ???뮞???紐낅늄?? `_sys/test/launch-wsbtest.ps1` + `results/` ????(CONVENTION.md 吏?)
- CHANGELOG ?브쑬?? `CLAUDE.md` 22????????`_archive/CHANGELOG.md` (~1,600 ?醫뤾쿃/?紐꾨???뉗빵)
- validator.md step 5b: GEMINI_MODE=ON ??audit JSON ??Gemini ?????遺용튋 ??verifier ?醫뤾쿃 ??됰튋
- CONVENTION.md 吏?: WSB??疫꿸퀡?????뮞????띻펾??곗쨮 ?⑤벊???
2026-05-31 ??域뱀뮆??揶쏆뮇苑??袁⑥┷ (??`_archive/CHANGELOG.md` 筌〓챷??

## Next Steps

1. **WSB ???뮞????쎈뻬**: `powershell -ExecutionPolicy Bypass -File P:\_sys\test\launch-wsbtest.ps1`
2. **?紐꾨??ル굝利?*: `ctx-end` ??쎈뻬 ??`_archive\sessions\` ????삳뮎 ?紐꾨?????3. **Axis ??쎄쾿?깆???野꺜筌?*: `gemini-status.bat` ??`context-health.bat` ??`collab-log-append.bat`
4. **Fresh PC / Zerobase setup**: Run `INSTALL.bat` (double-click) ??calls `_sys\setup.ps1`

---

## Gemini CLI ??뽰뒠 ?袁り텕??우퓗

Gemini CLI??Claude ??롪퐬??쇱벥 **癰귣똻???袁㏓럡**嚥???덉삂??뺣뼄. ?????쎈뱜??됱뵠?怨? ?袁⑤빒 ??쎈뻬??

```
[??????遺욧퍕]
     ??     ??[Claude Code ??Orchestrator + ??롪퐬??  ??雅??룐뫂遊? 筌롫뗀?덄뵳? Human Gate, ???씩??亦낅슣??     ?? ??     ?? ?? ??Gemini??[REQUEST_TO_CLAUDE: TYPE]??곗쨮 ???귨㎗?揶쎛??(??묐즸 ?臾먯젾)
     ?? ??[Gemini CLI ?????源딅립 ?臾먯젾??
     ????? Axis-A: ????몄쎗 ?브쑴苑?   ??portability-auditor (??쇱뒠 ??볧?500k ?醫뤾쿃)
     ????? Axis-B: 甕곌쑴??URL 野꺜筌? ??version-check.bat (Google Search grounding)
     ????? Axis-C: ?紐꾨??遺용튋      ??ctx-end ?袁⑹퓗??(?醫뤾문?? Flash)
     ????? Axis-D: ?????얜챶苡?野꺜???????袁る퓮 癰궰野???쥓??pass
     ????? Axis-D+: 餓λ쵌而??遺용튋     ??ctx-save ??     ????? Axis-E: ?癒?뵠?袁る뱜 揶쏅Ŋ沅? ??agent-audit.bat ??_archive/agent-audit.json
     ????? Axis-F: ??쎄쾿?깆?????뤵????script-deps.bat ??_archive/script-deps.json
     ????? Axis-G: ?뚣끇而??λ뜆釉?     ??git-draft.bat (?꾩꼷???곗뮆?? ?????野꺜?????뚣끇而?
     ????? Axis-H: Context health ??context-health.bat (JSONL size ??status.json + session-handoff.json)
     ?遺??? Axis-I: Pre-flight risk ??risk-scan.bat (Phase 1.5, collab-log patterns ??_archive/risk-scan.json)
```

**??묐즸 ?臾먯젾 ?癒?뒅**: ?臾믩????遺욧퍕??랁?椰꾧퀣???????덈뼄. Claude?????씩????釉??類ㅼ퐠 ???뵬夷똆EMINI_MODE夷똇uman Gate)?癒?퐣筌?筌ㅼ뮇伊?野껉퀣?숁쾮??뱽 揶쎛筌욊쑬?? ?癒?쉭?????뻿 ?類ㅻ뻼?? `CONVENTION.md 吏?-5` 筌〓챷??

### 疫뀀뜆? ??鍮?| 疫뀀뜆? | ??곸? |
|------|------|
| Gemini????롪퐬???????쎈뱜??됱뵠?怨뺤쨮 ????| CLAUDE.md夷똲tate.json ?紐꾨뻼 ?븍뜃?, 筌롫뗀?덄뵳???곸벉 |
| ??롪퐬???룐뫂遊???獄쏆꼶???紐꾪뀱 | 1,000 req/day ???춭, ?룐뫂遊?餓λ쵎???袁る퓮 |
| ?얜똻???癒?짗 ??쎈뻬 (cron/hook) | ?紐꾩쵄 ??쑴???밴쉐 ??筌띾슢利???鈺곌퀣?????쎈솭 |
| GEMINI_CONFIG_DIR ??쇱젟 | v0.44.1 沃섎챷???|
| Flash 筌뤴뫀?썸에?PASS/FAIL ?癒?젟 | Claude verifier揶쎛 ??μ뵬 筌욊쑴?????뮞 |

### ?온?????뵬
- `_sys/context/version-check.bat` ??Gemini 甕곌쑴??野꺜????`_archive/version-check.json`
- `_sys/context/ctx-end.bat` ???紐꾨??ル굝利???Gemini ?遺용튋 hook (??곸몵筌?椰꾨?瑗??)
- `_sys/context/context-health.bat` ??Axis-H: JSONL ??由?筌β돦????status.json + session-handoff.json
- `.claude/agents/portability-auditor.md` ??Gemini Full-Corpus Scan ??ｍ???釉?- `.claude/agents/proposer.md` ??version-check.bat ?紐꾪뀱 + ??롫짗 ??媛?筌왖??- `CONVENTION.md 吏?-4` ??Gemini ?紐꾪뀱 ???쉘 獄?疫뀀뜆? ???쉘

---

## ??롪퐬?? Portable Dev Environment

**筌뤴뫚紐?** `_sys/` ??쎄쾿?깆?????륁젟夷?袁㏓럡 ?곕떽?夷??곷뻼??揶쏅Ŋ沅쀬쮯?닌듼??類ｂ봺夷??뺢돌?귐딆궎 野꺜?醫? 4揶???釉?+ 7揶??袁ⓓ??癒?뵠?袁る뱜 ??(??11筌???곗쨮 筌ｌ꼶??
**?紐꺿봺椰?** Portable Dev Environment ?온??筌뤴뫀諭??臾믩씜 ??`portable-env` ??쎄텢 ????
??λ떄 筌욌뜄揆(??쎄쾿?깆?????살구, ?닌듼????툢 ???? 筌욊낯???臾먮뼗 揶쎛??

**??롪퐬????쎄텢 筌뤴뫖以?** portable-env, bat-ps1-engineer, add-tool, tidy-structure, audit-portability, scenario-review, propose-improvements, risk-scan, context-health

**癰궰野?????** `_archive/CHANGELOG.md` 筌〓챷??(筌ㅼ뮇伊???낅쑓??꾨뱜: 2026-06-01)

# Ops — codex-cli Known Bugs & Update Checkpoint

> Created: 2026-07-24 | Method: session-reproduced local evidence + official
> release notes/issue tracker research (cx.deepthink), independently
> spot-checked by the terminal (2 issue URLs fetched directly, both confirmed
> real and accurately summarized).
> Purpose: run this checklist after every codex-cli version bump, before
> re-enabling unattended `hub.py` dispatch, to catch drift early — this is
> exactly the failure mode that caused both the 2026-07-23 ag model-ID
> incident and the 2026-07-24 gpt-5.6 context-window incident (see
> `orchestration.json` commit `af05e3b`).

Cross-ref: `ops/peer-cli-reference.md` (capability audit), `ops/cli-baselines/`
(verbatim `--help` captures), `specific/cx.md`.

---

## Scope and baseline

Run this checkpoint after every Codex CLI version change and before
re-enabling unattended `hub.py` dispatch.

Baseline observed on 2026-07-23/24:

- Codex CLI: `0.144.6`
- Platform: native Windows
- Auth: ChatGPT login
- Portable `CODEX_HOME`: `_sys/codex/config`
- Evidence tags:
  - `[cli_live]`: observed from the installed CLI.
  - `[app_server]`: observed from a live app-server JSON-RPC response.
  - `[empirical_probe]`: reproduced through a controlled local comparison.
  - `[declared, unverified]`: reported upstream but not reproduced locally.

The public [0.144.6 release](https://github.com/openai/codex/releases/tag/rust-v0.144.6)
refreshed GPT-5.6 model metadata and corrected the Sol, Terra, and Luna
context windows to 272,000 tokens — the terminal independently confirmed this
claim by fetching the release notes directly and cross-checked it against a
live `codex debug models` call before fixing `orchestration.json`,
`model-registry.json`, and `specific/cx.md` (all three had stale `372000`).

## Audit bootstrap

Run from the repository root. Resolve the real npm-installed command rather
than the legacy `codex.bat` wrapper (removed in Engram/peerhub separation).


```powershell
$Codex = (Get-Command codex.cmd -CommandType Application).Source
$RepoRoot = (Get-Location).Path

& $Codex --version
"CODEX_HOME=$env:CODEX_HOME"

$LoginText = (& $Codex login status 2>&1) -join "`n"
$LoginExit = $LASTEXITCODE
[pscustomobject]@{
    login_exit = $LoginExit
    login_text = $LoginText
}
```

Do not treat remote catalog or model-call results as live evidence unless
`codex login status` succeeds first.

Use this helper for app-server checkpoints:

```powershell
function Invoke-CodexRpc {
    param(
        [Parameter(Mandatory)][string]$Method,
        [hashtable]$Params = @{},
        [int]$TimeoutMs = 20000
    )

    $psi = [System.Diagnostics.ProcessStartInfo]::new()
    $psi.FileName = $env:ComSpec
    $psi.Arguments = "/d /s /c `"`"$Codex`" app-server --stdio`""
    $psi.UseShellExecute = $false
    $psi.RedirectStandardInput = $true
    $psi.RedirectStandardOutput = $true
    $psi.RedirectStandardError = $true
    $psi.CreateNoWindow = $true

    $process = [System.Diagnostics.Process]::new()
    $process.StartInfo = $psi
    [void]$process.Start()

    try {
        $initialize = @{
            method = "initialize"
            id = 0
            params = @{
                clientInfo = @{
                    name = "engram_update_checkpoint"
                    title = "Engram update checkpoint"
                    version = "1.0.0"
                }
            }
        } | ConvertTo-Json -Depth 10 -Compress

        $process.StandardInput.WriteLine($initialize)

        do {
            $read = $process.StandardOutput.ReadLineAsync()
            if (-not $read.Wait($TimeoutMs)) {
                throw "app-server initialize timed out"
            }
            $message = $read.Result | ConvertFrom-Json
        } until ($message.id -eq 0)

        $process.StandardInput.WriteLine(
            '{"method":"initialized","params":{}}'
        )

        $request = @{
            method = $Method
            id = 1
            params = $Params
        } | ConvertTo-Json -Depth 30 -Compress

        $process.StandardInput.WriteLine($request)

        do {
            $read = $process.StandardOutput.ReadLineAsync()
            if (-not $read.Wait($TimeoutMs)) {
                throw "app-server $Method timed out"
            }
            $message = $read.Result | ConvertFrom-Json
        } until ($message.id -eq 1)

        if ($message.error) {
            throw ($message.error | ConvertTo-Json -Compress)
        }

        return $message.result
    }
    finally {
        if (-not $process.HasExited) {
            $process.StandardInput.Close()
            if (-not $process.WaitForExit(2000)) {
                $process.Kill($true)
            }
        }
        $process.Dispose()
    }
}
```

The handshake and RPC methods follow the official
[Codex app-server protocol](https://learn.chatgpt.com/docs/app-server).

## Locally observed checkpoints

### A1. CLI and app-server disagree about the effective MCP inventory

- [ ] Run both inventories against the same `CODEX_HOME`:

```powershell
$CliMcpRaw = (& $Codex mcp list --json) -join "`n"
$CliMcp = @($CliMcpRaw | ConvertFrom-Json)

$RpcMcp = Invoke-CodexRpc "mcpServerStatus/list" @{
    limit = 100
    detail = "toolsAndAuthOnly"
}

$RpcSummary = $RpcMcp.data | ForEach-Object {
    [pscustomobject]@{
        name = $_.name
        tools = @($_.tools.PSObject.Properties).Count
        auth_status = $_.authStatus
    }
}

[pscustomobject]@{
    cli_servers = $CliMcp.Count
    cli_names = $CliMcp.name -join ","
    rpc_servers = $RpcMcp.data.Count
    rpc_names = $RpcMcp.data.name -join ","
}
$RpcSummary
```

Baseline `[cli_live + app_server]`: CLI returned `[]`; app-server returned
`codex_apps`, 192 tools, and `bearerToken` auth.

- Still inconsistent: app-server exposes an active server/tool inventory that
  the CLI omits.
- Fixed upstream: the CLI or a replacement CLI diagnostic exposes the same
  effective runtime inventory.
- If only the documented scope changes, keep `hub.py` capability discovery on
  `mcpServerStatus/list`.

Local source: `ops/peer-cli-reference.md` §2. Officially, `codex mcp list`
lists configured servers, while `mcpServerStatus/list` exposes servers,
tools, resources, and auth status:
[MCP CLI documentation](https://learn.chatgpt.com/docs/extend/mcp?surface=cli),
[app-server documentation](https://learn.chatgpt.com/docs/app-server).

### A2. The local wrapper omits the installed `delete` root command

- [ ] Verify the installed surface and wrapper classification:

```powershell
& $Codex --help | Select-String '^\s+delete\s'

python -c "from _sys.cli.peer_console import peer_default_args; print(peer_default_args('cx', ['delete', 'dummy-id']))"
```

Baseline `[empirical_probe]`:

```text
['delete', 'dummy-id', '-s', 'workspace-write', '--model', ...]
```

- Still broken locally: sandbox/model defaults are appended after
  `delete dummy-id`.
- Fixed locally: the result is exactly `['delete', 'dummy-id']`.
- Do not execute a real deletion to test this classifier.

Local source: peerhub `peer_console.py` (removed from Engram in separation); `ops/peer-cli-reference.md` §2.


### A3. Refreshed, bundled, and app-server model catalogs differ and lack freshness provenance

- [ ] Compare the three catalogs and inspect their schemas:

```powershell
$DefaultRoot = ((& $Codex debug models) -join "`n") | ConvertFrom-Json
$BundledRoot = ((& $Codex debug models --bundled) -join "`n") | ConvertFrom-Json
$RpcModels = Invoke-CodexRpc "model/list" @{
    limit = 100
    includeHidden = $true
}

$DefaultModels = @($DefaultRoot.models)
$BundledModels = @($BundledRoot.models)

[pscustomobject]@{
    default_count = $DefaultModels.Count
    bundled_count = $BundledModels.Count
    rpc_count = $RpcModels.data.Count
    default_only = (Compare-Object $BundledModels.slug $DefaultModels.slug |
        Where-Object SideIndicator -eq "=>" |
        Select-Object -ExpandProperty InputObject) -join ","
    bundled_only = (Compare-Object $BundledModels.slug $DefaultModels.slug |
        Where-Object SideIndicator -eq "<=" |
        Select-Object -ExpandProperty InputObject) -join ","
}

$SchemaKeys = @(
    $DefaultRoot.PSObject.Properties.Name
    $DefaultModels[0].PSObject.Properties.Name
    $RpcModels.PSObject.Properties.Name
    $RpcModels.data[0].PSObject.Properties.Name
) | Sort-Object -Unique

$SchemaKeys | Where-Object {
    $_ -match 'source|provenance|fresh|fetch|updated.?at|timestamp'
}
```

Baseline `[cli_live + app_server]`:

- Default catalog: 7 models. Bundled catalog: 8 models. `gpt-5.2` was
  bundled-only. App-server returned 7 models.
- No source, fetch time, update time, or freshness field appeared.

- Limitation persists: catalogs differ and the provenance-key query returns
  nothing.
- Improved upstream: an explicit source/fetch timestamp is returned. Record
  its semantics before trusting it.
- Any slug, effort, context-window, or default-model delta requires a
  repository drift comparison (see A7).

Local source: `ops/peer-cli-reference.md` §2. The documented `model/list`
fields also omit freshness metadata:
[app-server model-list reference](https://learn.chatgpt.com/docs/app-server).

### A4. Unauthenticated catalog calls silently succeed with bundled data

- [ ] Test with an isolated empty `CODEX_HOME`; do not log out the real
  portable profile:

```powershell
$SavedCodexHome = $env:CODEX_HOME
$EmptyCodexHome = Join-Path $env:TEMP "codex-update-empty-home-$PID"
New-Item -ItemType Directory -Path $EmptyCodexHome | Out-Null

try {
    $env:CODEX_HOME = $EmptyCodexHome

    $LoginOutput = (& $Codex login status 2>&1) -join "`n"
    $LoginExit = $LASTEXITCODE

    $DefaultRaw = (& $Codex debug models 2>&1) -join "`n"
    $DefaultExit = $LASTEXITCODE

    $BundledRaw = (& $Codex debug models --bundled 2>&1) -join "`n"
    $BundledExit = $LASTEXITCODE

    try {
        $RpcCatalog = Invoke-CodexRpc "model/list" @{
            limit = 100
            includeHidden = $true
        }
        $RpcOutcome = "success:$($RpcCatalog.data.Count)"
    }
    catch {
        $RpcOutcome = "error:$($_.Exception.Message)"
    }

    [pscustomobject]@{
        login_exit = $LoginExit
        login_output = $LoginOutput
        default_exit = $DefaultExit
        bundled_exit = $BundledExit
        default_equals_bundled = ($DefaultRaw -ceq $BundledRaw)
        rpc_outcome = $RpcOutcome
    }
}
finally {
    $env:CODEX_HOME = $SavedCodexHome
    Remove-Item -LiteralPath $EmptyCodexHome -Recurse -Force
}
```

Baseline `[cli_live + app_server]`: login status exited 1 with
`Not logged in`; default and bundled catalog calls both exited 0 and
returned byte-identical data; `model/list` also succeeded.

- Still broken: unauthenticated default lookup exits 0 and equals bundled
  data, or app-server returns a catalog without identifying it as
  stale/bundled.
- Fixed upstream: the default/live path fails clearly on missing auth, or
  returns explicit, machine-readable provenance.
- Any other changed behavior remains untrusted until classified. Exit 0
  alone is never live-catalog evidence.

### A5. Windows `unelevated` sandbox restrictions are intentional

- [ ] Run this from a normal, non-nested host terminal:

```powershell
$SandboxProbe = @'
[pscustomobject]@{
    HTTP_PROXY = $env:HTTP_PROXY
    HTTPS_PROXY = $env:HTTPS_PROXY
    ALL_PROXY = $env:ALL_PROXY
    CODEX_SANDBOX_NETWORK_DISABLED = $env:CODEX_SANDBOX_NETWORK_DISABLED
}
whoami /groups
'@

& $Codex sandbox -C $RepoRoot `
    powershell.exe -NoProfile -Command $SandboxProbe
```

Baseline `[cli_live + empirical_probe]` with `[windows] sandbox = "unelevated"`:

- Child token was restricted and limited; Administrators were deny-only.
- Dead-end proxy variables such as `http://127.0.0.1:9` were injected.
- Network suppression was advisory; programs with independent networking
  stacks could bypass those environment variables.

This is expected behavior, not a provider outage or `hub.py` permission bug.
OpenAI documents restricted tokens and proxy poisoning in its
[Windows sandbox engineering description](https://openai.com/index/building-codex-windows-sandbox/).

- Behavior unchanged: the child remains restricted and proxy poisoning is
  present.
- Upstream changed: the mode is removed or its mechanism differs. Re-read
  the official design before updating the expected result.
- A failure caused by nesting this probe inside another Codex sandbox is not
  evidence of an upstream regression.

Local source: `ops/peer-cli-reference.md` §2; commit `f911efa`.

### A6. Top-level `codex fork` requires a TTY, while `thread/fork` does not

- [ ] Create a disposable source through app-server, then attempt the
  top-level CLI fork headless, then clean up:

```powershell
$Source = Invoke-CodexRpc "thread/start" @{ cwd = $RepoRoot; ephemeral = $false }
$RpcFork = Invoke-CodexRpc "thread/fork" @{ threadId = $Source.thread.id }
[pscustomobject]@{ source = $Source.thread.id; fork = $RpcFork.thread.id; forked_from = $RpcFork.thread.forkedFromId }

$null | & $Codex fork $Source.thread.id --no-alt-screen 2>&1
"exit=$LASTEXITCODE"

Invoke-CodexRpc "thread/delete" @{ threadId = $Source.thread.id }
```

Baseline `[cli_live + app_server]`: RPC fork succeeded and returned the
correct `forkedFromId`; top-level CLI exited 1 with
`Error: stdin is not a terminal`.

- Gotcha persists: RPC succeeds but headless CLI returns the TTY error.
- Improved upstream: a documented non-interactive fork mode succeeds and
  returns a machine-readable thread ID.
- Never test against a hub-managed room thread.

### A7. Model context-window metadata parity (recurring risk — bit us once already)

- [ ] Compare the live catalog with both repository declarations:

```powershell
$LiveModels = @(
    (((& $Codex debug models) -join "`n") | ConvertFrom-Json).models
)
$Registry = Get-Content -Raw "_sys/ai/model-registry.json" | ConvertFrom-Json
$Orchestration = Get-Content -Raw "_sys/ai/orchestration.json" | ConvertFrom-Json
$CxNode = $Orchestration.hub_nodes | Where-Object node_id -eq "cx"

foreach ($ProfileName in "standard", "effort", "deepthink") {
    $Profile = $CxNode.profiles.$ProfileName
    $Live = $LiveModels | Where-Object slug -eq $Profile.model_id
    $Registered = $Registry.models.PSObject.Properties[$Profile.model_id].Value

    [pscustomobject]@{
        profile = "cx.$ProfileName"
        model = $Profile.model_id
        live_context = $Live.context_window
        orchestration_context = $Profile.runtime_context_window
        registry_context = $Registered.context_limit
        match = (
            $Live.context_window -eq $Profile.runtime_context_window -and
            $Live.context_window -eq $Registered.context_limit
        )
    }
}
```

**Already caught once (2026-07-24, FIXED, commit `af05e3b`):** Codex 0.144.6
corrected GPT-5.6 Sol/Terra/Luna context windows to 272,000 tokens;
`orchestration.json`, `model-registry.json`, and `specific/cx.md` all still
declared the old 372,000 until this checkpoint's own research caught it.

- Still broken locally: any row reports `match = False`.
- Fixed locally: all machine-consumed values equal the authenticated live
  catalog and their validation timestamp/source is updated.
- If a later release changes the value again, do not retain the old number
  blindly — repeat the live comparison and attach the applicable release
  note. This is a RECURRING risk, not a one-time fix.

Source: [Codex CLI 0.144.6 release](https://github.com/openai/codex/releases/tag/rust-v0.144.6).

## Upstream-reported regression watches

All items below are `[declared, unverified]` unless a future audit records a
local reproduction. Sources independently spot-checked by the terminal
(2 of 2 fetched issue URLs matched their claimed content — see B1/B2 below
for the ones directly verified; the rest were not individually re-fetched
and should be treated with normal caution until then).

### B1. Windows sandbox process-launch, deletion, and runtime-access regressions

- [ ] From a normal, non-nested Windows terminal, run repeated process-start
  probes and test deletion/runtime access:

```powershell
1..10 | ForEach-Object {
    $Output = (& $Codex sandbox -C $RepoRoot powershell.exe -NoProfile -Command "Get-Location" 2>&1) -join "`n"
    [pscustomobject]@{ attempt = $_; exit = $LASTEXITCODE; output = $Output }
}

$ProbeFile = Join-Path $RepoRoot ".codex-sandbox-delete-probe"
$Node = (Get-Command node -CommandType Application).Source
Set-Content -LiteralPath $ProbeFile -Value "probe"
$ChildCommand = "Remove-Item -LiteralPath '$ProbeFile'`n& '$Node' --version"
& $Codex sandbox -C $RepoRoot powershell.exe -NoProfile -Command $ChildCommand
[pscustomobject]@{ exit = $LASTEXITCODE; file_still_exists = Test-Path -LiteralPath $ProbeFile }
```

- Still broken: trivial commands fail with `CreateProcessWithLogonW failed: 5`,
  `1326`, `1907`, or `1909`; the disposable file cannot be deleted; or the
  managed runtime is inaccessible.
- Fixed/regression-free: all ten launches succeed, the file is deleted, and
  the runtime executes.

Sources: [issue #9062](https://github.com/openai/codex/issues/9062),
[issue #18620](https://github.com/openai/codex/issues/18620). The
[0.144.0 release](https://github.com/openai/codex/releases/tag/rust-v0.144.0)
states Windows writable-root deletion and managed-runtime access were fixed.

### B2. MCP servers can be registered but their tools may not reach new threads

- [ ] Temporarily register a harmless test server, verify registration,
  require an actual tool call, then remove it (see full script in the
  original research artifact if re-running this checkpoint).

- Still broken: `mcp list`/`mcp get`/app-server status show the server/tools,
  but the new thread cannot see or call them.
- Fixed/regression-free: a successful MCP tool-call event is present.

Source: [openai/codex issue #19649](https://github.com/openai/codex/issues/19649).

### B3. Routed MCP OAuth tokens may not refresh automatically

- Still broken: a tool invocation after token expiry (refresh-token window
  still valid) returns `invalid_grant`/`Authorization required`, requiring
  manual `codex mcp login`.
- Fixed/regression-free: the invocation succeeds without interaction.
- Do not read, print, or copy credential files as part of this test.

The 0.144.0 release fixed expired auth for the hosted first-party
`codex_apps` connector, but that does not prove routed third-party MCP
refresh behavior. Sources:
[issue #17265](https://github.com/openai/codex/issues/17265),
[0.144.0 release](https://github.com/openai/codex/releases/tag/rust-v0.144.0).

### B4. `--ephemeral resume` may still persist the supposedly ephemeral turn

- Still broken: the rollout file grows during `--ephemeral resume`, or a
  later normal resume can see the ephemeral question.
- Fixed/regression-free: rollout size unchanged; ephemeral turn absent from
  later history.

Source: [openai/codex issue #20084](https://github.com/openai/codex/issues/20084).

### B5. Resuming a thread whose compaction refers to a retired model

- Regression present: resume/compaction fails because the recorded model is
  retired, or continuity is lost.
- Regression absent: Codex retries with the current model and preserves
  continuity.
- If no sanitized fixture exists, record `TEST NEEDED`; never use a
  production hub thread for this test.

Declared fixed in [0.144.0](https://github.com/openai/codex/releases/tag/rust-v0.144.0),
referencing upstream change `#30319`.

### B6. Windows stdio MCP children may lose required environment variables

- Regression present: variables missing, child exits with `WinError 10106`,
  `EAI_FAIL`, `ENOENT`, or is misreported as a startup timeout.
- Regression absent: child receives required environment, completes MCP
  init.

Historical sources: [issue #3311](https://github.com/openai/codex/issues/3311),
[issue #4180](https://github.com/openai/codex/issues/4180).

## Audit record

Append one record after every version bump:

```markdown
#### Codex CLI <version> — <YYYY-MM-DD>

- Binary: `<absolute real codex.cmd path>`
- `CODEX_HOME`: `<path>`
- Auth preflight: `PASS | FAIL`
- A1 MCP inventory: `PASS | FAIL | CHANGED`
- A2 wrapper command set: `PASS | FAIL`
- A3 model provenance/catalog parity: `PASS | FAIL | CHANGED`
- A4 unauthenticated catalog behavior: `PASS | FAIL | CHANGED`
- A5 Windows unelevated semantics: `PASS | FAIL | CHANGED`
- A6 headless fork behavior: `PASS | FAIL | CHANGED`
- A7 repository model metadata parity: `PASS | FAIL`
- B1 Windows sandbox smoke: `PASS | FAIL | NOT APPLICABLE`
- B2 MCP thread injection: `PASS | FAIL | TEST NEEDED`
- B3 MCP OAuth refresh: `PASS | FAIL | TEST NEEDED`
- B4 ephemeral-resume persistence: `PASS | FAIL`
- B5 retired-model resume: `PASS | FAIL | TEST NEEDED`
- B6 Windows MCP environment inheritance: `PASS | FAIL | TEST NEEDED`
- Release notes reviewed: `<URLs>`
- New/removed root commands: `<list>`
- New/removed RPC methods or schema fields: `<list>`
- Repository changes required: `<files or none>`
```

Do not mark the update checkpoint complete while any machine-consumed model
ID, context limit, command classifier, session flag, or effective capability
inventory disagrees with the authenticated runtime.

#### Codex CLI 0.144.6 — 2026-07-24

- Binary: `_sys/env/nodejs/npm-global/codex.cmd`
- `CODEX_HOME`: `_sys/codex/config`
- Auth preflight: `PASS`
- A1 MCP inventory: `CHANGED` (known drift, `mcp list` still incomplete vs `mcpServerStatus/list`)
- A2 wrapper command set: `FAIL` (`delete` missing from `_CODEX_COMMANDS`, unfixed)
- A3 model provenance/catalog parity: `CHANGED` (no provenance field, unfixed — permanent limitation)
- A4 unauthenticated catalog behavior: `CHANGED` (silent bundled fallback, unfixed — permanent limitation)
- A5 Windows unelevated semantics: `PASS` (confirmed intentional, by design)
- A6 headless fork behavior: `CHANGED` (TTY requirement confirmed, unfixed — permanent limitation)
- A7 repository model metadata parity: `FAIL -> FIXED` (372k -> 272k, commit `af05e3b`)
- B1-B6: `TEST NEEDED` (not yet reproduced locally, upstream-reported only)
- Repository changes required: `_sys/ai/orchestration.json`, `_sys/ai/model-registry.json`, `_sys/docs-v2/specific/cx.md` (all fixed this pass)

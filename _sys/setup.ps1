# ================================================================
# setup.ps1  -  Portable Dev Environment Bootstrapper
#
# Location : [PortableDev]\_sys\setup.ps1
#
# Run from Zerobase (only README.md + _sys\ exist) to auto-install
# everything: Python, Node.js, FFmpeg, Git, VS Code, Claude Code CLI.
#
# Idempotent: already-installed components are skipped.
# Error-resilient: one component failing does NOT stop others.
#
# Usage:
#   Double-click INSTALL.bat at project root
#   OR: powershell -ExecutionPolicy Bypass -File _sys\setup.ps1
#
# Flags:
#   -SkipVSCode    Skip VS Code download (~100MB)
#   -SkipClaude    Skip Claude Code CLI npm install
#   -Force         Re-download/reinstall even if already present
# ================================================================

param(
    [switch]$SkipVSCode,
    [switch]$SkipClaude,
    [switch]$Force
)

$ErrorActionPreference = "Continue"
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8

# ── Paths ──────────────────────────────────────────────────────
$SYS_DIR    = $PSScriptRoot
$BASE_DIR   = (Get-Item -LiteralPath (Join-Path $SYS_DIR "..")).FullName
$ENV_DIR    = Join-Path $SYS_DIR "env"
$TOOLS_DIR  = Join-Path $SYS_DIR "tools"
$DATA_DIR   = Join-Path $SYS_DIR "data"
$SETUP_DIR  = Join-Path $DATA_DIR "setup-files"
$CLAUDE_DIR = Join-Path $SYS_DIR "claude"

# ── Versions (update here when new releases come out) ──────────
$V = @{
    Python = "3.13.4"
    NodeJS = "22.22.3"
    Git    = "2.49.0"
    VSCode = "1.100.2"
    Pwsh   = "7.6.2"
}

$URLs = @{
    Python = "https://www.python.org/ftp/python/$($V.Python)/python-$($V.Python)-embed-amd64.zip"
    NodeJS = "https://nodejs.org/dist/v$($V.NodeJS)/node-v$($V.NodeJS)-win-x64.zip"
    Git    = "https://github.com/git-for-windows/git/releases/download/v$($V.Git).windows.1/PortableGit-$($V.Git)-64-bit.7z.exe"
    FFmpeg = "https://github.com/BtbN/FFmpeg-Builds/releases/download/latest/ffmpeg-master-latest-win64-gpl-shared.zip"
    VSCode = "https://update.code.visualstudio.com/$($V.VSCode)/win32-x64-archive/stable"
    Pwsh   = "https://github.com/PowerShell/PowerShell/releases/download/v$($V.Pwsh)/PowerShell-$($V.Pwsh)-win-x64.zip"
}

# ── Output helpers ─────────────────────────────────────────────
function Write-Step($msg)    { Write-Host "`n>>> $msg" -ForegroundColor Cyan }
function Write-OK($msg)      { Write-Host "  [OK] $msg" -ForegroundColor Green }
function Write-Skip($msg)    { Write-Host "  [--] $msg (already installed)" -ForegroundColor DarkGray }
function Write-Info($msg)    { Write-Host "  [i]  $msg" -ForegroundColor Yellow }
function Write-Fail($msg)    { Write-Host "`n  [FAILED] $msg" -ForegroundColor Red }

# ── Utility functions ──────────────────────────────────────────
function Ensure-Dir($path) {
    if (-not (Test-Path -LiteralPath $path)) {
        New-Item -ItemType Directory -LiteralPath $path -Force | Out-Null
    }
}

function Download-File($url, $dest, $label) {
    Write-Info "Downloading $label..."
    $wc = New-Object System.Net.WebClient
    $wc.Headers.Add("User-Agent", "Mozilla/5.0")
    $wc.DownloadFile($url, $dest)
    $sizeMB = '{0:N1}' -f ((Get-Item -LiteralPath $dest).Length / 1MB)
    Write-OK "Downloaded: $(Split-Path $dest -Leaf) ($sizeMB MB)"
}

function Expand-Zip($zip, $dest) {
    Write-Info "Extracting..."
    Expand-Archive -LiteralPath $zip -DestinationPath $dest -Force
    Write-OK "Extracted"
}

# ── Failure tracking ───────────────────────────────────────────
$failures = [System.Collections.Generic.List[string]]::new()

function Run-Component($name, $block) {
    try {
        & $block
    } catch {
        Write-Fail "$name — $_"
        Write-Host "  Skipping $name and continuing..." -ForegroundColor DarkYellow
        $failures.Add($name)
    }
}

# ── 1. Folder structure ────────────────────────────────────────
Write-Step "Folder structure"
Run-Component "Folder structure" {
    @(
        $ENV_DIR, "$ENV_DIR\python", "$ENV_DIR\nodejs", "$ENV_DIR\ffmpeg",
        "$ENV_DIR\git",  "$ENV_DIR\vscode", "$ENV_DIR\venv", "$ENV_DIR\pwsh",
        $TOOLS_DIR, "$TOOLS_DIR\apps",
        "$CLAUDE_DIR\config", "$CLAUDE_DIR\agent",
        "$DATA_DIR\logs", "$DATA_DIR\temp", $SETUP_DIR,
        (Join-Path $BASE_DIR "workspace")
    ) | ForEach-Object { Ensure-Dir $_ }
    Write-OK "Folder structure ready"
}

# ── 2. Python ──────────────────────────────────────────────────
Write-Step "Python $($V.Python) (embeddable)"
Run-Component "Python" {
    $pyDir  = Join-Path $ENV_DIR "python"
    $pyExe  = Join-Path $pyDir "python.exe"
    if ($Force -or -not (Test-Path -LiteralPath $pyExe)) {
        $zipPath = Join-Path $SETUP_DIR "python-embed.zip"
        if ($Force -or -not (Test-Path -LiteralPath $zipPath)) {
            Download-File $URLs.Python $zipPath "Python $($V.Python)"
        }
        $tmpDir = Join-Path $SETUP_DIR "_python_tmp"
        Ensure-Dir $tmpDir
        Expand-Zip $zipPath $tmpDir
        $extracted = Get-ChildItem -LiteralPath $tmpDir -Directory | Select-Object -First 1
        $srcDir = if ($extracted) { $extracted.FullName } else { $tmpDir }
        Get-ChildItem -LiteralPath $srcDir |
            ForEach-Object { Move-Item -LiteralPath $_.FullName -Destination $pyDir -Force }
        if (Test-Path -LiteralPath $tmpDir) {
            Remove-Item -LiteralPath $tmpDir -Recurse -Force
        }

        # Enable pip: uncomment "import site" in ._pth file
        $pthFile = Get-ChildItem -LiteralPath $pyDir -Filter "python*._pth" |
                   Select-Object -First 1
        if ($pthFile) {
            $content = Get-Content -LiteralPath $pthFile.FullName -Raw
            $content = $content -replace '#import site', 'import site'
            Set-Content -LiteralPath $pthFile.FullName -Value $content -Encoding UTF8
            Write-OK "pip enabled ($($pthFile.Name))"
        }

        # Install pip via get-pip.py
        $getPip = Join-Path $SETUP_DIR "get-pip.py"
        if (-not (Test-Path -LiteralPath $getPip)) {
            Download-File "https://bootstrap.pypa.io/get-pip.py" $getPip "get-pip.py"
        }
        & $pyExe $getPip --no-warn-script-location 2>&1 | Out-Null
        Write-OK "Python ready"
    } else {
        Write-Skip "Python"
    }
}

# ── 3. Node.js ─────────────────────────────────────────────────
Write-Step "Node.js $($V.NodeJS)"
Run-Component "Node.js" {
    $nodeDir = Join-Path $ENV_DIR "nodejs"
    $nodeExe = Join-Path $nodeDir "node.exe"
    if ($Force -or -not (Test-Path -LiteralPath $nodeExe)) {
        $zipPath = Join-Path $SETUP_DIR "nodejs.zip"
        if ($Force -or -not (Test-Path -LiteralPath $zipPath)) {
            Download-File $URLs.NodeJS $zipPath "Node.js $($V.NodeJS)"
        }
        $tmpDir = Join-Path $SETUP_DIR "_nodejs_tmp"
        Ensure-Dir $tmpDir
        Expand-Zip $zipPath $tmpDir
        $extracted = Get-ChildItem -LiteralPath $tmpDir -Directory | Select-Object -First 1
        if ($extracted) {
            Get-ChildItem -LiteralPath $extracted.FullName |
                ForEach-Object { Move-Item -LiteralPath $_.FullName -Destination $nodeDir -Force }
            Remove-Item -LiteralPath $tmpDir -Recurse -Force
        }
        Write-OK "Node.js ready"
    } else {
        Write-Skip "Node.js"
    }
}

# ── 4. FFmpeg ──────────────────────────────────────────────────
Write-Step "FFmpeg (latest)"
Run-Component "FFmpeg" {
    $ffmpegDir = Join-Path $ENV_DIR "ffmpeg"
    $ffmpegExe = Join-Path $ffmpegDir "bin\ffmpeg.exe"
    if ($Force -or -not (Test-Path -LiteralPath $ffmpegExe)) {
        $zipPath = Join-Path $SETUP_DIR "ffmpeg.zip"
        if ($Force -or -not (Test-Path -LiteralPath $zipPath)) {
            Download-File $URLs.FFmpeg $zipPath "FFmpeg"
        }
        $tmpDir = Join-Path $SETUP_DIR "_ffmpeg_tmp"
        Ensure-Dir $tmpDir
        Expand-Zip $zipPath $tmpDir
        $extracted = Get-ChildItem -LiteralPath $tmpDir -Directory | Select-Object -First 1
        if ($extracted) {
            $binSrc = Join-Path $extracted.FullName "bin"
            if (Test-Path -LiteralPath $binSrc) {
                $binDest = Join-Path $ffmpegDir "bin"
                Ensure-Dir $binDest
                Get-ChildItem -LiteralPath $binSrc |
                    ForEach-Object { Move-Item -LiteralPath $_.FullName -Destination $binDest -Force }
            }
            Remove-Item -LiteralPath $tmpDir -Recurse -Force
        }
        Write-OK "FFmpeg ready"
    } else {
        Write-Skip "FFmpeg"
    }
}

# ── 5. Git ─────────────────────────────────────────────────────
Write-Step "Git $($V.Git) (portable)"
Run-Component "Git" {
    $gitDir = Join-Path $ENV_DIR "git"
    $gitExe = Join-Path $gitDir "cmd\git.exe"
    if ($Force -or -not (Test-Path -LiteralPath $gitExe)) {
        $exePath = Join-Path $SETUP_DIR "PortableGit.7z.exe"
        if ($Force -or -not (Test-Path -LiteralPath $exePath)) {
            Download-File $URLs.Git $exePath "Git $($V.Git) Portable"
        }
        Write-Info "Extracting Git (self-extracting archive)..."
        $proc = Start-Process -FilePath $exePath `
                              -ArgumentList "-o`"$gitDir`"", "-y" `
                              -Wait -PassThru -WindowStyle Hidden
        if ($proc.ExitCode -ne 0) {
            throw "Git extraction exited with code $($proc.ExitCode)"
        }
        Write-OK "Git ready"
    } else {
        Write-Skip "Git"
    }
}

# ── 6. VS Code ─────────────────────────────────────────────────
if (-not $SkipVSCode) {
    Write-Step "VS Code $($V.VSCode) (portable)"
    Run-Component "VS Code" {
        $vscDir = Join-Path $ENV_DIR "vscode"
        $vscExe = Join-Path $vscDir "Code.exe"
        if ($Force -or -not (Test-Path -LiteralPath $vscExe)) {
            $zipPath = Join-Path $SETUP_DIR "vscode.zip"
            if ($Force -or -not (Test-Path -LiteralPath $zipPath)) {
                Download-File $URLs.VSCode $zipPath "VS Code $($V.VSCode)"
            }
            Expand-Zip $zipPath $vscDir
            Ensure-Dir (Join-Path $vscDir "data")   # portable mode
            Write-OK "VS Code ready (portable mode enabled)"
        } else {
            Write-Skip "VS Code"
        }
    }
} else {
    Write-Info "VS Code skipped (-SkipVSCode)"
}

# ── 6.5. PowerShell 7 ─────────────────────────────────────────
Write-Step "PowerShell $($V.Pwsh)"
Run-Component "PowerShell 7" {
    $pwshDir = Join-Path $ENV_DIR "pwsh"
    $pwshExe = Join-Path $pwshDir "pwsh.exe"
    if ($Force -or -not (Test-Path -LiteralPath $pwshExe)) {
        $zipPath = Join-Path $SETUP_DIR "pwsh.zip"
        if ($Force -or -not (Test-Path -LiteralPath $zipPath)) {
            Download-File $URLs.Pwsh $zipPath "PowerShell $($V.Pwsh)"
        }
        Expand-Zip $zipPath $pwshDir
        Write-OK "PowerShell 7 ready"
    } else {
        Write-Skip "PowerShell 7"
    }
}

# ── 7. Python venv ─────────────────────────────────────────────
Write-Step "Python virtual environment"
Run-Component "Python venv" {
    $venvDir  = Join-Path $ENV_DIR "venv"
    $venvPy   = Join-Path $venvDir "Scripts\python.exe"
    $pyExe    = Join-Path $ENV_DIR "python\python.exe"
    if ($Force -or -not (Test-Path -LiteralPath $venvPy)) {
        if (-not (Test-Path -LiteralPath $pyExe)) {
            throw "python.exe not found — install Python first"
        }
        Write-Info "Creating venv..."
        & $pyExe -m venv $venvDir
        Write-OK "venv ready"
    } else {
        Write-Skip "Python venv"
    }
}

# ── 8. Claude Code CLI ─────────────────────────────────────────
if (-not $SkipClaude) {
    Write-Step "Claude Code CLI"
    Run-Component "Claude Code CLI" {
        $npmGlobal = Join-Path $ENV_DIR "nodejs\npm-global"
        Ensure-Dir $npmGlobal

        $env:NPM_CONFIG_PREFIX = $npmGlobal
        $env:NPM_CONFIG_CACHE  = Join-Path $ENV_DIR "nodejs\npm-cache"
        $env:PATH              = "$(Join-Path $ENV_DIR 'nodejs');$env:PATH"

        $claudeCmd = Join-Path $npmGlobal "claude.cmd"
        if ($Force -or -not (Test-Path -LiteralPath $claudeCmd)) {
            Write-Info "npm install -g @anthropic-ai/claude-code ..."
            $npmExe = Join-Path $ENV_DIR "nodejs\npm.cmd"
            & $npmExe install -g "@anthropic-ai/claude-code" 2>&1 |
                ForEach-Object { Write-Host "  $_" }
            if (Test-Path -LiteralPath $claudeCmd) {
                Write-OK "Claude Code CLI ready"
            } else {
                throw "claude.cmd not found after install — check npm output above"
            }
        } else {
            Write-Skip "Claude Code CLI"
        }
    }
} else {
    Write-Info "Claude Code CLI skipped (-SkipClaude)"
}

# ── 9. Context menu ────────────────────────────────────────────
Write-Step "Context menu registration"
Run-Component "Context menu" {
    & (Join-Path $SYS_DIR "manage.ps1") -Action Register -Silent
    Write-OK "Context menu registered"
}

# ── Summary ────────────────────────────────────────────────────
Write-Host ""
if ($failures.Count -eq 0) {
    Write-Host "======================================================" -ForegroundColor Green
    Write-Host "  Setup complete! All components installed." -ForegroundColor Green
} else {
    Write-Host "======================================================" -ForegroundColor Yellow
    Write-Host "  Setup finished with $($failures.Count) failure(s):" -ForegroundColor Yellow
    foreach ($f in $failures) {
        Write-Host "    - $f" -ForegroundColor Red
    }
    Write-Host "  Re-run setup.ps1 -Force to retry failed components." -ForegroundColor Yellow
}
Write-Host ""
Write-Host "  Next steps:" -ForegroundColor White
Write-Host "  1. Right-click any folder -> 'Open in Sandbox ($((Split-Path $BASE_DIR -Leaf)))'" -ForegroundColor Gray
Write-Host "  2. In VS Code terminal: claude  (log in to Anthropic)" -ForegroundColor Gray
Write-Host "  3. Copy _sys\context\CLAUDE_global.md -> _sys\claude\config\CLAUDE.md" -ForegroundColor Gray
Write-Host "======================================================" -ForegroundColor $(if ($failures.Count -eq 0) { "Green" } else { "Yellow" })
Write-Host ""

if ($Host.Name -eq "ConsoleHost") {
    Read-Host "Press Enter to exit"
}

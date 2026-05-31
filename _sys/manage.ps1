# ================================================================
# manage.ps1  -  Unified Sandbox Environment Manager
#
# Location  : [PortableDev]\_sys\manage.ps1
#
# Actions   : Register, Unregister
#
# Features  :
#   - Single Source of Truth for naming and mapping logic.
#   - State-aware registration: cleans up orphaned registry keys.
#   - Aggressive global cleanup: removes all broken/legacy keys and SUBSTs.
# ================================================================

param(
    [Parameter(Mandatory=$true)][ValidateSet('Register', 'Unregister')]
    [string]$Action,
    [string]$BaseDir,
    [switch]$Silent
)

[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$OutputEncoding = [System.Text.Encoding]::UTF8

# ----------------------------------------------------------------
# 1. Initialization & Normalisation
# ----------------------------------------------------------------
if (-not $BaseDir) { $BaseDir = (Get-Item -LiteralPath (Join-Path $PSScriptRoot "..")).FullName }

try {
    $BaseDir = (Get-Item -LiteralPath $BaseDir -ErrorAction Stop).FullName
} catch {
    Write-Host "[Error] BaseDir not found: $BaseDir" -ForegroundColor Red
    if (-not $Silent) { Read-Host "Press Enter to exit" }; exit 1
}

$leaf        = Split-Path $BaseDir -Leaf
$parentPath  = Split-Path $BaseDir -Parent
$parentName  = if ($parentPath) { Split-Path $parentPath -Leaf } else { $null }
if ($parentName -and $parentName -match '^[A-Z]:$') { $parentName = $null }

$drivePhys   = (Split-Path $BaseDir -Qualifier).Replace(":", "")
$sysDir      = Join-Path $BaseDir "_sys"
$configPath  = Join-Path $sysDir "local.config.bat"
$codePath    = Join-Path $sysDir "env\vscode\Code.exe"
$launchScript = Join-Path $sysDir "launch.ps1"

# Unique Registry Key (Safe: replace colon and backslash)
$keyBase      = if ($parentName) { "${drivePhys}_${parentName}_${leaf}" } else { "${drivePhys}_${leaf}" }
$TARGET_KEY   = "SandboxRun_$($keyBase -replace '[\\/:]', '_')"

# ----------------------------------------------------------------
# 2. State Loading
# ----------------------------------------------------------------
$state = @{ SUBST_DRIVE_LETTER = $null; MENU_REG_KEY = $null }
if (Test-Path -LiteralPath $configPath) {
    $content = Get-Content -LiteralPath $configPath -Raw
    if ($content -match 'SUBST_DRIVE_LETTER=([A-Z])') { $state.SUBST_DRIVE_LETTER = $Matches[1] }
    if ($content -match 'MENU_REG_KEY=(SandboxRun_[A-Za-z0-9_]+)') { $state.MENU_REG_KEY = $Matches[1] }
}

# ----------------------------------------------------------------
# 3. Helpers
# ----------------------------------------------------------------

function Set-GeminiPortability($baseDir) {
    $geminiHost = Join-Path $env:USERPROFILE ".gemini"
    $geminiPortable = Join-Path $baseDir "_sys\gemini\config"
    
    if (-not (Test-Path $geminiPortable)) { New-Item -ItemType Directory -Path $geminiPortable -Force | Out-Null }

    if (Test-Path -LiteralPath $geminiHost) {
        $item = Get-Item -LiteralPath $geminiHost
        if ($item.Attributes -match "ReparsePoint") {
            $target = (Get-Item -LiteralPath $geminiHost).Target
            if ($target -eq $geminiPortable) {
                Write-Host "  [OK] Gemini Portability already active." -ForegroundColor Green
                return
            }
        } else {
            $backup = "${geminiHost}.host_backup"
            if (-not (Test-Path -LiteralPath $backup)) {
                Move-Item -LiteralPath $geminiHost -Destination $backup -Force
                Write-Host "  [Info] Backed up host Gemini config to .gemini.host_backup" -ForegroundColor Gray
            } else {
                Write-Host "  [Warning] .gemini and .gemini.host_backup both exist. Skipping junction." -ForegroundColor Yellow
                return
            }
        }
    }
    
    # Create Junction (mklink /J target source) -> mklink /J %USERPROFILE%\.gemini [PortablePath]\_sys\gemini\config
    & cmd /c "mklink /J `"$geminiHost`" `"$geminiPortable`"" | Out-Null
    if ($LASTEXITCODE -eq 0) {
        Write-Host "  [OK] Gemini Portability enabled (Junction created)" -ForegroundColor Green
    } else {
        Write-Host "  [Fail] Could not create Gemini junction." -ForegroundColor Red
    }
}

function Remove-GeminiPortability($baseDir) {
    $geminiHost = Join-Path $env:USERPROFILE ".gemini"
    $geminiPortable = Join-Path $baseDir "_sys\gemini\config"
    
    if (Test-Path -LiteralPath $geminiHost) {
        $item = Get-Item -LiteralPath $geminiHost
        if ($item.Attributes -match "ReparsePoint") {
            $target = (Get-Item -LiteralPath $geminiHost).Target
            if ($target -eq $geminiPortable) {
                & cmd /c "rmdir `"$geminiHost`"" | Out-Null
                Write-Host "  [OK] Gemini Portability disabled (Junction removed)" -ForegroundColor Green
                
                $backup = "${geminiHost}.host_backup"
                if (Test-Path -LiteralPath $backup) {
                    Move-Item -LiteralPath $backup -Destination $geminiHost -Force
                    Write-Host "  [Info] Restored host Gemini config from .gemini.host_backup" -ForegroundColor Gray
                }
            }
        }
    }
}

function Global-Cleanup($targetBaseDir, $targetLeaf) {
    Write-Host "  [Info] Performing global cleanup for $targetLeaf..." -ForegroundColor Gray
    
    # 1. Remove ANY SUBST drive pointing to this BaseDir
    $substLines = & cmd /c subst 2>$null
    foreach ($line in $substLines) {
        if ($line -match '^([A-Z]):') {
            $drive = $Matches[1]
            if ($line -imatch [regex]::Escape($targetBaseDir)) {
                & cmd /c "subst ${drive}: /D" 2>$null
                Write-Host "  [OK] Released SUBST: ${drive}:" -ForegroundColor Green
            }
        }
    }

    # 2. Aggressively remove ANY Registry Key matching patterns
    $registryRoots = @(
        "HKCU:\Software\Classes\Directory\Background\shell",
        "HKCU:\Software\Classes\Directory\shell",
        "HKCU:\Software\Classes\*\shell",
        "HKCU:\Software\Classes\lnkfile\shell"
    )
    foreach ($root in $registryRoots) {
        if (Test-Path -LiteralPath $root) {
            $keys = Get-ChildItem -LiteralPath $root -ErrorAction SilentlyContinue
            foreach ($k in $keys) {
                if ($k.Name -match "SandboxRun_.*($targetLeaf|_D_D_|${drivePhys}_${drivePhys})") {
                    try {
                        Remove-Item -LiteralPath $k.PSPath -Recurse -Force -ErrorAction Stop
                        Write-Host "  [OK] Removed Orphan Registry: $($k.Name)" -ForegroundColor Gray
                    } catch {
                        Write-Host "  [Fail] Could not remove key: $($k.Name)" -ForegroundColor Red
                    }
                }
            }
        }
    }
}

# ----------------------------------------------------------------
# 4. Action Execution
# ----------------------------------------------------------------

if ($Action -eq "Unregister") {
    Write-Host "`n===================================================" -ForegroundColor Cyan
    Write-Host " Unregistering: $leaf" -ForegroundColor Cyan
    Write-Host "===================================================" -ForegroundColor Cyan

    Global-Cleanup $BaseDir $leaf
    Remove-GeminiPortability $BaseDir

    if (Test-Path -LiteralPath $configPath) {
        $userLines = Get-Content -LiteralPath $configPath | Where-Object { $_ -notmatch '^\:\: \[(/)?auto\]' -and $_ -notmatch '^set "(BASE_DIR_PHYS|MENU_REG_KEY|SUBST_DRIVE_LETTER|CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS)=' }
        $nonEmpty = $userLines | Where-Object { $_.Trim() -ne '' }
        if ($nonEmpty) {
            ($userLines -join "`r`n") | Set-Content -LiteralPath $configPath -Encoding UTF8
        } else {
            Remove-Item -LiteralPath $configPath -Force
        }
        Write-Host "  [OK] local.config.bat cleaned" -ForegroundColor Green
    }

    Write-Host "`n Unregistration complete." -ForegroundColor Green
    if (-not $Silent) { Read-Host "Press Enter to exit" }
    exit 0
}

if ($Action -eq "Register") {
    Write-Host "`n===================================================" -ForegroundColor Cyan
    Write-Host " Registering: $leaf" -ForegroundColor Cyan
    Write-Host "===================================================" -ForegroundColor Cyan

    Global-Cleanup $BaseDir $leaf
    Set-GeminiPortability $BaseDir

    $assignedLetter = $null
    $prefer = $leaf.Substring(0, 1).ToUpper()
    $reserved = @('A', 'B', 'C')
    $all = 65..90 | ForEach-Object { [char]$_ }
    $candidates = @($prefer) + ($all | Where-Object { $_ -notin $reserved -and $_ -ne $prefer })
    foreach ($letter in $candidates) {
        if (-not (Test-Path "${letter}:\")) {
            & cmd /c "subst ${letter}: `"$BaseDir`"" 2>&1 | Out-Null
            if ($LASTEXITCODE -eq 0) { 
                $assignedLetter = $letter
                Write-Host "  [Info] Waiting for drive ${assignedLetter}: to stabilize..." -NoNewline -ForegroundColor Gray
                for ($i = 1; $i -le 10; $i++) {
                    if (Test-Path "${assignedLetter}:\") {
                        Write-Host " [Ready]" -ForegroundColor Green
                        break
                    }
                    Write-Host "." -NoNewline -ForegroundColor Gray
                    Start-Sleep -Seconds 1
                }
                break 
            }
        }
    }

    $cleanPath    = $BaseDir.TrimEnd('\')
    $substDisplay = if ($assignedLetter) { " ($cleanPath -> $($assignedLetter):)" } else { " ($cleanPath)" }
    $menuLabel    = "Open in Sandbox: $leaf$substDisplay"

    $targets = @(
        @{ Path = "HKCU:\Software\Classes\Directory\Background\shell\$TARGET_KEY"; Arg = "%V" }
        @{ Path = "HKCU:\Software\Classes\Directory\shell\$TARGET_KEY";            Arg = "%V" }
        @{ Path = "HKCU:\Software\Classes\*\shell\$TARGET_KEY";                    Arg = "%1" }
        @{ Path = "HKCU:\Software\Classes\lnkfile\shell\$TARGET_KEY";              Arg = "%1" }
    )

    foreach ($t in $targets) {
        try {
            if (-not (Test-Path -LiteralPath $t.Path)) { New-Item -Path $t.Path -Force | Out-Null }
            Set-ItemProperty -LiteralPath $t.Path -Name "(default)"    -Value $menuLabel
            Set-ItemProperty -LiteralPath $t.Path -Name "HasLUAShield" -Value ""
            if (Test-Path -LiteralPath $codePath) { Set-ItemProperty -LiteralPath $t.Path -Name "Icon" -Value $codePath }
            
            $cmdKey = "$($t.Path)\command"
            if (-not (Test-Path -LiteralPath $cmdKey)) { New-Item -Path $cmdKey -Force | Out-Null }
            $cmd = "powershell.exe -NoProfile -WindowStyle Hidden -ExecutionPolicy Bypass -File `"$launchScript`" -Target `"$($t.Arg)`""
            Set-ItemProperty -LiteralPath $cmdKey -Name "(default)" -Value $cmd
        } catch {
            Write-Host "  [Warning] Registry error on $($t.Path)" -ForegroundColor Yellow
        }
    }
    Write-Host "  [OK] Context Menu registered: $menuLabel" -ForegroundColor Green

    $autoBlock = @(
        ":: [auto] Generated by manage.ps1 - do not edit this block"
        "set `"BASE_DIR_PHYS=$BaseDir`""
        "set `"MENU_REG_KEY=$TARGET_KEY`""
        "set `"SUBST_DRIVE_LETTER=$assignedLetter`""
        "set `"CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS=1`""
        ":: [/auto]"
    )

    $userLines = @()
    if (Test-Path -LiteralPath $configPath) {
        $userLines = Get-Content -LiteralPath $configPath | Where-Object { $_ -notmatch '^\:\: \[(/)?auto\]' -and $_ -notmatch '^set "(BASE_DIR_PHYS|MENU_REG_KEY|SUBST_DRIVE_LETTER|CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS)=' }
    }
    $newConfig = ($autoBlock + @("") + $userLines) -join "`r`n"
    [System.IO.File]::WriteAllText($configPath, $newConfig, [System.Text.UTF8Encoding]::new($false))
    Write-Host "  [OK] State saved to local.config.bat" -ForegroundColor Green

    Write-Host "`n Registration complete!" -ForegroundColor Green
    if (-not $Silent) { Read-Host "`nPress Enter to exit" }
    exit 0
}

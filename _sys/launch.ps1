# ================================================================
# launch.ps1  -  Registry command -> start.bat relay script
#
# Location: [PortableDev]\_sys\launch.ps1
# Called by: Windows Explorer right-click menu (via registry)
# NOT intended for direct user execution.
#
# Handles path safety:
#   Registry: powershell -File "launch.ps1" -Target "%V"
#   Explorer expands %V: ...launch.ps1" -Target "C:\My Folder"
#   This script: cmd /c call "start.bat" "C:\My Folder"
#   start.bat receives: %~1 = C:\My Folder  (quotes auto-stripped)
# ================================================================
param(
    [string]$Target = ""
)

$bat = Join-Path $PSScriptRoot "start.bat"

if ($Target -eq "") {
    $cmdArgs = "/c call `"$bat`" || pause"
} else {
    $cmdArgs = "/c call `"$bat`" `"$Target`" || pause"
}

Start-Process -FilePath "cmd.exe" -ArgumentList $cmdArgs

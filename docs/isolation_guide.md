# Optional isolation providers

Run `engram isolation check` for a read-only check, or
`engram isolation check --json` for stable codes, reasons, capabilities, and
guidance. No Windows features are enabled, no distributions or VMs are created,
and no files are written by this check. UNAVAILABLE is normal: a completed check
exits 0 even when neither provider is available. Internal errors exit 1; invalid
arguments exit 2. Optional provider probe failures do not crash Engram.

Windows Sandbox uses a separate kernel and isolates guest execution from the
host. Explicit writable shares still expose host data. WSL2 provides Linux
compatibility and reproducibility, not equivalent security isolation: Windows
filesystem/executable interop and network access remain possible. The WSL2
provider does not enforce the profile's network restriction. Select a provider
explicitly according to your testing and security needs; WSL2 is not an automatic
security fallback for Sandbox.

See Microsoft's [Sandbox overview](https://learn.microsoft.com/en-us/windows/security/application-security/application-isolation/windows-sandbox/windows-sandbox-overview)
and [Sandbox CLI reference](https://learn.microsoft.com/en-us/windows/security/application-security/application-isolation/windows-sandbox/windows-sandbox-cli).

## Availability scenarios

The excerpts below show the status and representative reason lines. Each full
human report also prints the guidance title, explanation, setup requirements,
steps with example commands, and what still works. Exact reasons depend on the
Windows build, runner error, and supported command set.

Both available: select Sandbox for isolated Windows tests and WSL2 for Linux
compatibility tests.

```text
windows-sandbox: AVAILABLE (OK)
  Reason: Raw lifecycle probes succeeded; CLI; guest evidence capture
wsl2: AVAILABLE (OK)
  Reason: Linux compatibility/reproducibility only; not security-equivalent to Sandbox; Windows filesystem/executable/network interop remains possible; no network enforcement; parallel private distros supported, serialized default
```

Sandbox only: Windows isolation works; Linux provider tests remain optional.

```text
windows-sandbox: AVAILABLE (OK)
  Reason: Raw lifecycle probes succeeded; CLI; guest evidence capture
wsl2: UNAVAILABLE (WSL_NOT_INSTALLED)
  Reason: Probe failed: FileNotFoundError: ...; Linux compatibility/reproducibility only; ...
```

WSL only: Linux compatibility tests work. Do not treat WSL as a substitute for
Sandbox security isolation.

```text
windows-sandbox: UNAVAILABLE (WSB_UNSUPPORTED_EDITION)
  Reason: Probe failed: FileNotFoundError: ...
wsl2: AVAILABLE (OK)
  Reason: Linux compatibility/reproducibility only; ...
```

Neither: normal Engram workflows (`open`, `doctor`, updates, and ordinary host
tests) still work. Optional isolation tests can be skipped until setup is ready.

```text
windows-sandbox: UNAVAILABLE (WSB_FEATURE_DISABLED)
  Reason: Probe failed: RuntimeError: wsb.exe list failed with process exit ...
wsl2: UNAVAILABLE (WSL_NOT_INSTALLED)
  Reason: Probe failed: FileNotFoundError: ...; Linux compatibility/reproducibility only; ...
```

For example, a disabled Sandbox block also includes:

```text
  Sandbox feature disabled: The structured Windows feature probe reports Sandbox is disabled.
  Setup may need administrator: True; reboot: True
  - Enable Sandbox in administrator PowerShell: Enable-WindowsOptionalFeature -Online -FeatureName Containers-DisposableClientVM -All
  - Restart Windows after enabling the feature; confirm virtualization is enabled in BIOS/UEFI.
  - Verify: wsb list --raw
  Without it: Engram open, doctor, updates, and ordinary host workflows still work; another available provider can be selected explicitly.
```

## Troubleshooting

The guidance SSOT is `_sys/config/isolation-guidance.json`, validated against
`isolation-guidance.schema.json`. Codes come from exceptions, numeric exit codes,
or structured OS probes, never localized error messages. Unknown or absent codes
receive generic guidance. A timeout, access denial, malformed result, or failed
supplemental query does not prove that a feature is disabled or unsupported.

| Code / symptom | Action | Administrator / reboot |
| --- | --- | --- |
| `OK` | No setup action required. | No / no |
| `WSB_CLI_MISSING` | Check edition and update Windows; older builds may have the desktop app without `wsb.exe`. Verify `wsb list --raw`. The provider needs raw list/stop support even with LogonCommand fallback. | Updates or feature setup may need both |
| `WSB_FEATURE_DISABLED` | Administrator PowerShell: `Enable-WindowsOptionalFeature -Online -FeatureName Containers-DisposableClientVM -All` | Yes / yes |
| `WSB_UNSUPPORTED_EDITION` | Windows Home has no Sandbox. Use a supported edition for Sandbox, or WSL for compatibility testing. | No command can enable Sandbox on Home |
| `WSL_NOT_INSTALLED` | Administrator PowerShell: `wsl --install --no-distribution`; then `wsl --update` and `wsl --version` | Yes / restart if requested |
| `WSL_PROBE_FAILED` | Retry `wsl --version`, run `wsl --update`, complete any pending restart, then retry the check. | Setup may need both |
| `PROBE_ERROR` / unknown code | Retry `engram isolation check`; inspect `wsb list --raw` and `wsl --version` directly. Avoid diagnosing from translated text. | Depends on cause |
| Virtualization off | Enable hardware virtualization in BIOS/UEFI; follow your machine vendor's instructions. | Firmware access / reboot |

Sandbox feature queries may require elevation; if a standard-user query fails,
the check keeps the best diagnosis from the original failure. A working
`WindowsSandbox.exe` alone does not satisfy the provider's verified teardown
requirements. See Microsoft's [WSL installation](https://learn.microsoft.com/en-us/windows/wsl/install)
and [WSL troubleshooting](https://learn.microsoft.com/en-us/windows/wsl/troubleshooting).

## Opt-in live tests

Offline unit tests use fake runners and do not launch either provider. To opt in
on a prepared Windows host, run these from the repo root in PowerShell. Live tests
create temporary VMs/private distros and writable evidence in pytest temporary
directories; they do not use a repository archive directory.

```powershell
$env:ENGRAM_WINDOWS_SANDBOX_LIVE = '1'
python -m pytest _sys/tests/unit/test_windows_sandbox_provider.py -k live
Remove-Item Env:ENGRAM_WINDOWS_SANDBOX_LIVE

$env:ENGRAM_WSL2_LIVE = '1'
$env:ENGRAM_WSL2_ROOTFS = (Resolve-Path ./alpine-minirootfs.tar.gz).Path
python -m pytest _sys/tests/unit/test_wsl2_provider.py -k live
Remove-Item Env:ENGRAM_WSL2_LIVE
Remove-Item Env:ENGRAM_WSL2_ROOTFS
```

Supply an Alpine minirootfs `tar.gz` as `ENGRAM_WSL2_ROOTFS`; the WSL test imports
a fresh private WSL2 distro from it. Download it separately from the official
Alpine distribution site. Availability is not proof that a supplied rootfs or a
particular guest command will work. Lifecycle tool failures retain their exception
types and include the hint "run `engram isolation check`".

See the [CLI reference](cli_reference.md) for the command's complete help.

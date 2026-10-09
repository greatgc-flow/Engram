# CP949 / Korean-Locale Path Verification Gate

This document describes the testing architecture and verification procedures for CP949 (Korean locale) path resilience in Engram, implementing Decision D (EN-GAP-P0-006).

---

## 1. Background and Motivation

Engram supports portable installations located in directories with Korean and CJK characters (e.g., `D:\한글폴더\PortableDev`).
Windows handles non-Unicode legacy commands and Explorer context menus via the active ANSI Code Page (ACP). On Korean Windows systems, this codepage is **CP949** (a superset of EUC-KR). Python's `"mbcs"` codec maps directly to the active system ACP.

On standard hosted CI runners (GitHub Actions `windows-latest`), the system ACP is **CP1252** (Western European), which cannot encode Korean characters. Reconfiguring the hosted system ACP to CP949 (`Set-WinSystemLocale ko-KR`) requires an OS reboot, which is not supported cleanly on hosted runners.

Historically, this caused Korean-path tests to silently skip on hosted CI via conditional skip markers.

---

## 2. Hosted CI Emulation Strategy (Option D)

To ensure regressions in path encoding, sidecar writing, and batch relay execution are caught on every pull request, hosted CI uses an **encoding boundary emulation strategy**:

1. **Explicit CP949 Injection**:
   When the host system's ANSI codepage cannot encode Korean (`"한글".encode("mbcs")` raises `UnicodeEncodeError`), the test fixture intercepts the registrar's encoding boundary and explicitly encodes sidecars and relays using `cp949`.
2. **Exact Sidecar Byte Assertions**:
   Tests verify that `.physroot.txt` and `.root.txt` sidecar files match the exact raw CP949 byte sequences expected on disk (`str(path).encode("cp949")`).
3. **Batch Execution under `chcp 949`**:
   Relay `.bat` scripts and environment handoff batch routines are executed with console codepage set to 949 (`chcp 949 >nul && ...`) to verify that `set /p` and `cmd.exe` path expansions work end-to-end.

### Strict CI Verification Step
In `.github/workflows/ci.yml`, a dedicated verification step runs:

```powershell
python -u -m pytest _sys/tests/unit -v -m cp949 --cp949-strict --tb=short
```

The `--cp949-strict` flag (handled in `conftest.py`) enforces:
- **Zero skips**: Fails unconditionally if any test marked `cp949` is skipped.
- **Non-empty set**: Fails unconditionally if 0 tests are collected.

---

## 3. Known Residual Gap Note

> [!WARNING]
> **Injected encoding cannot prove production MBCS behavior.**
> Emulating CP949 at Python's encoding boundary and running `chcp 949` proves that Engram's batch parsing, sidecar contracts, quoting rules, and handoff files correctly handle CP949 bytes. However, it cannot prove that external Windows system APIs (such as Windows Explorer shell registration, native file dialogs, or OS APIs that inspect the system ACP directly) will behave identically on a real CP949 system.

---

## 4. Pre-Release Local Verification Gate (Real System ACP)

To close the residual gap, proof under a **real system ACP** (ACP = 949) is maintained as a **mandatory release-time gate** (run prior to tagging releases), rather than a per-commit CI gate.

### Pre-Release Verification Procedure

1. **Verify Local Machine Codepage**:
   Run the following in PowerShell on the release machine:
   ```powershell
   [System.Text.Encoding]::Default.CodePage
   ```
   Confirm that the output is `949`.

2. **Execute the CP949 Test Suite**:
   Execute the full suite of CP949 tests:
   ```powershell
   python -u -m pytest _sys/tests/unit -v -m cp949 --cp949-strict
   ```

3. **Verify Expectations**:
   - All tests in the `cp949` test set must pass.
   - Skips must be `0`.
   - Native MBCS roundtripping must succeed without monkeypatching or emulation.

4. **Record the Result**:
   Attach the test run output to the release checklist or audit record for the target release.

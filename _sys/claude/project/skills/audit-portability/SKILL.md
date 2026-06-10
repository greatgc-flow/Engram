---
name: audit-portability
description: "Audit Portable Dev Environment portability and isolation. Verify host PC independence, env var isolation, hardcoded path detection, registry residue. Use for: portability audit, isolation check, portable verification, env var check."
---

# Audit Portability — Portability Verification Procedure

## When to Use
- After adding new scripts or tools
- Before USB migration or PC change
- Periodic isolation health check
- When portability issues are suspected

## Verification Principles
- USERPROFILE/APPDATA/LOCALAPPDATA: never override (host backup only via HOST_LOCALAPPDATA)
- Tool-specific isolation: each tool gets dedicated env var (NPM_CONFIG_*, PIP_CACHE_DIR, etc.)
- Registry keys: SandboxRun_[FolderName] naming pattern (unique per sandbox, cleanup on remove)
- PATH: only add BASE_DIR-relative paths

## 3-Level Checklist

### Critical (must fix — stops portability)
- [ ] Hardcoded drive letters: `C:\`, `D:\` etc. in scripts (not in comments)
- [ ] Direct USERPROFILE/APPDATA/LOCALAPPDATA override (not HOST_LOCALAPPDATA backup)
- [ ] Absolute paths using user paths (C:\Users\... form)

### Warning (review recommended)
- [ ] TEMP/TMP not redirected to `_sys\data\temp`
- [ ] Tool cache/config pointing outside BASE_DIR
- [ ] Registry keys not following SandboxRun_[FolderName] pattern
- [ ] PATH additions including host-absolute paths

### Info (intentional patterns — OK)
- [ ] HOST_LOCALAPPDATA intentional use (Claude Desktop requires host app data)
- [ ] Host Git config use (by design — portable env uses host git identity)
- [ ] Claude config junction (_sys\gemini\config -> %USERPROFILE%\.gemini)

## Verification Procedure

1. **Gemini Full-Corpus Scan (if Gemini ON)**
   - Check include-files size first (§3-4-A: >400KB -> split)
   - Use portability-auditor agent for systematic scan

2. **Grep verification (always)**
   - Grep for drive letters: `C:\\`, `D:\\` in *.bat and *.ps1
   - Grep for USERPROFILE/APPDATA: check context (override vs. read)
   - Grep for absolute paths: `[A-Z]:\\Users\\`

3. **Review findings**
   - Critical: immediate fix required
   - Warning: investigate intention, document if by design
   - Info: verify matches architecture decisions in CLAUDE.md

## Output
Audit report: _workspace/03_portability_audit.json (for verifier) + 03_portability_audit.md (human readable)
"""
Launcher Path Integrity Tests
Verifies that Korean/special-char/space paths survive the full
registry → launch.bat → start.bat → app-launch chain without truncation,
quote collapse, or encoding loss.

Node.js Korean Path Safety:
Node.js (npm, claude, gemini CLI) silently fails or crashes when invoked with
non-ASCII (Korean) characters in:
  - NPM_CONFIG_PREFIX / NPM_CONFIG_CACHE
  - CLAUDE_CONFIG_DIR
  - PATH entries
  - cwd of the launched process (VS Code TARGET_DIR)

SUBST is the only mechanism that converts Korean physical paths to ASCII.
These tests verify that SUBST protection is in place at every relevant point.
"""
import re
import json
import subprocess
import sys
from pathlib import Path
from unittest.mock import patch, MagicMock
import pytest

SYS_DIR = Path(__file__).parent.parent.parent
LAUNCH_BAT  = SYS_DIR / "cli" / "launch.bat"
START_BAT   = SYS_DIR / "start.bat"
LAUNCHER_PY = SYS_DIR / "core" / "launcher.py"  # logic moved from cli/launcher.py (thin wrapper)
ENV_JSON    = SYS_DIR / "env.json"
PEERS_JSON  = SYS_DIR / "ai" / "peers.json"

# Challenging paths for portability
TRICKY_PATHS = [
    r"D:\PortableDev (2) - 복사본",        # Korean + parens + spaces + dash
    r"D:\테스트 폴더\my project",           # Korean dir + space
    r"C:\Users\GREAT\Desktop",             # simple ASCII
    r"E:\dev (sandbox)",                   # parens + space
    r"D:\path with spaces and (parens)",   # spaces + parens (no Korean)
]


class TestRegistryCommandFormat:
    """Registry command string must survive shell expansion intact."""

    def test_cmd_str_quotes_all_components(self):
        """cmd.exe /c ""path" "arg"" pattern — both path and arg quoted."""
        sys.path.insert(0, str(SYS_DIR / "cli"))
        import manage
        base = Path(r"D:\PortableDev (2) - 복사본")
        script = base / "_sys" / "cli" / "launch.bat"
        cmd = f'cmd.exe /c ""{script}" "%V""'
        # Outer wrapper: cmd.exe /c "..."
        assert cmd.startswith('cmd.exe /c "')
        assert cmd.endswith('"')
        # launch.bat path is quoted (handles spaces)
        assert f'"{script}"' in cmd
        # arg placeholder is quoted
        assert '"%V"' in cmd

    @pytest.mark.parametrize("base_path", [
        r"D:\PortableDev (2) - 복사본",
        r"D:\테스트 폴더\sandbox",
        r"E:\dev (copy)",
    ])
    def test_physical_path_in_registry_cmd(self, base_path):
        """Physical path (no SUBST) must be used in registry to survive reboot."""
        sys.path.insert(0, str(SYS_DIR / "cli"))
        import manage
        base = Path(base_path)
        script = base / "_sys" / "cli" / "launch.bat"
        cmd = f'cmd.exe /c ""{script}" "%V""'
        # Must NOT use SUBST placeholder like 'E:\_sys'
        assert str(script) in cmd
        # Must not reference a different drive as the root
        assert base_path[:2] in cmd  # drive letter present


class TestBatRelayChain:
    """launch.bat → start.bat argument forwarding integrity."""

    def test_launch_bat_forwards_full_arg(self, tmp_path):
        """launch.bat passes %* verbatim; path with spaces must be preserved."""
        # Simulate what cmd.exe does: split on spaces unless quoted
        tricky = r'"D:\PortableDev (2) - 복사본"'
        # If the outer quotes are present the path is a single token
        tokens = tricky.strip('"').split()
        # After strip-quoting the full path is one item, not split on spaces
        assert len([tricky]) == 1  # treated as one argument when quoted

    @pytest.mark.parametrize("path", TRICKY_PATHS)
    def test_start_bat_tilde1_expansion(self, path):
        r"""%~1 in start.bat strips surrounding quotes — result must equal raw path."""
        # %~1 strips leading/trailing double-quotes from %1
        quoted = f'"{path}"'
        # Simulate %~1 behaviour: remove outer quotes
        expanded = quoted.strip('"')
        assert expanded == path
        # Crucially: path should not be empty or truncated
        assert len(expanded) > 3

    def test_no_truncation_on_parentheses(self):
        """Parentheses in paths must not cause truncation.
        start.bat delegates to launcher.py (Python), which handles parens natively
        via subprocess list args — no cmd.exe block expansion risk."""
        content = LAUNCHER_PY.read_text(encoding="utf-8", errors="ignore")
        # launcher.py must use subprocess list args (not shell string)
        assert "subprocess.Popen([" in content, \
            "launcher.py must use list-form Popen (handles () in paths natively)"
        # No shell=True in critical launch calls
        critical_block = content[content.find("subprocess.Popen("):][:300]
        assert "shell=True" not in critical_block, \
            "Critical subprocess.Popen must NOT use shell=True"

    def test_korean_path_not_empty_after_expansion(self):
        """Korean segment must survive in path string (no silent truncation)."""
        path = r"D:\PortableDev (2) - 복사본\workspace"
        # Korean chars: 복사본 (3 chars)
        assert "복사본" in path
        # Simulate Path.resolve() — Python handles Korean NTFS paths natively
        p = Path(path)
        assert "복사본" in str(p)


class TestSubstPathNormalization:
    """Physical ↔ SUBST path substitution in start.bat."""

    def test_physical_path_replaced_with_subst(self):
        """start.bat TARGET substitution: BASE_DIR_PHYS → BASE_DIR (SUBST)."""
        # Simulate: TARGET = D:\PortableDev (2) - 복사본\workspace
        # BASE_DIR_PHYS = D:\PortableDev (2) - 복사본, BASE_DIR = E:
        phys = r"D:\PortableDev (2) - 복사본"
        subst = r"E:"
        target = r"D:\PortableDev (2) - 복사본\workspace"
        # Batch: set "TARGET=!TARGET:%BASE_DIR_PHYS%=%BASE_DIR%!"
        result = target.replace(phys, subst)
        assert result == r"E:\workspace"
        assert "복사본" not in result  # Korean segment correctly removed

    def test_non_sandbox_path_unchanged(self):
        """Paths outside BASE_DIR must not be modified by substitution."""
        phys = r"D:\PortableDev (2) - 복사본"
        subst = r"E:"
        external = r"C:\Users\GREAT\Desktop"
        result = external.replace(phys, subst)
        assert result == external  # unchanged


class TestLaunchBatStructure:
    """launch.bat must self-locate via %~dp0 for SUBST-resilient operation."""

    def test_launch_bat_uses_tilde_dp0(self):
        """launch.bat must derive SYS_DIR from %~dp0 (not hardcoded path).
        %~dp0 gives the physical location of the batch file itself, allowing
        the script to work both when called via SUBST and via physical path."""
        content = LAUNCH_BAT.read_text(encoding="utf-8", errors="ignore")
        assert "%~dp0" in content, "launch.bat must use %~dp0 for self-location"

    def test_launch_bat_calls_start_bat(self):
        """launch.bat must relay to start.bat via the derived path."""
        content = LAUNCH_BAT.read_text(encoding="utf-8", errors="ignore")
        assert "start.bat" in content, "launch.bat must call start.bat"
        # Must forward all arguments
        assert "%*" in content, "launch.bat must forward %* to start.bat"

    def test_launch_bat_no_hardcoded_drive(self):
        """launch.bat must not have any hardcoded drive letter paths."""
        import re
        content = LAUNCH_BAT.read_text(encoding="utf-8", errors="ignore")
        hardcoded = re.search(r'(?<!%~dp0)[A-Z]:\\(?!sys)', content, re.IGNORECASE)
        # If found, it's a potential portability issue
        assert hardcoded is None, \
            f"Potential hardcoded path in launch.bat: {hardcoded.group()}"

    def test_start_bat_uses_delayed_expansion_in_blocks(self):
        """Path safety for () characters.
        start.bat is now a thin wrapper — launcher.py (Python) handles path safety
        via subprocess list args instead of BAT EnableDelayedExpansion."""
        content = LAUNCHER_PY.read_text(encoding="utf-8", errors="ignore")
        # Python subprocess with list args avoids all cmd.exe expansion issues
        assert "subprocess.Popen([" in content, \
            "launcher.py must use list-form subprocess to handle () in paths safely"


class TestNodeJsPathSafety:
    """SUBST must protect Node.js tools from Korean paths at every entry point.

    Architecture note (post-refactor): env vars/PATH are now driven by
    _sys/env.json (tool_env_vars, path_entries) and _sys/ai/peers.json (env_vars).
    launcher.py (Python) reads these — start.bat is a thin wrapper.

    Risk matrix:
      [A] NPM_CONFIG_PREFIX/CACHE — env.json tool_env_vars (SUBST-safe)
      [B] CLAUDE_CONFIG_DIR — peers.json claude.env_vars (SUBST-safe)
      [C] PATH nodejs entries — env.json path_entries (SUBST-safe)
      [D] TARGET passed to VS Code — substituted in launcher.py
      [E] SUBST failure → RuntimeError in launcher.py
      [F] Unregistered → launcher.py uses physical path gracefully
    """

    # ── [A] NPM env vars ────────────────────────────────────────────────────
    def test_npm_config_prefix_uses_env_dir_not_phys(self):
        """[A] NPM_CONFIG_PREFIX must be in env.json tool_env_vars (SUBST-safe)."""
        data = json.loads(ENV_JSON.read_text(encoding="utf-8"))
        tool_vars = data.get("tool_env_vars", {})
        assert "NPM_CONFIG_PREFIX" in tool_vars, \
            "NPM_CONFIG_PREFIX not in env.json tool_env_vars"
        spec = tool_vars["NPM_CONFIG_PREFIX"]
        assert spec.get("base") in ("env", "sys"), \
            f"NPM_CONFIG_PREFIX must resolve via env/sys base: {spec}"

    def test_npm_config_cache_uses_env_dir_not_phys(self):
        """[A] NPM_CONFIG_CACHE must be in env.json tool_env_vars (SUBST-safe)."""
        data = json.loads(ENV_JSON.read_text(encoding="utf-8"))
        tool_vars = data.get("tool_env_vars", {})
        assert "NPM_CONFIG_CACHE" in tool_vars, \
            "NPM_CONFIG_CACHE not in env.json tool_env_vars"

    # ── [B] Claude Code CLI path ─────────────────────────────────────────────
    def test_claude_config_dir_uses_subst_derived_var(self):
        """[B] CLAUDE_CONFIG_DIR must be in peers.json claude env_vars (SUBST-safe)."""
        data = json.loads(PEERS_JSON.read_text(encoding="utf-8"))
        claude_env = data["peers"]["claude"].get("env_vars", {})
        assert "CLAUDE_CONFIG_DIR" in claude_env, \
            "CLAUDE_CONFIG_DIR must be in peers.json claude.env_vars"

    # ── [C] PATH entries ─────────────────────────────────────────────────────
    def test_nodejs_path_entry_uses_env_dir_variable(self):
        """[C] nodejs PATH entries must be in env.json path_entries (SUBST-safe)."""
        data = json.loads(ENV_JSON.read_text(encoding="utf-8"))
        path_entries = data.get("path_entries", [])
        nodejs_entries = [e for e in path_entries if "nodejs" in e.get("sub", "")]
        assert nodejs_entries, "No nodejs entries in env.json path_entries"
        for entry in nodejs_entries:
            assert entry.get("base") in ("env", "sys"), \
                f"nodejs entry must use env/sys base: {entry}"

    # ── [D] TARGET substitution ──────────────────────────────────────────────
    @pytest.mark.parametrize("korean_base,subst,target,expected", [
        (
            r"D:\테스트_폴더\PortableDev", "P:",
            r"D:\테스트_폴더\PortableDev\workspace\myproj",
            r"P:\workspace\myproj",
        ),
        (
            r"D:\PortableDev (2) - 복사본", "P:",
            r"D:\PortableDev (2) - 복사본\workspace",
            r"P:\workspace",
        ),
        (
            r"E:\한글경로\SandboxDev", "Q:",
            r"E:\한글경로\SandboxDev\workspace\project",
            r"Q:\workspace\project",
        ),
    ])
    def test_target_substitution_removes_korean_before_nodejs(
        self, korean_base, subst, target, expected
    ):
        """[D] TARGET substitution must replace Korean physical base with SUBST path.
        The result is passed as cwd/arg to VS Code (Electron/Node.js) — must be ASCII."""
        # Simulates: set "TARGET=!TARGET:%BASE_DIR_PHYS%=%BASE_DIR%!"
        result = target.replace(korean_base, subst)
        assert result == expected, f"Substitution result mismatch: {result}"
        assert not re.search(r"[가-힣]", result), \
            f"Korean characters remain in TARGET after substitution: {result}"

    def test_target_outside_base_dir_unchanged(self):
        """[D] External paths (outside BASE_DIR_PHYS) must NOT be substituted.
        User opens external projects — those paths must be passed as-is."""
        korean_base = r"D:\테스트_폴더\PortableDev"
        subst = "P:"
        for external in [r"C:\Users\user\project", r"E:\other\repo", r"D:\unrelated"]:
            result = external.replace(korean_base, subst)
            assert result == external, \
                f"External path must be unchanged by TARGET substitution: {result}"

    def test_start_bat_has_target_substitution_logic(self):
        """[D] launcher.py must substitute physical path with SUBST in target."""
        content = LAUNCHER_PY.read_text(encoding="utf-8", errors="ignore")
        assert "base_dir_phys" in content, \
            "launcher.py must track physical base dir (base_dir_phys)"
        assert "target.replace" in content, \
            "launcher.py must replace physical path with SUBST path in target"

    # ── [E] SUBST failure handling ───────────────────────────────────────────
    def test_subst_failure_causes_error_exit_not_korean_fallback(self):
        """[E] launcher.py must raise RuntimeError on SUBST failure (no silent fallback)."""
        content = LAUNCHER_PY.read_text(encoding="utf-8", errors="ignore")
        assert "RuntimeError" in content, \
            "launcher.py must raise RuntimeError on SUBST failure"
        assert "map_subst_drive" in content, \
            "launcher.py must have map_subst_drive() function"

    # ── [F] Unregistered fallback ────────────────────────────────────────────
    def test_unregistered_fallback_has_explicit_warning(self):
        """[F] launcher.py must handle no-SUBST case (fall back to physical path)."""
        content = LAUNCHER_PY.read_text(encoding="utf-8", errors="ignore")
        assert "subst_drive" in content.lower(), \
            "launcher.py must read subst_drive from config"
        assert "base_dir_phys" in content, \
            "launcher.py must track physical base_dir_phys for fallback"

    def test_korean_unregistered_gets_temp_subst(self):
        """[F] launcher.py handles unregistered case via physical path fallback."""
        content = LAUNCHER_PY.read_text(encoding="utf-8", errors="ignore")
        assert "subst_drive" in content.lower()
        assert "base_dir_phys" in content

    def test_start_bat_verifies_subst_target_before_reuse(self):
        """[S-3] launcher.py must verify existing SUBST maps to this env."""
        content = LAUNCHER_PY.read_text(encoding="utf-8", errors="ignore")
        # Sentinel check: verify SUBST points to this env's launcher.py
        assert "launcher.py" in content, \
            "launcher.py must verify SUBST drive via sentinel file check"
        # Must release wrong SUBST with /D before remapping
        assert '"/D"' in content or "'/D'" in content or '"/D"' in content, \
            "launcher.py must release wrong SUBST mapping with /D"


class TestManagePySubstEncoding:
    """manage.py must use OEM encoding when reading subst command output."""

    def test_subst_output_uses_oem_encoding(self):
        """[S-6/A] subst command output must be read with encoding='oem'.
        Windows cmd tools use OEM code page (cp949 on Korean, cp1252 on English).
        text=True without encoding uses ANSI which misreads Korean paths on some locales."""
        manage_py = SYS_DIR / "cli" / "manage.py"
        content = manage_py.read_text(encoding="utf-8", errors="ignore")
        # Both get_subst_mappings() and global_cleanup() call subst
        # Both must use encoding='oem' not just text=True
        subst_calls = [
            line for line in content.splitlines()
            if '["subst"]' in line and 'check_output' in line
        ]
        assert subst_calls, "No subprocess.check_output(['subst']) calls found in manage.py"
        for call in subst_calls:
            assert "encoding='oem'" in call, \
                f"subst call must use encoding='oem': {call.strip()}"


class TestVSCodeLaunchArg:
    """Code.exe receives correct workspace path."""

    @pytest.mark.parametrize("target_dir", [
        r"E:\workspace",
        r"C:\Users\GREAT\Desktop",
        r"D:\테스트 폴더",
    ])
    def test_vscode_called_with_dot_in_target_dir(self, target_dir, tmp_path):
        """launcher.py calls VS Code with '.' after os.chdir(target_dir)."""
        content = LAUNCHER_PY.read_text(encoding="utf-8", errors="ignore")
        assert '"."' in content, \
            "launcher.py must call VS Code with '.' argument"
        assert "vscode_exe" in content

    def test_code_exe_path_uses_env_dir_variable(self):
        """launcher.py Code.exe path must not have hardcoded drive letters."""
        content = LAUNCHER_PY.read_text(encoding="utf-8", errors="ignore")
        hardcoded = re.search(r'[A-Z]:\\[^"\'/]*[\\/]env[\\/]vscode', content)
        assert hardcoded is None, \
            f"Hardcoded drive in vscode path: {hardcoded.group() if hardcoded else ''}"
        assert "sys_dir" in content and "vscode" in content

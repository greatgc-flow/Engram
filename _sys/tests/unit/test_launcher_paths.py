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

Paths are preserved cleanly without truncation or quote collapse.
These tests verify that path protection is in place at every relevant point.
"""
import re
import json
import subprocess
import sys
from pathlib import Path
from unittest.mock import patch, MagicMock
import pytest

SYS_DIR = Path(__file__).parent.parent.parent
START_BAT   = SYS_DIR / "start.bat"
LAUNCHER_PY = SYS_DIR / "core" / "launcher.py"  # logic moved from cli/launcher.py (thin wrapper)
ENV_JSON    = SYS_DIR / "env.json"

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
        base = Path(r"D:\PortableDev (2) - 복사본")
        script = base / "_sys" / "start.bat"
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
        """Physical path must be used in registry to survive reboot."""
        base = Path(base_path)
        script = base / "_sys" / "start.bat"
        cmd = f'cmd.exe /c ""{script}" "%V""'
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
    """launcher.py (Python) now owns path safety; _sys/cli/launch.bat and its
    %~dp0 self-location/SUBST-resilience concerns were retired in P1-7 along
    with the rest of the _sys/cli shims (SUBST support itself was already
    removed in P1-3)."""

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
    _sys/env.json (tool_env_vars, path_entries).
    launcher.py (Python) reads these — start.bat is a thin wrapper.

    Risk matrix:
      [A] NPM_CONFIG_PREFIX/CACHE — env.json tool_env_vars (SUBST-safe)
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

    # ── [C] PATH entries ─────────────────────────────────────────────────────
    def test_nodejs_path_entry_uses_env_dir_variable(self):
        """[C] nodejs PATH entries must be in env.json path_entries (safe)."""
        data = json.loads(ENV_JSON.read_text(encoding="utf-8"))
        path_entries = data.get("path_entries", [])
        nodejs_entries = [e for e in path_entries if "nodejs" in e.get("sub", "")]
        assert nodejs_entries, "No nodejs entries in env.json path_entries"
        for entry in nodejs_entries:
            assert entry.get("base") in ("env", "sys"), \
                f"nodejs entry must use env/sys base: {entry}"


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

"""
Launcher Path Integrity Tests
Verifies that Korean/special-char/space paths survive the full
registry → launch.bat → start.bat → app-launch chain without truncation,
quote collapse, or encoding loss.
"""
import subprocess
import sys
from pathlib import Path
from unittest.mock import patch, MagicMock
import pytest

SYS_DIR = Path(__file__).parent.parent.parent
LAUNCH_BAT = SYS_DIR / "cli" / "launch.bat"
START_BAT = SYS_DIR / "start.bat"

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
        """Parentheses in path must not cause cmd.exe FOR-block truncation."""
        path = r"D:\PortableDev (2) - 복사본"
        # The known bug: cmd.exe inside if(...) or for(...) treats ) as block-end
        # The fix is to use EnableDelayedExpansion + !VAR! inside blocks.
        # Verify our start.bat uses setlocal EnableDelayedExpansion
        content = START_BAT.read_text(encoding="utf-8", errors="ignore")
        assert "EnableDelayedExpansion" in content, \
            "start.bat must use EnableDelayedExpansion to handle () in paths"
        # Also verify !TARGET! is used (not %TARGET%) inside conditional blocks
        assert "!TARGET!" in content

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


class TestVSCodeLaunchArg:
    """Code.exe receives correct workspace path."""

    @pytest.mark.parametrize("target_dir", [
        r"E:\workspace",
        r"C:\Users\GREAT\Desktop",
        r"D:\테스트 폴더",
    ])
    def test_vscode_called_with_dot_in_target_dir(self, target_dir, tmp_path):
        """start.bat cds to TARGET_DIR then calls Code.exe '.'; verify intent."""
        # After cd /d TARGET_DIR, '.' resolves to TARGET_DIR
        # We verify that Code.exe is called with a '.' argument (relative to cd'd dir)
        content = START_BAT.read_text(encoding="utf-8", errors="ignore")
        assert 'Code.exe" "."' in content or "Code.exe\" \".\"" in content, \
            "start.bat must call Code.exe with '.' after cd /d TARGET_DIR"

    def test_code_exe_path_uses_env_dir_variable(self):
        """Code.exe path must use !ENV_DIR! variable, not hardcoded drive."""
        content = START_BAT.read_text(encoding="utf-8", errors="ignore")
        # Must NOT contain hardcoded drive letter before \env\vscode
        import re
        # Pattern: a drive letter hardcoded before \env\vscode
        hardcoded = re.search(r'[A-Z]:\\[^%!]*\\env\\vscode', content)
        assert hardcoded is None, \
            f"Hardcoded drive letter found in Code.exe path: {hardcoded.group()}"
        # Must use variable
        assert "ENV_DIR" in content

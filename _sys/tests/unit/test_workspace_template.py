"""TDD — I5: workspace_base template completeness.

Tests are written BEFORE template files are created.
All tests MUST FAIL until implementation is complete.
"""
import json
import pytest
from pathlib import Path

TEMPLATE_DIR = Path(__file__).parent.parent.parent / "templates" / "workspace-base"
REQUIRED_FILES = [
    ".gitignore",
    "CLAUDE.md",
    "GEMINI.md",
    "config/settings.json",
]
REQUIRED_DIRS = [
    "specific",
    "config",
]


# ── Structure ────────────────────────────────────────────────────────────────

class TestWorkspaceBaseStructure:
    def test_template_dir_exists(self):
        assert TEMPLATE_DIR.exists(), f"workspace_base/ not found at {TEMPLATE_DIR}"

    def test_required_files_exist(self):
        missing = [f for f in REQUIRED_FILES if not (TEMPLATE_DIR / f).exists()]
        assert not missing, f"Missing template files: {missing}"

    def test_required_dirs_exist(self):
        missing = [d for d in REQUIRED_DIRS if not (TEMPLATE_DIR / d).is_dir()]
        assert not missing, f"Missing template dirs: {missing}"

    def test_readme_exists(self):
        assert (TEMPLATE_DIR / "README.md").exists()


# ── Content ──────────────────────────────────────────────────────────────────

class TestWorkspaceBaseContent:
    def test_gitignore_has_common_ignores(self):
        gitignore = (TEMPLATE_DIR / ".gitignore").read_text(encoding="utf-8")
        for pattern in [".env", "_state", "__pycache__"]:
            assert pattern in gitignore, f".gitignore missing pattern: {pattern}"

    def test_claude_md_has_link_to_docs(self):
        content = (TEMPLATE_DIR / "CLAUDE.md").read_text(encoding="utf-8")
        assert "docs-v2" in content or "manual" in content, \
            "CLAUDE.md should reference docs-v2 or user manual"

    def test_gemini_md_has_link_to_docs(self):
        content = (TEMPLATE_DIR / "GEMINI.md").read_text(encoding="utf-8")
        assert "docs-v2" in content or "manual" in content

    def test_config_settings_is_valid_json(self):
        settings_path = TEMPLATE_DIR / "config" / "settings.json"
        content = settings_path.read_text(encoding="utf-8")
        data = json.loads(content)  # raises if invalid JSON
        assert isinstance(data, dict)

    def test_config_settings_has_project_name_field(self):
        settings_path = TEMPLATE_DIR / "config" / "settings.json"
        data = json.loads(settings_path.read_text(encoding="utf-8"))
        assert "project_name" in data, "settings.json must have project_name field"

    def test_config_settings_has_collab_rate_override(self):
        settings_path = TEMPLATE_DIR / "config" / "settings.json"
        data = json.loads(settings_path.read_text(encoding="utf-8"))
        assert "collab_rate_override" in data, \
            "settings.json must have collab_rate_override field"

    def test_collab_rate_override_default_is_null(self):
        settings_path = TEMPLATE_DIR / "config" / "settings.json"
        data = json.loads(settings_path.read_text(encoding="utf-8"))
        assert data["collab_rate_override"] is None, \
            "collab_rate_override should default to null (use global setting)"


# ── Portability ──────────────────────────────────────────────────────────────

class TestWorkspaceBasePortability:
    def test_no_hardcoded_drive_letters(self):
        """No file in the template should contain hardcoded drive letters."""
        import re
        drive_pattern = re.compile(r'[A-Za-z]:\\\\', re.IGNORECASE)
        violations = []
        for f in TEMPLATE_DIR.rglob("*"):
            if f.is_file() and f.suffix in (".md", ".json", ".txt", ".bat", ".gitignore"):
                content = f.read_text(encoding="utf-8", errors="ignore")
                if drive_pattern.search(content):
                    violations.append(str(f.relative_to(TEMPLATE_DIR)))
        assert not violations, f"Hardcoded drive letters found in: {violations}"

    def test_no_userprofile_in_templates(self):
        """Templates must not reference %USERPROFILE% or hardcoded user paths."""
        violations = []
        for f in TEMPLATE_DIR.rglob("*"):
            if f.is_file() and f.suffix in (".md", ".json", ".bat"):
                content = f.read_text(encoding="utf-8", errors="ignore")
                if "USERPROFILE" in content or "C:\\Users" in content:
                    violations.append(str(f.relative_to(TEMPLATE_DIR)))
        assert not violations, f"User-specific paths found in: {violations}"

"""Tests for pathlayout."""
import sys
from pathlib import Path
import pytest

ROOT = Path(__file__).resolve().parents[3]
CORE = ROOT / "_sys" / "core"
if str(CORE) not in sys.path:
    sys.path.insert(0, str(CORE))

from pathlayout import PathLayout, resolve_path_layout
import hub


def test_resolve_path_layout_no_override(monkeypatch):
    """Test that resolving without override calls hub.find_ai_root()."""
    fake_ai_root = Path("/fake/ai/root")
    called = False

    def mock_find_ai_root():
        nonlocal called
        called = True
        return fake_ai_root

    monkeypatch.setattr(hub, "find_ai_root", mock_find_ai_root)

    layout = resolve_path_layout()
    assert called is True
    assert layout.ai_root == fake_ai_root


def test_resolve_path_layout_with_override(monkeypatch):
    """Test that resolving with override uses it and skips find_ai_root."""
    fake_override = Path("/override/ai/root")
    called = False

    def mock_find_ai_root():
        nonlocal called
        called = True
        return Path("/should/not/be/called")

    monkeypatch.setattr(hub, "find_ai_root", mock_find_ai_root)

    layout = resolve_path_layout(ai_root_override=fake_override)
    assert called is False
    assert layout.ai_root == fake_override.resolve()


def test_resolve_path_layout_relative_to_arbitrary_root(monkeypatch, tmp_path):
    """Test that install_root/sys_root/project_root resolve correctly relative to an arbitrary root."""
    import pathlayout

    # Create mock file layout
    mock_install_root = tmp_path / "fake_install"
    mock_pathlayout_file = mock_install_root / "_sys" / "core" / "pathlayout.py"
    mock_pathlayout_file.parent.mkdir(parents=True, exist_ok=True)
    mock_pathlayout_file.touch()

    monkeypatch.setattr(pathlayout, "__file__", str(mock_pathlayout_file))

    # Test with an override to avoid hub.find_ai_root call
    layout = resolve_path_layout(ai_root_override=mock_install_root / ".ai")

    assert layout.install_root == mock_install_root.resolve()
    assert layout.sys_root == (mock_install_root / "_sys").resolve()
    assert layout.project_root == mock_install_root.resolve()


def test_pathlayout_is_frozen():
    """Test that PathLayout is immutable."""
    layout = PathLayout(
        install_root=Path("a"),
        sys_root=Path("b"),
        project_root=Path("c"),
        ai_root=Path("d")
    )
    with pytest.raises(Exception):
        layout.install_root = Path("e")


def test_resolve_path_layout_value_equality():
    """Test that two separate resolutions with the same input produce equal instances."""
    override = Path("/same/override")
    layout1 = resolve_path_layout(ai_root_override=override)
    layout2 = resolve_path_layout(ai_root_override=override)

    assert layout1 == layout2
    assert layout1 is not layout2

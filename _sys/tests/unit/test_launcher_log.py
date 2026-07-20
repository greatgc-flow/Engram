import pytest
from pathlib import Path
from unittest.mock import patch

import _sys.core.launcher as launcher

def test_launcher_log_append_mode(tmp_path):
    """
    Proves that launcher.py no longer reads the entire log file into memory
    to append a line, avoiding O(N^2) behavior and severe race conditions.
    """
    ctx = {
        "base_dir": tmp_path,
        "sys_dir": tmp_path / "_sys",
        "paths": {"state": tmp_path / "state"},
        "args": []
    }
    
    # Setup necessary mock files
    (tmp_path / "state").mkdir(parents=True, exist_ok=True)
    (tmp_path / "_sys" / "ai").mkdir(parents=True, exist_ok=True)
    (tmp_path / "_sys" / "ai" / "peers.json").write_text("{}", encoding="utf-8")
    
    read_text_calls = []
    original_read_text = Path.read_text
    
    def mock_read_text(self, *args, **kwargs):
        if hasattr(self, "name") and "start_" in self.name and self.name.endswith(".log"):
            read_text_calls.append(self.name)
        return original_read_text(self, *args, **kwargs)
        
    with patch("subprocess.Popen"), \
         patch("subprocess.run"), \
         patch.object(Path, "read_text", autospec=True, side_effect=mock_read_text):
        
        launcher.main(ctx)
        
    # Verify a log file was created and written to
    log_dir = tmp_path / "_archive" / "logs"
    log_files = list(log_dir.glob("start_*.log"))
    assert len(log_files) == 1
    
    content = log_files[0].read_text(encoding="utf-8")
    assert "Started :" in content
    assert "BASE    :" in content
    
    assert len(read_text_calls) == 0, f"read_text was called {len(read_text_calls)} times on log file, expected 0 for append mode"

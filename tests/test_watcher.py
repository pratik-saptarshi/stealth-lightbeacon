import os
import shutil
import time
from pathlib import Path

import pytest
from utils.watcher import WorkspaceWatcher

def test_workspace_watcher_flow():
    test_dir = ".data/test_watcher_root"
    if os.path.exists(test_dir):
        shutil.rmtree(test_dir)
    os.makedirs(test_dir, exist_ok=True)
    
    # Create a dummy python file to watch
    dummy_file = os.path.join(test_dir, "test_file.py")
    with open(dummy_file, "w") as f:
        f.write("# initial content\n")
        
    watcher = WorkspaceWatcher(workspace_root=test_dir, debounce_interval_ms=100)
    
    try:
        watcher.start()
        # Give it a second to spin up and scan
        time.sleep(0.5)
        
        # Modify the dummy file to trigger change detection
        with open(dummy_file, "a") as f:
            f.write("# modified content\n")
            
        # Wait for debounce and trigger
        time.sleep(0.5)
        
        # Verify watcher registered file modifications
        assert len(watcher.file_mtimes) > 0
        
    finally:
        watcher.stop()
        if os.path.exists(test_dir):
            shutil.rmtree(test_dir)


def test_workspace_watcher_scans_and_tracks_changes(tmp_path, monkeypatch):
    root = tmp_path / "watch"
    root.mkdir()
    keep = root / "keep.py"
    keep.write_text("print('ok')\n", encoding="utf-8")
    (root / "skip.txt").write_text("ignore\n", encoding="utf-8")
    hidden = root / ".venv"
    hidden.mkdir()
    (hidden / "hidden.py").write_text("print('hidden')\n", encoding="utf-8")
    broken = root / "broken.md"
    broken.write_text("broken\n", encoding="utf-8")

    watcher = WorkspaceWatcher(workspace_root=str(root), debounce_interval_ms=50)

    def fake_getmtime(path):
        if path.endswith("broken.md"):
            raise OSError("missing")
        return Path(path).stat().st_mtime

    monkeypatch.setattr("os.path.getmtime", fake_getmtime)

    assert watcher._scan_files(first_scan=True) is False
    assert "keep.py" in watcher.file_mtimes
    assert "skip.txt" not in watcher.file_mtimes
    assert ".venv/hidden.py" not in watcher.file_mtimes
    assert "broken.md" not in watcher.file_mtimes

    watcher.file_mtimes["keep.py"] = 0.0
    assert watcher._scan_files(first_scan=False) is True
    assert watcher.changed_files == {"keep.py"}

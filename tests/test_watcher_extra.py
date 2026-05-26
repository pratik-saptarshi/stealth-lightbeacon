from pathlib import Path
from unittest.mock import patch

from utils.watcher import WorkspaceWatcher


def test_workspace_watcher_scan_prunes_and_skips_bad_files(tmp_path, monkeypatch):
    root = tmp_path / "watch"
    root.mkdir()
    (root / "keep.py").write_text("print('ok')\n", encoding="utf-8")
    (root / "skip.txt").write_text("ignore\n", encoding="utf-8")
    hidden = root / ".venv"
    hidden.mkdir()
    (hidden / "hidden.py").write_text("print('hidden')\n", encoding="utf-8")
    broken = root / "broken.md"
    broken.write_text("broken\n", encoding="utf-8")

    watcher = WorkspaceWatcher(str(root), debounce_interval_ms=50)

    def fake_getmtime(path):
        if path.endswith("broken.md"):
            raise OSError("missing")
        return Path(path).stat().st_mtime

    monkeypatch.setattr("os.path.getmtime", fake_getmtime)

    changed = watcher._scan_files(first_scan=True)

    assert changed is False
    assert "keep.py" in watcher.file_mtimes
    assert "skip.txt" not in watcher.file_mtimes
    assert ".venv/hidden.py" not in watcher.file_mtimes
    assert "broken.md" not in watcher.file_mtimes


def test_workspace_watcher_trigger_sync_noop_then_prints(tmp_path):
    watcher = WorkspaceWatcher(str(tmp_path), debounce_interval_ms=50)

    watcher.trigger_sync()
    watcher.changed_files.update({"a.py", "b.md"})

    with patch("builtins.print") as mock_print:
        watcher.trigger_sync()

    assert watcher.changed_files == set()
    mock_print.assert_any_call("\n=== Debounce Trigger: Syncing 2 files ===")


def test_workspace_watcher_detects_modified_file(tmp_path, monkeypatch):
    root = tmp_path / "watch-change"
    root.mkdir()
    target = root / "changed.py"
    target.write_text("print('old')\n", encoding="utf-8")

    watcher = WorkspaceWatcher(str(root), debounce_interval_ms=50)
    watcher.file_mtimes["changed.py"] = 1.0

    def fake_getmtime(path):
        return 2.0 if path.endswith("changed.py") else Path(path).stat().st_mtime

    monkeypatch.setattr("os.path.getmtime", fake_getmtime)

    changed = watcher._scan_files(first_scan=False)

    assert changed is True
    assert watcher.file_mtimes["changed.py"] == 2.0
    assert watcher.changed_files == {"changed.py"}

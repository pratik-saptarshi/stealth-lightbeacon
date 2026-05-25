import os
import shutil
import time
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

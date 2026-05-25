import os
import time
import threading

class WorkspaceWatcher:
    """Robust background directory watcher with debounced change notification and graceful shutdown."""
    def __init__(self, workspace_root, debounce_interval_ms=2000):
        self.workspace_root = os.path.abspath(workspace_root)
        self.debounce_interval_s = debounce_interval_ms / 1000.0
        self.shutdown_event = threading.Event()
        self.changed_files = set()
        self.watch_thread = None
        self.file_mtimes = {}

    def start(self):
        print(f"Starting WorkspaceWatcher on {self.workspace_root}...")
        self.watch_thread = threading.Thread(target=self._watch_loop, daemon=True)
        self.watch_thread.start()

    def stop(self):
        print("Stopping WorkspaceWatcher...")
        self.shutdown_event.set()
        if self.watch_thread:
            self.watch_thread.join(timeout=3.0)

    def _watch_loop(self):
        # Initial scan to populate baseline file modification times
        self._scan_files(first_scan=True)
        
        while not self.shutdown_event.is_set():
            # Check every second for modifications
            self.shutdown_event.wait(1.0)
            if self.shutdown_event.is_set():
                break
                
            if self._scan_files(first_scan=False):
                # Debounce: wait for additional concurrent writes to finish
                self.shutdown_event.wait(self.debounce_interval_s)
                if not self.shutdown_event.is_set():
                    self.trigger_sync()

    def _scan_files(self, first_scan=False) -> bool:
        changed = False
        for root, dirs, files in os.walk(self.workspace_root):
            # Prune directory search tree to skip large/generated directories
            dirs[:] = [d for d in dirs if not d.startswith('.') and d not in ('__pycache__', 'node_modules', '.venv', 'reports', 'report', '.data')]
            
            for file in files:
                if not (file.endswith('.py') or file.endswith('.toml') or file.endswith('.md')):
                    continue
                path = os.path.join(root, file)
                try:
                    mtime = os.path.getmtime(path)
                except OSError:
                    continue
                
                rel_path = os.path.relpath(path, self.workspace_root)
                if first_scan:
                    self.file_mtimes[rel_path] = mtime
                else:
                    last_mtime = self.file_mtimes.get(rel_path)
                    if last_mtime is None or mtime > last_mtime:
                        self.file_mtimes[rel_path] = mtime
                        self.changed_files.add(rel_path)
                        changed = True
        return changed

    def trigger_sync(self):
        files_to_sync = list(self.changed_files)
        self.changed_files.clear()
        if not files_to_sync:
            return
            
        print(f"\n=== Debounce Trigger: Syncing {len(files_to_sync)} files ===")
        for file in files_to_sync:
            print(f"Syncing delta: {file}")

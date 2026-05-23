"""
cache.py — SQLite-backed asynchronous local caching layer.
Uses standard library sqlite3 executed via run_in_executor to avoid blocking the event loop,
providing high safety and zero third-party dependencies.
"""

import os
import sqlite3
import time
import json
import asyncio
from typing import Optional, Dict, Any

class AsyncCache:
    """
    Asynchronous key-value cache backed by SQLite.
    """
    def __init__(self, db_path: str = "reports/cache.db"):
        self.db_path = db_path
        # Ensure target directory exists
        db_dir = os.path.dirname(self.db_path)
        if db_dir:
            os.makedirs(db_dir, exist_ok=True)
        self._init_db()

    def _init_db(self):
        """
        Creates the database tables if they do not exist yet.
        """
        conn = sqlite3.connect(self.db_path)
        try:
            with conn:
                conn.execute("PRAGMA journal_mode=WAL")
                conn.execute("PRAGMA synchronous=NORMAL")
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS pagespeed_cache (
                        url TEXT PRIMARY KEY,
                        timestamp REAL,
                        response_json TEXT
                    )
                """)
        except Exception:
            pass
        finally:
            conn.close()

    async def get(self, url: str, ttl: int = 86400) -> Optional[Dict[str, Any]]:
        """
        Retrieves a cached value if it exists and is within the TTL boundary.
        """
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, self._sync_get, url, ttl)

    def _sync_get(self, url: str, ttl: int) -> Optional[Dict[str, Any]]:
        conn = sqlite3.connect(self.db_path)
        try:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT timestamp, response_json FROM pagespeed_cache WHERE url = ?",
                (url,)
            )
            row = cursor.fetchone()
            if not row:
                return None
            
            timestamp, response_json = row
            # Validate expiration against TTL
            if time.time() - timestamp < ttl:
                return json.loads(response_json)
        except Exception:
            pass
        finally:
            conn.close()
        return None

    async def set(self, url: str, response_data: Dict[str, Any]) -> None:
        """
        Asynchronously stores a key-value payload in the cache.
        """
        loop = asyncio.get_running_loop()
        await loop.run_in_executor(None, self._sync_set, url, response_data)

    def _sync_set(self, url: str, response_data: Dict[str, Any]) -> None:
        conn = sqlite3.connect(self.db_path)
        try:
            response_json = json.dumps(response_data)
            timestamp = time.time()
            with conn:
                conn.execute(
                    "INSERT OR REPLACE INTO pagespeed_cache (url, timestamp, response_json) VALUES (?, ?, ?)",
                    (url, timestamp, response_json)
                )
        except Exception:
            pass
        finally:
            conn.close()

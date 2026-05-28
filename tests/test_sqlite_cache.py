"""
test_sqlite_cache.py — Unit tests for the SQLite-backed async cache.
"""

import pytest
import os
import asyncio
import time
from unittest.mock import patch
from modules.cache import AsyncCache

@pytest.fixture
def temp_db_path(tmp_path) -> str:
    """
    Returns a temporary database path for testing.
    """
    return str(tmp_path / "test_cache.db")

@pytest.mark.asyncio
async def test_cache_set_and_get(temp_db_path):
    """
    Verifies that writing to the cache and reading from it works successfully.
    """
    cache = AsyncCache(temp_db_path)
    url = "https://example.com/pagespeed-test"
    response_data = {"score": 90, "metrics": {"LCP": 1200}}
    
    # Assert initially empty
    cached_data = await cache.get(url)
    assert cached_data is None
    
    # Save to cache
    await cache.set(url, response_data)
    
    # Read back and verify
    cached_data = await cache.get(url)
    assert cached_data is not None
    assert cached_data["score"] == 90
    assert cached_data["metrics"]["LCP"] == 1200

@pytest.mark.asyncio
async def test_cache_ttl_expiration(temp_db_path):
    """
    Verifies that cache entries expire correctly after the TTL duration.
    """
    cache = AsyncCache(temp_db_path)
    url = "https://example.com/stale-cache"
    response_data = {"score": 45}
    
    await cache.set(url, response_data)
    
    # Get with standard TTL (should succeed)
    cached_ok = await cache.get(url, ttl=100)
    assert cached_ok is not None
    
    # Get with 0 or negative TTL (should expire)
    cached_expired = await cache.get(url, ttl=-1)
    assert cached_expired is None

@pytest.mark.asyncio
async def test_cache_overwrite(temp_db_path):
    """
    Verifies that setting a URL again updates and overwrites the existing entry.
    """
    cache = AsyncCache(temp_db_path)
    url = "https://example.com/overwrite-test"
    
    await cache.set(url, {"score": 50})
    await cache.set(url, {"score": 99})
    
    cached_data = await cache.get(url)
    assert cached_data is not None
    assert cached_data["score"] == 99


@pytest.mark.asyncio
async def test_cache_handles_sqlite_errors(temp_db_path):
    class BrokenCursor:
        def execute(self, *args, **kwargs):
            raise RuntimeError("boom")

        def fetchone(self):
            return None

    class BrokenConnection:
        def cursor(self):
            return BrokenCursor()

        def execute(self, *args, **kwargs):
            raise RuntimeError("boom")

        def close(self):
            pass

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

    with patch("modules.cache.sqlite3.connect", return_value=BrokenConnection()):
        cache = AsyncCache(temp_db_path)

        assert await cache.get("https://example.com/missing", ttl=1) is None
        await cache.set("https://example.com/missing", {"score": 1})

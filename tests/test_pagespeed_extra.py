from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from modules.pagespeed import PagespeedEvaluator


class _FakeResponse:
    def __init__(self, status_code, payload=None):
        self.status_code = status_code
        self._payload = payload or {}

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(f"status={self.status_code}")

    def json(self):
        return self._payload


@pytest.mark.asyncio
async def test_pagespeed_backoff_retries_on_rate_limit(tmp_path, monkeypatch):
    evaluator = PagespeedEvaluator(cache_dir=str(tmp_path))
    responses = [
        _FakeResponse(429),
        _FakeResponse(
            200,
            {
                "lighthouseResult": {"categories": {"performance": {"score": 0.91}}},
                "loadingExperience": {
                    "metrics": {
                        "LARGEST_CONTENTFUL_PAINT_MS": {"percentile": 1200},
                        "CUMULATIVE_LAYOUT_SHIFT_SCORE": {"percentile": 2},
                        "INTERACTION_TO_NEXT_PAINT": {"percentile": 80},
                        "EXPERIMENTAL_TIME_TO_FIRST_BYTE": {"percentile": 200},
                    }
                },
            },
        ),
    ]
    client = MagicMock()
    client.get = AsyncMock(side_effect=responses)
    sleep = AsyncMock()
    monkeypatch.setattr("modules.pagespeed.asyncio.sleep", sleep)

    result = await evaluator._fetch_psi_with_backoff("https://example.com", client)

    assert result["lighthouseResult"]["categories"]["performance"]["score"] == 0.91
    assert client.get.await_count == 2
    assert sleep.await_count == 1


@pytest.mark.asyncio
async def test_pagespeed_evaluate_returns_fallback_on_api_failure(tmp_path, monkeypatch):
    evaluator = PagespeedEvaluator(cache_dir=str(tmp_path))
    monkeypatch.setattr(evaluator, "_read_from_cache", AsyncMock(return_value=None))
    monkeypatch.setattr(evaluator, "_fetch_psi_with_backoff", AsyncMock(side_effect=RuntimeError("offline")))

    result = await evaluator.evaluate("", "https://example.com/offline")

    assert result.domain == "PageSpeed & Performance"
    assert result.issues[0].id == "R-PERF-API-FAIL"
    assert result.metadata["api_status"] == "failed"


@pytest.mark.asyncio
async def test_pagespeed_cache_helpers_tolerate_backend_errors(tmp_path, monkeypatch):
    evaluator = PagespeedEvaluator(cache_dir=str(tmp_path))
    monkeypatch.setattr(evaluator.cache, "get", AsyncMock(side_effect=RuntimeError("cache read")))
    monkeypatch.setattr(evaluator.cache, "_sync_set", MagicMock(side_effect=RuntimeError("cache write")))

    assert await evaluator._read_from_cache("https://example.com") is None
    evaluator._write_to_cache("https://example.com", {"ok": True})

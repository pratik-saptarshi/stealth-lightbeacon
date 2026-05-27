from __future__ import annotations

from unittest.mock import AsyncMock, Mock, patch

import pytest

from modules.base import EvaluationResult, Issue
from modules.html_parser import HtmlParser
from utils.browser_pool import BrowserPool
from utils.budget_validator import BudgetValidator
from utils.crawl_diff import compare_audit_reports, compare_audit_runs
from utils.recon import ReconAdvisor
from utils.selector_resolver import SelectorResolver


@pytest.mark.asyncio
async def test_recon_status_code_falls_back_to_browser(monkeypatch):
    client = Mock()
    response = Mock()
    response.status_code = 429
    response.headers = {"Server": "nginx"}
    response.text = "<html><body>rate limit</body></html>"
    client.get = AsyncMock(return_value=response)
    client.aclose = AsyncMock(return_value=None)

    with patch("httpx.AsyncClient", return_value=client):
        recommendation = await ReconAdvisor().inspect("https://example.com")

    assert recommendation.recommended_engine == "stealth"
    assert recommendation.posture == "browser"
    assert "status:429" in recommendation.evidence
    client.aclose.assert_awaited_once()


def test_budget_validator_returns_empty_without_pagespeed_result():
    validator = BudgetValidator({"performance_score": 8.0})
    assert validator.validate([]) == []


def test_selector_resolver_returns_unrepaired_selector_below_threshold():
    parser = HtmlParser("<main><h1 class='headline'>Title</h1></main>")
    resolver = SelectorResolver(min_confidence=0.95)

    resolved = resolver.resolve(parser, "h1#missing", text_hint="mismatch")

    assert resolved.repaired is False
    assert resolved.confidence < 0.95
    assert resolved.selector == "h1"


def test_crawl_diff_reports_regressions_and_resolved_issues():
    previous = {
        "target_url": "https://example.com",
        "average_score": 8.0,
        "domains": [
            {
                "domain": "SEO",
                "score": 8.5,
                "issues": [{"id": "SEO-1"}],
            },
            {
                "domain": "Performance",
                "score": 7.5,
                "issues": [{"id": "PERF-1"}],
            },
        ],
    }
    current = {
        "target_url": "https://example.com",
        "average_score": 7.0,
        "domains": [
            {
                "name": "SEO",
                "score": 8.0,
                "issues": [{"id": "SEO-2"}],
            },
            {
                "name": "Accessibility",
                "score": 7.5,
                "issues": [],
            },
        ],
    }

    diff = compare_audit_reports(previous, current)

    assert diff["added_domains"] == ["Accessibility"]
    assert diff["removed_domains"] == ["Performance"]
    assert diff["regressions"] == ["Performance", "SEO"]
    assert diff["improvements"] == ["Accessibility"]
    assert diff["new_issue_ids"] == ["SEO-2"]
    assert diff["resolved_issue_ids"] == ["PERF-1", "SEO-1"]


@pytest.mark.asyncio
async def test_compare_audit_runs_prefers_store_report_method():
    class _Store:
        async def get_run_report(self, run_id):
            return {"target_url": run_id, "domains": []}

    diff = await compare_audit_runs(_Store(), "previous", "current")

    assert diff["score_delta"] == 0.0


@pytest.mark.asyncio
async def test_browser_pool_close_swallows_teardown_errors(monkeypatch):
    BrowserPool._instance = None
    pool = BrowserPool()

    class _Failing:
        async def close(self):
            raise RuntimeError("close failed")

        async def stop(self):
            raise RuntimeError("stop failed")

    pool.browser = _Failing()
    pool.playwright = _Failing()
    pool.proxy = _Failing()

    await pool.close()

    assert pool.browser is None
    assert pool.playwright is None
    assert pool.proxy is None

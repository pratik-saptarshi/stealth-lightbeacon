"""
test_drupal.py — Unit tests for the DrupalEvaluator module.
"""

import pytest
import httpx
from unittest.mock import AsyncMock, patch
from modules.drupal import DrupalEvaluator
from modules.base import EvaluationResult

@pytest.fixture
def mock_html_drupal() -> str:
    """
    Returns a mock HTML page revealing standard Drupal system indicators.
    """
    return """<!DOCTYPE html>
<html>
<head>
  <meta name="generator" content="Drupal 10 (https://www.drupal.org)">
  <link rel="stylesheet" href="/sites/default/files/css/aggregate.css">
  <script src="/core/assets/vendor/jquery/jquery.min.js"></script>
</head>
<body>
  <h1>A Drupal Powered Website</h1>
</body>
</html>
"""

@pytest.mark.asyncio
async def test_drupal_evaluator_fingerprints(mock_html_drupal: str):
    """
    Verifies that Drupal generators and core file paths are correctly identified.
    """
    evaluator = DrupalEvaluator()
    with patch.object(DrupalEvaluator, "_fetch_headers", AsyncMock(return_value=None)):
        result = await evaluator.evaluate(
            mock_html_drupal,
            "https://example.com",
            check_api=False,
        )
    
    assert isinstance(result, EvaluationResult)
    assert result.domain == "Drupal & Security Headers"
    
    # Fingerprints should yield INFO notices, score remains relatively stable
    assert result.score >= 8.5
    
    issue_ids = [issue.id for issue in result.issues]
    assert "R-DRUP-FINGERPRINT" in issue_ids
    assert "R-DRUP-CORE-PATHS" in issue_ids


@pytest.mark.asyncio
async def test_drupal_security_header_gaps_and_cookie_flags():
    html = "<html><body><h1>Plain page</h1></body></html>"
    headers = httpx.Headers(
        {
            "Set-Cookie": "sessionid=abc123; Path=/",
        }
    )
    evaluator = DrupalEvaluator()

    with patch.object(DrupalEvaluator, "_fetch_headers", AsyncMock(return_value=headers)):
        result = await evaluator.evaluate(
            html,
            "https://example.com",
            check_api=False,
        )

    issue_ids = [issue.id for issue in result.issues]
    assert "R-SEC-CSP-MISS" in issue_ids
    assert "R-SEC-HSTS-MISS" in issue_ids
    assert "R-SEC-XFRAME-MISS" in issue_ids
    assert "R-SEC-XCONTENT-MISS" in issue_ids
    assert "R-SEC-COOKIE-INSECURE" in issue_ids


@pytest.mark.asyncio
async def test_drupal_security_headers_present_and_cookie_list_fallback():
    html = "<html><body><h1>Secure page</h1></body></html>"
    headers = {
        "Content-Security-Policy": "default-src 'self'",
        "Strict-Transport-Security": "max-age=31536000; includeSubDomains",
        "X-Frame-Options": "SAMEORIGIN",
        "X-Content-Type-Options": "nosniff",
        "Set-Cookie": ["sessionid=abc; HttpOnly; Secure; SameSite=Lax"],
    }
    evaluator = DrupalEvaluator()

    with patch.object(DrupalEvaluator, "_fetch_headers", AsyncMock(return_value=headers)):
        result = await evaluator.evaluate(
            html,
            "https://example.com",
            check_api=False,
        )

    assert result.score >= 9.0
    assert result.metadata["has_csp"] is True
    assert result.metadata["has_hsts"] is True


@pytest.mark.asyncio
async def test_drupal_fetch_headers_falls_back_to_get():
    evaluator = DrupalEvaluator()
    client = AsyncMock()
    client.head = AsyncMock(side_effect=RuntimeError("head blocked"))
    client.get = AsyncMock(return_value=AsyncMock(headers={"X-Test": "ok"}))

    headers = await evaluator._fetch_headers("https://example.com", client)

    assert headers == {"X-Test": "ok"}
    client.head.assert_awaited_once()
    client.get.assert_awaited_once()

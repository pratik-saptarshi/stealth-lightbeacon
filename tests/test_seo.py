"""
test_seo.py — Unit tests for the SeoEvaluator module.
"""

import pytest
import httpx
from modules.seo import SeoEvaluator
from modules.base import EvaluationResult

@pytest.mark.asyncio
async def test_seo_evaluator_valid_html(mock_html_valid: str):
    """
    Verifies that a perfectly structured HTML page receives a high score and no critical issues.
    """
    evaluator = SeoEvaluator()
    result = await evaluator.evaluate(mock_html_valid, "https://example.com/acme-widgets")
    
    assert isinstance(result, EvaluationResult)
    assert result.domain == "Technical SEO"
    assert result.score >= 8.0
    
    # Check issue IDs
    issue_ids = [issue.id for issue in result.issues]
    assert "R-SEO-CAN-MISS" not in issue_ids
    assert "R-SEO-LD-MISS" not in issue_ids
    assert "R-SEO-TITLE-MISS" not in issue_ids
    assert "R-SEO-DESC-MISS" not in issue_ids

@pytest.mark.asyncio
async def test_seo_evaluator_invalid_html(mock_html_invalid: str):
    """
    Verifies that a poorly configured HTML page receives a low score and flags all diagnostic issues.
    """
    evaluator = SeoEvaluator()
    result = await evaluator.evaluate(mock_html_invalid, "https://example.com/stale-page")
    
    assert isinstance(result, EvaluationResult)
    assert result.score <= 6.0
    
    issue_ids = [issue.id for issue in result.issues]
    
    # Verify expected critical issues are flagged
    assert "R-SEO-CAN-MISS" in issue_ids
    assert "R-SEO-LD-MISS" in issue_ids
    assert any(issue_id.startswith("R-SEO-DESC-") for issue_id in issue_ids)
    assert "R-SEO-ROBOTS-NOINDEX" in issue_ids


@pytest.mark.asyncio
async def test_seo_evaluator_handles_none_like_attributes():
    """
    Verifies that malformed attributes that parse as None do not crash the evaluator.
    """
    html = """<!DOCTYPE html>
<html>
<head>
  <title>Example</title>
  <link rel="canonical" href>
  <meta name="description" content>
  <meta name="robots" content>
</head>
<body>
  <main>Content</main>
</body>
</html>
"""
    evaluator = SeoEvaluator()
    result = await evaluator.evaluate(html, "https://example.com/none-attrs")

    assert isinstance(result, EvaluationResult)
    issue_ids = [issue.id for issue in result.issues]
    assert "R-SEO-CAN-EMPTY" in issue_ids
    assert "R-SEO-DESC-MISS" in issue_ids

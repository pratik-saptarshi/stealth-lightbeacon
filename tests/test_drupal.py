"""
test_drupal.py — Unit tests for the DrupalEvaluator module.
"""

import pytest
import httpx
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
    result = await evaluator.evaluate(mock_html_drupal, "https://example.com")
    
    assert isinstance(result, EvaluationResult)
    assert result.domain == "Drupal & Security Headers"
    
    # Fingerprints should yield INFO notices, score remains relatively stable
    assert result.score >= 8.5
    
    issue_ids = [issue.id for issue in result.issues]
    assert "R-DRUP-FINGERPRINT" in issue_ids
    assert "R-DRUP-CORE-PATHS" in issue_ids

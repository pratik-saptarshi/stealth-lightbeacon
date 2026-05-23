"""
test_accessibility.py — Unit tests for the AccessibilityEvaluator module.
"""

import pytest
from modules.accessibility import AccessibilityEvaluator
from modules.base import EvaluationResult

@pytest.mark.asyncio
async def test_accessibility_valid_html(mock_html_valid: str):
    """
    Verifies that a valid HTML page passes accessibility checks with a high score.
    """
    evaluator = AccessibilityEvaluator()
    result = await evaluator.evaluate(mock_html_valid, "https://example.com/acme-widgets")
    
    assert isinstance(result, EvaluationResult)
    assert result.domain == "Accessibility (WCAG 2.2 AA)"
    assert result.score >= 9.0
    assert not result.issues

@pytest.mark.asyncio
async def test_accessibility_invalid_html(mock_html_invalid: str):
    """
    Verifies that an invalid HTML page receives a poor score and flags key issues.
    """
    evaluator = AccessibilityEvaluator()
    result = await evaluator.evaluate(mock_html_invalid, "https://example.com/bad-page")
    
    assert isinstance(result, EvaluationResult)
    assert result.score < 6.0
    
    issue_ids = [issue.id for issue in result.issues]
    
    assert "R-A11Y-ALT-MISS-0" in issue_ids
    assert "R-A11Y-H1-MULTIPLE" in issue_ids
    assert "R-A11Y-HEAD-SKIP-2" in issue_ids
    assert "R-A11Y-IA-EMPTY-0" in issue_ids

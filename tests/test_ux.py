"""
test_ux.py — Unit tests for the UxEvaluator module.
"""

import pytest
from modules.ux import UxEvaluator
from modules.base import EvaluationResult

@pytest.fixture
def mock_html_ux_invalid() -> str:
    """
    Returns a mock HTML page containing heavy UX and mobile responsiveness violations.
    """
    return """<!DOCTYPE html>
<html>
<head>
  <title>Bad UX Page</title>
  <!-- Missing viewport meta tag completely -->
</head>
<body>
  <nav id="main-menu" class="menu">
    <ul>
      <li><a href="/">Home</a>
        <ul>
          <li><a href="/products">Products</a>
            <ul>
              <li><a href="/products/widgets">Widgets</a>
                <ul>
                  <li><a href="/products/widgets/blue" style="height: 24px; font-size: 10px;">Blue Widgets (Nested Level 4)</a></li>
                </ul>
              </li>
            </ul>
          </li>
        </ul>
      </li>
    </ul>
  </nav>
</body>
</html>
"""

@pytest.mark.asyncio
async def test_ux_evaluator_valid(mock_html_valid: str):
    """
    Verifies that a well-designed page passes UX heuristics smoothly.
    """
    evaluator = UxEvaluator()
    result = await evaluator.evaluate(mock_html_valid, "https://example.com/acme")
    
    assert isinstance(result, EvaluationResult)
    assert result.domain == "UX Performance"
    assert result.score >= 9.0
    assert not result.issues

@pytest.mark.asyncio
async def test_ux_evaluator_invalid(mock_html_ux_invalid: str):
    """
    Verifies that responsive viewports, small fonts, deep nested menus, and tiny buttons are successfully flagged.
    """
    evaluator = UxEvaluator()
    result = await evaluator.evaluate(mock_html_ux_invalid, "https://example.com/bad-ux")
    
    assert isinstance(result, EvaluationResult)
    assert result.score < 8.0
    
    issue_ids = [issue.id for issue in result.issues]
    
    assert "R-UX-VIEWPORT-MISS" in issue_ids
    assert "R-UX-NAV-DEPTH" in issue_ids
    assert "R-UX-FONT-SMALL-0" in issue_ids
    assert "R-UX-TAP-HEIGHT-1" in issue_ids


@pytest.mark.asyncio
async def test_ux_evaluator_handles_none_like_attributes():
    """
    Verifies that malformed attributes that parse as None do not crash the evaluator.
    """
    html = """<!DOCTYPE html>
<html>
<head>
  <title>Example UX</title>
  <meta name="viewport" content>
</head>
<body>
  <nav id>
    <a href="/example" style>Example</a>
  </nav>
</body>
</html>
"""
    evaluator = UxEvaluator()
    result = await evaluator.evaluate(html, "https://example.com/ux-none-attrs")

    assert isinstance(result, EvaluationResult)
    issue_ids = [issue.id for issue in result.issues]
    assert "R-UX-VIEWPORT-WIDTH" in issue_ids

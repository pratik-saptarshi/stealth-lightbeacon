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

@pytest.mark.asyncio
async def test_accessibility_flags_generic_and_decorative_image_alt_texts():
    """
    Verifies that image alt variants are classified correctly.
    """
    html = """<!DOCTYPE html>
<html lang="en">
<head>
  <title>Image Variants</title>
</head>
<body>
  <h1>Media Library</h1>
  <img src="hero.jpg" alt="hero.jpg">
  <img src="decorative.png" alt="">
  <img src="photo.png" alt="photo">
</body>
</html>
"""

    evaluator = AccessibilityEvaluator()
    result = await evaluator.evaluate(html, "https://example.com/image-variants")

    issue_ids = [issue.id for issue in result.issues]

    assert "R-A11Y-ALT-BAD-0" in issue_ids
    assert "R-A11Y-ALT-BAD-2" in issue_ids
    assert result.score < 10.0

@pytest.mark.asyncio
async def test_accessibility_covers_heading_interactive_and_form_paths():
    """
    Verifies that the evaluator handles missing H1s, skipped headings, wrapped-image links,
    empty interactive controls, and the main form-label branches.
    """
    html = """<!DOCTYPE html>
<html lang="en">
<head>
  <title>Forms and Controls</title>
</head>
<body>
  <h2>Secondary Heading</h2>
  <h4>Skipped Heading</h4>
  <a href="/wrapped"><img src="icon.svg" alt="Icon"></a>
  <button></button>
  <a href="/empty"></a>
  <form>
    <input type="hidden" name="csrf" value="abc123">
    <label for="email">Email</label>
    <input id="email" name="email" type="email">
    <input name="nickname" aria-label="Nickname">
    <label><textarea name="bio"></textarea></label>
    <input name="dept" aria-labelledby="dept-label">
    <span id="dept-label">Department</span>
    <input name="plain">
  </form>
</body>
</html>
"""

    evaluator = AccessibilityEvaluator()
    result = await evaluator.evaluate(html, "https://example.com/forms-and-controls")

    issue_ids = [issue.id for issue in result.issues]

    assert "R-A11Y-H1-MISS" in issue_ids
    assert "R-A11Y-HEAD-SKIP-1" in issue_ids
    assert "R-A11Y-IA-EMPTY-1" in issue_ids
    assert "R-A11Y-IA-EMPTY-2" in issue_ids
    assert "R-A11Y-FORM-LABEL-0-4" in issue_ids
    assert "R-A11Y-FORM-SUBMIT-0" in issue_ids
    assert result.score < 8.0

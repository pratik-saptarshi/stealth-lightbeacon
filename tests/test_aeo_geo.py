"""
test_aeo_geo.py — Unit tests for the AeoGeoEvaluator module.
"""

import pytest
from modules.aeo_geo import AeoGeoEvaluator
from modules.base import EvaluationResult

@pytest.fixture
def mock_html_aeo_geo_opt() -> str:
    """
    Returns a mock HTML page highly optimized for AEO and GEO metrics.
    """
    return """<!DOCTYPE html>
<html lang="en">
<head>
  <title>AEO Optimization</title>
  <script type="application/ld+json">
  {
    "@context": "https://schema.org",
    "@type": "Article",
    "headline": "AEO Optimization Guide",
    "datePublished": "2026-05-23T12:00:00Z",
    "author": {
      "@type": "Person",
      "name": "Dr. Sarah Jenkins",
      "jobTitle": "Search Optimization Analyst",
      "sameAs": "https://twitter.com/sarahjenkins"
    }
  }
  </script>
</head>
<body>
  <h2>What is Answer Engine Optimization?</h2>
  <p>Answer Engine Optimization is a technical methodology designed to structure content so that generative AI search engines can easily fetch and parse definitions directly for users.</p>
  
  <p>Learn more about this topic on <a href="https://wikipedia.org/wiki/Search_engine_optimization">Wikipedia</a> and read advanced studies on <a href="https://arxiv.org/abs/2401.00000">arXiv</a>.</p>
</body>
</html>
"""

@pytest.fixture
def mock_html_stuffed() -> str:
    """
    Returns a mock HTML page containing heavy keyword stuffing.
    """
    return """<!DOCTYPE html>
<html>
<head><title>Stuffed Page</title></head>
<body>
  <p>Widget is the best widget. Buy widget here. We sell blue widget, red widget, and green widget. Every widget is a durable widget. Choose a widget today. Excellent widget performance is guaranteed by our widget engineering team.</p>
</body>
</html>
"""


@pytest.fixture
def mock_html_aeo_geo_warning() -> str:
    return """<!DOCTYPE html>
<html lang="en">
<head>
  <title>AEO Gaps</title>
  <script type="application/ld+json">{"@context":"https://schema.org","@type":"WebPage"}</script>
</head>
<body>
  <h1>Overview</h1>
  <h3>What is answer engine optimization?</h3>
  <p>Too short.</p>
  <p>Reference material at <a href="https://example.com/source">Example</a>.</p>
</body>
</html>
"""


@pytest.fixture
def mock_html_aeo_geo_malformed_jsonld() -> str:
    return """<!DOCTYPE html>
<html>
<head>
  <script type="application/ld+json">{not valid json}</script>
</head>
<body>
  <p>Plain prose without question headings or citations.</p>
</body>
</html>
"""

@pytest.mark.asyncio
async def test_aeo_geo_valid_opt(mock_html_aeo_geo_opt: str):
    """
    Verifies that a page with E-E-A-T profiles, fresh dates, authoritative links, and Q&A formats
    passes with high scores.
    """
    evaluator = AeoGeoEvaluator()
    result = await evaluator.evaluate(mock_html_aeo_geo_opt, "https://example.com/opt-page")
    
    assert isinstance(result, EvaluationResult)
    assert result.domain == "AEO & GEO Optimization"
    assert result.score >= 8.5
    assert not result.issues

@pytest.mark.asyncio
async def test_aeo_geo_invalid_stuffed(mock_html_stuffed: str):
    """
    Verifies that page isolations, missing schemas, and keyword stuffing are successfully identified.
    """
    evaluator = AeoGeoEvaluator()
    result = await evaluator.evaluate(mock_html_stuffed, "https://example.com/stuffed")
    
    assert isinstance(result, EvaluationResult)
    assert result.score < 7.0
    
    issue_ids = [issue.id for issue in result.issues]
    
    assert "R-GEO-STUFFING-WARN" in issue_ids
    assert "R-GEO-CIT-NONE" in issue_ids
    assert "R-GEO-EEAT-AUTHOR" in issue_ids


@pytest.mark.asyncio
async def test_aeo_geo_warning_paths_and_malformed_jsonld(
    mock_html_aeo_geo_warning: str,
    mock_html_aeo_geo_malformed_jsonld: str,
):
    evaluator = AeoGeoEvaluator()

    warning_result = await evaluator.evaluate(
        mock_html_aeo_geo_warning,
        "https://example.com/warn",
    )
    warning_ids = [issue.id for issue in warning_result.issues]

    assert "R-AEO-SNIPPET-LEN" in warning_ids
    assert "R-AEO-HEAD-SKIP" in warning_ids
    assert "R-GEO-CIT-LOW" in warning_ids

    malformed_result = await evaluator.evaluate(
        mock_html_aeo_geo_malformed_jsonld,
        "https://example.com/malformed",
    )
    malformed_ids = [issue.id for issue in malformed_result.issues]

    assert "R-AEO-QA-NONE" in malformed_ids
    assert "R-AEO-HEADINGS-MISS" in malformed_ids
    assert "R-GEO-CIT-NONE" in malformed_ids


@pytest.mark.asyncio
async def test_aeo_geo_nested_jsonld_list_shapes():
    html = """<!DOCTYPE html>
<html lang="en">
<head>
  <script type="application/ld+json">
  [
    {
      "@graph": [
        {
          "@type": ["Article", "WebPage"],
          "headline": "Nested article",
          "author": {
            "@type": "Person",
            "name": "Nested Author",
            "jobTitle": "Editor"
          },
          "dateModified": "2026-05-27T00:00:00Z"
        }
      ]
    }
  ]
  </script>
</head>
<body>
  <h2>How does nested schema work?</h2>
  <p>This answer intentionally stays concise and cites <a href="https://wikipedia.org/wiki/Schema.org">Wikipedia</a>.</p>
</body>
</html>
"""
    result = await AeoGeoEvaluator().evaluate(html, "https://example.com/nested")

    assert result.metadata["eeat_author_found"] is True
    assert result.metadata["readiness_components"]["structured_data"] == 10.0
    assert result.metadata["qa_outline_found"] is True

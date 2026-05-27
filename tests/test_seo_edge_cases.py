from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from modules.seo import SeoEvaluator


@pytest.mark.asyncio
async def test_seo_evaluator_flags_mixed_metadata_and_schema_warnings():
    html = """<!DOCTYPE html>
<html>
<head>
  <title>Short</title>
  <link rel="canonical" href="http://example.com/other">
  <meta name="description" content="too short">
  <meta name="robots" content="noindex">
  <script type="application/ld+json">{bad json</script>
</head>
<body>
  <main>Content</main>
</body>
</html>
"""

    evaluator = SeoEvaluator()
    with patch.object(SeoEvaluator, "_fetch_robots_txt", new=AsyncMock(return_value=None)):
        result = await evaluator.evaluate(html, "https://example.com/page")

    issue_ids = {issue.id for issue in result.issues}

    assert "R-SEO-CAN-SCHEME" in issue_ids
    assert "R-SEO-LD-PARSE-0" in issue_ids
    assert "R-SEO-TITLE-LEN" in issue_ids
    assert "R-SEO-DESC-LEN" in issue_ids
    assert "R-SEO-OG-MISS" in issue_ids
    assert "R-SEO-ROBOTS-NOINDEX" in issue_ids
    assert "R-SEO-ROBOTS-MISS" in issue_ids

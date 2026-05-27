from modules.base import EvaluationResult, Issue
from report.generator import ReportGenerator


def test_report_generator_writes_escaped_html(tmp_path):
    results = [
        EvaluationResult(
            domain="Technical SEO",
            score=8.5,
            issues=(
                Issue(
                    id="R-SEO-TITLE-LEN",
                    severity="warning",
                    message="<script>alert('x')</script>",
                    location="<title>",
                    remedy="Shorten the title.",
                ),
            ),
            metadata={"crawled_pages_count": 1},
        )
    ]

    ReportGenerator.generate_report("https://example.com", results, str(tmp_path))

    html_path = tmp_path / "report.html"
    assert html_path.exists()

    html = html_path.read_text(encoding="utf-8")
    assert "Audit Engine Version:</strong> v1.2.5" in html
    assert "&lt;script&gt;alert(&#39;x&#39;)&lt;/script&gt;" in html
    assert "<script>alert('x')</script>" not in html
    assert "Technical SEO" in html
    assert "8.5/10.0" in html

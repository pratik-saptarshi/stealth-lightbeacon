from pathlib import Path

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
                Issue(
                    id="R-SEO-TITLE-LEN",
                    severity="warning",
                    message="<script>alert('x')</script>",
                    location="<h1>",
                    remedy="Shorten the title.",
                ),
            ),
            metadata={"crawled_pages_count": 1},
        )
    ]

    report_paths = ReportGenerator.generate_report("https://example.com", results, str(tmp_path))

    html_path = Path(report_paths["html_path"])
    assert html_path.exists()
    assert html_path.parent.name == "example-com"
    assert html_path.name.startswith("example-com_report_")
    assert "_score-8p5_result-success.html" in html_path.name
    assert Path(report_paths["legacy_html_path"]).exists()

    html = html_path.read_text(encoding="utf-8")
    assert "v1.2.7" in html
    assert "&lt;script&gt;alert(&#39;x&#39;)&lt;/script&gt;" in html
    assert "<script>alert('x')</script>" not in html
    assert "Technical SEO" in html
    assert "8.5/10" in html
    assert html.count("R-SEO-TITLE-LEN") == 1
    assert ">2<" in html

    pdf_path = Path(report_paths["pdf_path"])
    assert pdf_path.exists()
    assert pdf_path.read_bytes().startswith(b"%PDF")
    assert Path(report_paths["legacy_pdf_path"]).exists()


def test_grouped_issues_keeps_domains_distinct_for_same_id_and_message():
    domains = [
        {
            "name": "Technical SEO",
            "issues": [
                {
                    "id": "DUP-1",
                    "message": "Duplicate issue text",
                    "severity": "warning",
                    "location": "/seo",
                    "remedy": "Fix SEO thing",
                }
            ],
        },
        {
            "name": "Accessibility",
            "issues": [
                {
                    "id": "DUP-1",
                    "message": "Duplicate issue text",
                    "severity": "warning",
                    "location": "/a11y",
                    "remedy": "Fix a11y thing",
                }
            ],
        },
    ]

    grouped = ReportGenerator._group_issues(domains)

    assert len(grouped) == 2
    assert {item["domain"] for item in grouped} == {"Technical SEO", "Accessibility"}
    assert all(item["occurrences"] == 1 for item in grouped)

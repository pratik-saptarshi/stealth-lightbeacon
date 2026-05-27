import json
import xml.etree.ElementTree as ET

import pytest

from modules.base import EvaluationResult, Issue
from report.formats import build_report_payload, normalize_report_payload, render_report_format


def _sample_results():
    return [
        EvaluationResult(
            domain="Technical SEO",
            score=8.5,
            issues=(
                Issue(
                    id="R-SEO-TITLE-LEN",
                    severity="warning",
                    message="Title is too long.",
                    location="<title>",
                    remedy="Shorten the title.",
                ),
            ),
            metadata={"crawled_pages_count": 1},
        ),
        EvaluationResult(
            domain="Accessibility (WCAG 2.2 AA)",
            score=9.0,
            issues=tuple(),
            metadata={"crawled_pages_count": 1},
        ),
    ]


def test_report_payload_and_markdown_rendering():
    payload = build_report_payload("https://example.com", _sample_results())

    assert payload["target_url"] == "https://example.com"
    assert payload["average_score"] == pytest.approx(8.75)
    assert payload["total_issues"] == 1
    assert payload["domains"][0]["name"] == "Technical SEO"

    markdown = render_report_format("llm", payload)
    assert "# Stealth Lightbeacon Audit Report" in markdown
    assert "## Technical SEO" in markdown
    assert "- `R-SEO-TITLE-LEN`" in markdown
    assert "<html" not in markdown.lower()


def test_geo_xml_rendering_is_well_formed():
    payload = build_report_payload("https://example.com", _sample_results())

    xml_text = render_report_format("geo-xml", payload)
    root = ET.fromstring(xml_text)

    assert root.tag == "geoAuditReport"
    assert root.findtext("targetUrl") == "https://example.com"
    assert root.find("domains/domain") is not None
    assert root.find("domains/domain/name").text == "Technical SEO"


def test_legacy_payload_shapes_are_normalized():
    legacy_payload = {
        "targetUrl": "https://example.com",
        "averageScore": 7.5,
        "totalIssues": 1,
        "domains": [
            {
                "domain": "Technical SEO",
                "score": 7.5,
                "issues": [
                    {
                        "id": "R-SEO-TITLE-LEN",
                        "severity": "warning",
                        "message": "Title is too long.",
                        "location": "<title>",
                        "remedy": "Shorten the title.",
                    }
                ],
                "metadata": {"source": "legacy"},
            }
        ],
    }

    normalized = normalize_report_payload(legacy_payload)

    assert normalized["target_url"] == "https://example.com"
    assert normalized["domains"][0]["name"] == "Technical SEO"
    assert normalized["domains"][0]["metadata"] == {"source": "legacy"}

    rendered = render_report_format("json", legacy_payload)
    parsed = json.loads(rendered)
    assert parsed["target_url"] == "https://example.com"
    assert parsed["domains"][0]["name"] == "Technical SEO"


def test_report_payload_normalizes_legacy_defaults():
    legacy_payload = {
        "targetUrl": "https://example.com",
        "domains": [
            {
                "domain": "Technical SEO",
                "score": "7.25",
                "issues": [
                    {
                        "id": "R-SEO-TITLE-LEN",
                        "severity": "warning",
                        "message": "Title is too long.",
                        "location": "<title>",
                        "remedy": "Shorten the title.",
                    },
                    "skip-me",
                ],
                "metadata": "not-a-mapping",
            },
            {
                "name": "Accessibility (WCAG 2.2 AA)",
                "score": 8.75,
                "issues": [],
            },
        ],
    }

    normalized = normalize_report_payload(legacy_payload)

    assert normalized["average_score"] == pytest.approx(8.0)
    assert normalized["total_issues"] == 1
    assert normalized["domains"][0]["metadata"] == {}
    assert len(normalized["domains"][0]["issues"]) == 1

    rendered = render_report_format(" JSON ", legacy_payload)
    parsed = json.loads(rendered)
    assert parsed["average_score"] == pytest.approx(8.0)
    assert parsed["domains"][0]["name"] == "Technical SEO"


def test_unknown_report_format_is_rejected():
    payload = build_report_payload("https://example.com", _sample_results())

    with pytest.raises(ValueError):
        render_report_format("pdf", payload)

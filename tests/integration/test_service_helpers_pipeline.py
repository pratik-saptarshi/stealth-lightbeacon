"""
Integration coverage for helper layers used by the service pipeline.
"""

from __future__ import annotations

import json

from modules.base import EvaluationResult, Issue
from report.formats import build_report_payload, normalize_report_payload, render_report_format
from services.evaluators import select_active_evaluators
from services.runtime import build_runtime_settings


def test_service_helper_selection_and_runtime_resolution(monkeypatch, tmp_path):
    monkeypatch.setenv("SLB_TARGET_URL", "https://example.com/from-env")
    monkeypatch.setenv("SLB_AUDITS", "seo,drupal")
    monkeypatch.setenv("SLB_AUTH_TOKEN", "token-123")
    monkeypatch.setenv("SLB_FAIL_ON_CRITICAL", "yes")

    settings = build_runtime_settings(
        url=None,
        audits=None,
        fail_on_critical=False,
        output_dir=str(tmp_path / "out"),
    )

    assert settings.url == "https://example.com/from-env"
    assert settings.audits == ["seo", "drupal"]
    assert settings.auth_token == "token-123"
    assert settings.fail_on_critical is True

    default_names = [type(e).__name__ for e in select_active_evaluators(None)]
    assert "SeoEvaluator" in default_names
    assert "DrupalEvaluator" in default_names

    alias_names = [type(e).__name__ for e in select_active_evaluators("all")]
    assert len(alias_names) == len(default_names)

    selected = [type(e).__name__ for e in select_active_evaluators("aeo,geo,security")]
    assert "AeoGeoEvaluator" in selected
    assert "DrupalEvaluator" in selected


def test_report_helpers_and_renderers(tmp_path):
    payload = build_report_payload(
        "https://example.com",
        [
            EvaluationResult(
                domain="Technical SEO",
                score=8.5,
                issues=(
                    Issue(
                        id="R-SEO-DESC-LEN",
                        severity="warning",
                        message="Meta description is suboptimal.",
                        location="<meta name=\"description\">",
                        remedy="Adjust the summary length.",
                    ),
                ),
                metadata={"source": "integration"},
            )
        ],
    )

    assert payload["target_url"] == "https://example.com"
    assert payload["total_issues"] == 1
    assert payload["domains"][0]["metadata"] == {"source": "integration"}

    legacy = normalize_report_payload(
        {
            "targetUrl": "https://example.com/legacy",
            "averageScore": 4.2,
            "totalIssues": 3,
            "domains": [
                {
                    "domain": "Legacy",
                    "score": 4.2,
                    "issues": [
                        {
                            "id": "LEG-1",
                            "severity": "info",
                            "message": "legacy",
                            "location": "",
                            "remedy": "",
                        }
                    ],
                    "metadata": {"legacy": True},
                }
            ],
        }
    )
    assert legacy["target_url"] == "https://example.com/legacy"
    assert legacy["average_score"] == 4.2
    assert legacy["total_issues"] == 3

    rendered_json = render_report_format("json", payload)
    assert json.loads(rendered_json)["target_url"] == "https://example.com"

    rendered_markdown = render_report_format("llm", payload)
    assert "# Stealth Lightbeacon Audit Report" in rendered_markdown

    rendered_geo_xml = render_report_format("geo-xml", payload)
    assert "<geoAuditReport" in rendered_geo_xml

    out_file = tmp_path / "report.json"
    from main import save_json_report

    save_json_report(
        "https://example.com",
        [
            EvaluationResult(
                domain="Technical SEO",
                score=8.5,
                issues=(
                    Issue(
                        id="R-SEO-DESC-LEN",
                        severity="warning",
                        message="Meta description is suboptimal.",
                        location="<meta name=\"description\">",
                        remedy="Adjust the summary length.",
                    ),
                ),
                metadata={"source": "integration"},
            )
        ],
        str(out_file),
    )
    assert out_file.exists()

import pytest

from modules.base import EvaluationResult, Issue
from utils.crawl_diff import compare_audit_reports, compare_audit_runs


def test_crawl_diff_detects_regressions_and_improvements():
    previous = {
        "target_url": "https://example.com",
        "domains": [
            {
                "name": "Technical SEO",
                "score": 8.0,
                "issues": [{"id": "R-SEO-TITLE-LEN", "severity": "warning"}],
            }
        ],
    }
    current = {
        "target_url": "https://example.com",
        "domains": [
            {
                "name": "Technical SEO",
                "score": 6.5,
                "issues": [
                    {"id": "R-SEO-TITLE-LEN", "severity": "warning"},
                    {"id": "R-SEO-CAN-MISS", "severity": "critical"},
                ],
            }
        ],
    }

    diff = compare_audit_reports(previous, current)

    assert diff["score_delta"] == pytest.approx(-1.5)
    assert "Technical SEO" in diff["regressions"]
    assert "R-SEO-CAN-MISS" in diff["new_issue_ids"]


@pytest.mark.asyncio
async def test_compare_audit_runs_uses_persisted_reports():
    report_a = {
        "targetUrl": "https://example.com",
        "domains": [{"domain": "Technical SEO", "score": 8.0, "issues": []}],
    }
    report_b = {
        "targetUrl": "https://example.com",
        "domains": [{"domain": "Technical SEO", "score": 7.0, "issues": [{"id": "R-SEO-LD-MISS"}]}],
    }

    class DummyStore:
        def __init__(self):
            self.duck_conn = type(
                "Conn",
                (),
                {
                    "execute": lambda self, sql, params=None: type(
                        "R",
                        (),
                        {
                            "fetchone": lambda self: (
                                {"run_a": report_a, "run_b": report_b}[params[0]],
                            )
                        },
                    )(),
                },
            )()

    diff = await compare_audit_runs(DummyStore(), "run_a", "run_b")

    assert diff["score_delta"] == pytest.approx(-1.0)
    assert "R-SEO-LD-MISS" in diff["new_issue_ids"]


@pytest.mark.asyncio
async def test_compare_audit_runs_uses_raw_sql_fallback_and_missing_run():
    report_a = {"targetUrl": "https://example.com", "domains": []}

    class RawStore:
        def __init__(self):
            self.duck_conn = type(
                "Conn",
                (),
                {
                "execute": lambda self, sql, params=None: type(
                    "R",
                    (),
                    {
                        "fetchone": lambda self: (
                            '{"target_url": "https://example.com", "domains": []}',
                        )
                        if params[0] == "run_a"
                        else None
                    },
                )(),
                },
            )()

    with pytest.raises(ValueError, match="Missing audit run"):
        await compare_audit_runs(RawStore(), "run_a", "run_b")

    diff = await compare_audit_runs(
        type(
            "Store",
            (),
            {
                "duck_conn": type(
                    "Conn",
                    (),
                    {
                        "execute": lambda self, sql, params=None: type(
                            "R",
                            (),
                            {
                                "fetchone": lambda self: (
                                    '{"target_url": "https://example.com", "domains": []}',
                                )
                                if params[0] == "run_a"
                                else (
                                    '{"target_url": "https://example.com", "domains": [{"name": "Technical SEO", "score": 5.0, "issues": []}]}',
                                )
                            },
                        )(),
                    },
                )(),
            },
        )(),
        "run_a",
        "run_b",
    )

    assert diff["score_delta"] == pytest.approx(5.0)

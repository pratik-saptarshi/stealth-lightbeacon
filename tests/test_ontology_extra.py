from pathlib import Path

import pytest

import utils.ontology as ontology
from utils.ontology import OntologyStore


@pytest.mark.asyncio
async def test_ontology_store_fallback_health_and_diff(tmp_path, monkeypatch):
    monkeypatch.setattr(ontology, "DUCKDB_AVAILABLE", False)
    monkeypatch.setattr(ontology, "LANCEDB_AVAILABLE", False)

    store = OntologyStore(root_dir=str(tmp_path / "store"), vector_dimensions=8)

    try:
        await store.begin_run("run-a", "https://example.com/a", "2026-01-01T00:00:00Z", {"crawl_depth": 1})
        await store.record_page(
            "run-a",
            "https://example.com/a",
            "<html><body>alpha</body></html>",
            status_code=200,
            response_time_ms=50,
            headers={"Content-Type": "text/html"},
        )
        await store.finish_run(
            "run-a",
            {
                "targetUrl": "https://example.com/a",
                "domains": [
                    {
                        "name": "Technical SEO",
                        "score": 6.0,
                        "issues": [{"id": "A"}],
                    }
                ],
            },
            page_count=1,
            domain_count=1,
        )

        await store.begin_run("run-b", "https://example.com/b", "2026-01-02T00:00:00Z", {"crawl_depth": 2})
        await store.record_page(
            "run-b",
            "https://example.com/b",
            "<html><title>Beta</title><body>beta</body></html>",
            status_code=200,
            response_time_ms=25,
            headers={"Content-Type": "text/html"},
        )
        await store.record_finding(
            "run-b",
            "https://example.com/b",
            "Accessibility",
            "B",
            "warning",
            "Beta finding",
            location="body",
            remedy="Fix beta",
            metadata={"tag": "body"},
        )
        await store.finish_run(
            "run-b",
            {
                "targetUrl": "https://example.com/b",
                "domains": [
                    {
                        "name": "Technical SEO",
                        "score": 9.0,
                        "issues": [],
                    },
                    {
                        "name": "Accessibility",
                        "score": 8.0,
                        "issues": [{"id": "B"}],
                    },
                ],
            },
            page_count=1,
            domain_count=2,
        )

        diff = await store.diff_runs("run-a", "run-b")
        assert diff["score_delta"] > 0
        assert diff["added_domains"] == ["Accessibility"]
        assert diff["regressions"] == []
        assert diff["improvements"] == ["Accessibility", "Technical SEO"] or diff["improvements"] == ["Technical SEO", "Accessibility"]
        assert diff["new_issue_ids"] == ["B"]
        assert diff["resolved_issue_ids"] == ["A"]

        health = store.health()
        assert health["duckDbReady"] is True
        assert health["lanceDbReady"] is False
        assert store.duck_conn.tables["audit_pages"][0]["title"] == "https://example.com/a"
        assert store.search("beta finding", limit=1)
    finally:
        store.close()


@pytest.mark.asyncio
async def test_ontology_store_missing_report_raises(tmp_path, monkeypatch):
    monkeypatch.setattr(ontology, "DUCKDB_AVAILABLE", False)
    monkeypatch.setattr(ontology, "LANCEDB_AVAILABLE", False)

    store = OntologyStore(root_dir=str(tmp_path / "missing"), vector_dimensions=8)
    try:
        with pytest.raises(ValueError, match="Missing audit run"):
            await store.get_run_report("does-not-exist")
    finally:
        store.close()

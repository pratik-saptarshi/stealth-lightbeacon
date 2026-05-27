import asyncio

import pytest

import utils.ontology as ontology
from utils.ontology import OntologyStore


class _FailingVectorStore:
    def __init__(self):
        self.insert_batches = []

    def insert(self, rows):
        self.insert_batches.append([dict(row) for row in rows])
        raise RuntimeError("vector store unavailable")

    def search(self, query_vector, limit=10):
        return []


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


@pytest.mark.asyncio
async def test_ontology_store_finish_run_survives_vector_store_failure(tmp_path, monkeypatch):
    monkeypatch.setattr(ontology, "DUCKDB_AVAILABLE", False)
    monkeypatch.setattr(ontology, "LANCEDB_AVAILABLE", False)

    store = OntologyStore(root_dir=str(tmp_path / "failing"), vector_dimensions=8)
    store.vector_store = _FailingVectorStore()

    try:
        await store.begin_run("run-fail", "https://example.com/fail", "2026-01-03T00:00:00Z", {"crawl_depth": 1})
        await store.record_page(
            "run-fail",
            "https://example.com/fail",
            "<html><body>fail</body></html>",
            status_code=200,
            response_time_ms=75,
        )
        await store.finish_run(
            "run-fail",
            {
                "targetUrl": "https://example.com/fail",
                "domains": [],
            },
            page_count=1,
            domain_count=0,
        )

        report = await store.get_run_report("run-fail")
        assert report["target_url"] == "https://example.com/fail"
        assert len(store.duck_conn.tables["audit_pages"]) == 1
        assert len(store.vector_store.insert_batches) >= 1
    finally:
        store.close()


@pytest.mark.asyncio
async def test_ontology_store_applies_backpressure_when_queue_saturates(tmp_path, monkeypatch):
    monkeypatch.setattr(ontology, "DUCKDB_AVAILABLE", False)
    monkeypatch.setattr(ontology, "LANCEDB_AVAILABLE", False)

    store = OntologyStore(
        root_dir=str(tmp_path / "backpressure"),
        vector_dimensions=8,
        persistence_queue_size=1,
    )

    original_ensure = store._ensure_persistence_worker
    monkeypatch.setattr(store, "_ensure_persistence_worker", lambda: None)

    try:
        await store.begin_run(
            "run-bp",
            "https://example.com/bp",
            "2026-01-04T00:00:00Z",
            {"crawl_depth": 1},
        )
        first_task = asyncio.create_task(
            store.record_page(
                "run-bp",
                "https://example.com/one",
                "<html><title>One</title><body>one</body></html>",
                status_code=200,
                response_time_ms=10,
            )
        )

        second_task = asyncio.create_task(
            store.record_page(
                "run-bp",
                "https://example.com/two",
                "<html><title>Two</title><body>two</body></html>",
                status_code=200,
                response_time_ms=20,
            )
        )

        await asyncio.sleep(0.1)
        assert not second_task.done()

        monkeypatch.setattr(store, "_ensure_persistence_worker", original_ensure)
        original_ensure()

        await first_task
        await second_task

        await store.finish_run(
            "run-bp",
            {
                "targetUrl": "https://example.com/bp",
                "domains": [],
            },
            page_count=2,
            domain_count=0,
        )

        assert len(store.duck_conn.tables["audit_pages"]) == 2
    finally:
        monkeypatch.setattr(store, "_ensure_persistence_worker", original_ensure)
        store.close()


@pytest.mark.asyncio
async def test_ontology_store_keeps_processing_after_worker_failure(tmp_path, monkeypatch):
    monkeypatch.setattr(ontology, "DUCKDB_AVAILABLE", False)
    monkeypatch.setattr(ontology, "LANCEDB_AVAILABLE", False)

    store = OntologyStore(
        root_dir=str(tmp_path / "failure-isolation"),
        vector_dimensions=8,
        persistence_queue_size=4,
    )

    original_process = store._process_persistence_item
    seen = {"count": 0}

    def flaky_process(item):
        seen["count"] += 1
        if seen["count"] == 1:
            raise RuntimeError("boom")
        return original_process(item)

    monkeypatch.setattr(store, "_process_persistence_item", flaky_process)

    try:
        await store.begin_run(
            "run-failover",
            "https://example.com/failover",
            "2026-01-05T00:00:00Z",
            {"crawl_depth": 1},
        )
        await store.record_page(
            "run-failover",
            "https://example.com/first",
            "<html><title>First</title><body>first</body></html>",
            status_code=200,
            response_time_ms=10,
        )
        await store.record_page(
            "run-failover",
            "https://example.com/second",
            "<html><title>Second</title><body>second</body></html>",
            status_code=200,
            response_time_ms=20,
        )
        await store.finish_run(
            "run-failover",
            {
                "targetUrl": "https://example.com/failover",
                "domains": [],
            },
            page_count=2,
            domain_count=0,
        )

        pages = store.duck_conn.tables["audit_pages"]
        assert len(pages) == 1
        assert pages[0]["page_url"] == "https://example.com/second"
        assert store._persistence_failures >= 1
    finally:
        store.close()

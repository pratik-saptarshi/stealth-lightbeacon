from __future__ import annotations

import asyncio
import threading

from utils.ontology import OntologyStore


def test_vector_writes_flow_through_background_worker(tmp_path):
    store = OntologyStore(root_dir=str(tmp_path / "service-store"), vector_dimensions=8)
    thread_names: list[str] = []
    original_insert = store._insert_vector_rows

    def wrapped_insert(rows):
        if rows and any(row.get("kind") != "run" for row in rows):
            thread_names.append(threading.current_thread().name)
        return original_insert(rows)

    store._insert_vector_rows = wrapped_insert

    try:
        asyncio.run(
            store.begin_run(
                run_id="run-queue",
                target_url="https://example.com",
                started_at="2026-05-27T00:00:00Z",
                options={"crawl_depth": 1},
            )
        )
        asyncio.run(
            store.record_page(
                run_id="run-queue",
                page_url="https://example.com/page",
                html_content="<html><title>Queue Test</title><body>alpha</body></html>",
                status_code=200,
                response_time_ms=20,
                headers={"Content-Type": "text/html"},
            )
        )
        asyncio.run(
            store.record_finding(
                run_id="run-queue",
                page_url="https://example.com/page",
                domain_id="Accessibility",
                issue_id="R-A11Y-ALT-MISSING",
                severity="critical",
                message="Missing alt text",
                location="img.logo",
                remedy="Add alt text",
                metadata={"tag": "img"},
            )
        )
        asyncio.run(
            store.finish_run(
                "run-queue",
                {"targetUrl": "https://example.com", "domains": []},
                page_count=1,
                domain_count=1,
            )
        )

        assert thread_names
        assert all(name != threading.current_thread().name for name in thread_names)
    finally:
        store.close()


def test_vector_batch_failure_falls_back_to_single_rows(tmp_path):
    class FlakyVectorStore:
        def __init__(self) -> None:
            self.calls: list[int] = []
            self.rows: list[dict] = []

        def insert(self, rows):
            self.calls.append(len(rows))
            if len(rows) > 1:
                raise RuntimeError("batch insert failed")
            self.rows.extend(rows)

        def search(self, *_args, **_kwargs):
            return []

    store = OntologyStore(root_dir=str(tmp_path / "service-store"), vector_dimensions=8)
    store.vector_store = FlakyVectorStore()
    store._vector_flush_threshold = 2

    try:
        asyncio.run(
            store.begin_run(
                run_id="run-fallback",
                target_url="https://example.com",
                started_at="2026-05-27T00:00:00Z",
                options={"crawl_depth": 1},
            )
        )
        asyncio.run(
            store.record_page(
                run_id="run-fallback",
                page_url="https://example.com/page",
                html_content="<html><title>Fallback Test</title><body>alpha</body></html>",
                status_code=200,
                response_time_ms=20,
                headers={"Content-Type": "text/html"},
            )
        )
        asyncio.run(
            store.record_finding(
                run_id="run-fallback",
                page_url="https://example.com/page",
                domain_id="Accessibility",
                issue_id="R-A11Y-ALT-MISSING",
                severity="critical",
                message="Missing alt text",
                location="img.logo",
                remedy="Add alt text",
                metadata={"tag": "img"},
            )
        )
        asyncio.run(
            store.finish_run(
                "run-fallback",
                {"targetUrl": "https://example.com", "domains": []},
                page_count=1,
                domain_count=1,
            )
        )

        assert store.vector_store.calls == [1, 1, 1]
        assert len(store.vector_store.rows) == 3
    finally:
        store.close()

from __future__ import annotations

import pytest

import utils.ontology as ontology
from utils.ontology import OntologyStore


@pytest.mark.asyncio
async def test_ontology_helper_validation_and_descriptor_paths(tmp_path, monkeypatch):
    monkeypatch.setattr(ontology, "DUCKDB_AVAILABLE", False)
    monkeypatch.setattr(ontology, "LANCEDB_AVAILABLE", False)

    store = OntologyStore(root_dir=str(tmp_path / "helpers"), vector_dimensions=8)
    try:
        with pytest.raises(ValueError, match="Evaluation target is required"):
            await store.create_evaluation({"target": "", "profile": "seo", "outputFormats": ["json"]})

        with pytest.raises(ValueError, match="At least one output format is required"):
            await store.create_evaluation({"target": "https://example.com", "profile": "seo", "outputFormats": []})

        assert store._normalize_output_formats([" json ", "both", "html", "json"]) == ["json", "html"]
        with pytest.raises(ValueError, match="supported output format"):
            store._normalize_output_formats(["bogus"])

        descriptors = store._build_artifact_descriptors(
            "eval-1",
            ["both"],
            base_url="https://example.com/base/",
        )
        assert [item["name"] for item in descriptors] == ["report.json", "report.html"]
        assert descriptors[0]["downloadUrl"] == "https://example.com/base/evaluations/eval-1/artifacts/report.json"

        status_payload = store._row_to_status_payload(
            {
                "evaluation_id": "eval-1",
                "status": "queued",
                "terminal": False,
                "stage": "queued",
                "progress_percent": 0,
                "message": "queued",
                "exit_state": None,
            }
        )
        assert status_payload["evaluationId"] == "eval-1"
        assert status_payload["progressPercent"] == 0

        with pytest.raises(ValueError, match="Missing terminal result"):
            store._row_to_result_payload({"evaluation_id": "eval-1", "result_json": None})
    finally:
        store.close()


@pytest.mark.asyncio
async def test_ontology_evaluation_lifecycle_and_artifacts(tmp_path, monkeypatch):
    monkeypatch.setattr(ontology, "DUCKDB_AVAILABLE", False)
    monkeypatch.setattr(ontology, "LANCEDB_AVAILABLE", False)

    store = OntologyStore(root_dir=str(tmp_path / "lifecycle"), vector_dimensions=8)
    try:
        created = await store.create_evaluation(
            {
                "target": "https://example.com",
                "profile": "seo",
                "outputFormats": ["both"],
                "maxDepth": 3,
                "maxUrls": 20,
                "failOnCritical": True,
                "budgetGate": True,
            },
            evaluation_id="eval-123",
            accepted_at="2026-05-27T00:00:00Z",
        )
        assert created["evaluationId"] == "eval-123"
        assert created["status"] == "queued"

        queued_status = await store.get_evaluation_status("eval-123")
        assert queued_status["status"] == "queued"
        assert queued_status["terminal"] is False

        running_status = await store.update_evaluation_status(
            "eval-123",
            status="running",
            stage="crawl",
            progress_percent=200,
            message="working",
        )
        assert running_status["stage"] == "crawl"
        assert running_status["progressPercent"] == 100

        report = {
            "targetUrl": "https://example.com",
            "averageScore": 7.2,
            "domains": [
                {
                    "name": "Technical SEO",
                    "score": 7.2,
                    "issues": [
                        {
                            "id": "R-SEO-TITLE-LEN",
                            "severity": "critical",
                            "message": "Title is too long.",
                            "location": "<title>",
                            "remedy": "Shorten the title.",
                        }
                    ],
                }
            ],
        }
        result = await store.complete_evaluation("eval-123", report, base_url="https://example.com")
        assert result["evaluationId"] == "eval-123"
        assert result["severityCounts"]["critical"] == 1

        stored_status = await store.get_evaluation_status("eval-123")
        assert stored_status["terminal"] is True
        assert stored_status["exitState"] == "budget_breach"

        stored_result = await store.get_evaluation_result("eval-123")
        assert stored_result["status"] == "completed"
        assert stored_result["summary"]["target_url"] == "https://example.com"

        store.duck_conn.tables["evaluations"][0]["artifacts_json"] = None
        artifacts = await store.get_evaluation_artifacts("eval-123", base_url="https://example.com")
        assert len(artifacts) == 2
        assert artifacts[0]["mediaType"] == "application/json"

        store.duck_conn.tables["evaluations"][0]["artifacts_json"] = "[]"
        assert await store.get_evaluation_artifacts("eval-123") == []
    finally:
        store.close()


@pytest.mark.asyncio
async def test_ontology_process_item_and_health_failure(tmp_path, monkeypatch):
    monkeypatch.setattr(ontology, "DUCKDB_AVAILABLE", False)
    monkeypatch.setattr(ontology, "LANCEDB_AVAILABLE", False)

    store = OntologyStore(root_dir=str(tmp_path / "process"), vector_dimensions=8)
    try:
        with pytest.raises(ValueError, match="Unknown persistence item kind"):
            store._process_persistence_item({"kind": "bogus"})

        monkeypatch.setattr(store, "_duck_execute", lambda *args, **kwargs: (_ for _ in ()).throw(RuntimeError("no db")))
        assert store.health()["duckDbReady"] is False
    finally:
        store.close()


@pytest.mark.asyncio
async def test_ontology_artifact_queue_and_close_paths(tmp_path, monkeypatch):
    monkeypatch.setattr(ontology, "DUCKDB_AVAILABLE", False)
    monkeypatch.setattr(ontology, "LANCEDB_AVAILABLE", False)

    store = OntologyStore(root_dir=str(tmp_path / "artifacts"), vector_dimensions=8)
    try:
        await store.create_evaluation(
            {
                "target": "https://example.com",
                "profile": "seo",
                "outputFormats": ["json"],
            },
            evaluation_id="eval-artifacts",
            accepted_at="2026-05-27T00:00:00Z",
        )

        assert await store.get_evaluation_artifacts("eval-artifacts") == []

        store._drain_persistence_queue_sync = lambda: None
        store._enqueue_persistence_item_sync = lambda item: None
        store._persistence_worker = type(
            "Worker",
            (),
            {
                "is_alive": lambda self: True,
                "join": lambda self, timeout=5: None,
            },
        )()
        store._persistence_queue.join = lambda: None
        store.duck_conn.close = lambda: (_ for _ in ()).throw(RuntimeError("close failed"))

        store.close()
    finally:
        store.duck_conn.close = lambda: None

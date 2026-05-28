from __future__ import annotations

import json

import pytest

import utils.ontology as ontology
import utils.recon as recon
from utils.ontology import OntologyStore
from utils.recon import ReconRecommendation


@pytest.mark.asyncio
async def test_evaluation_lifecycle_and_artifacts_are_persisted(tmp_path, monkeypatch):
    monkeypatch.setattr(ontology, "DUCKDB_AVAILABLE", False)
    monkeypatch.setattr(ontology, "LANCEDB_AVAILABLE", False)

    store = OntologyStore(root_dir=str(tmp_path / "service-store"), vector_dimensions=8)

    try:
        create_response = await store.create_evaluation(
            {
                "target": "https://example.com",
                "profile": "default",
                "outputFormats": ["both", "json", "llm", "geo-xml"],
                "maxDepth": 2,
                "maxUrls": 20,
                "failOnCritical": True,
                "budgetGate": False,
            },
            evaluation_id="eval-123",
            accepted_at="2026-05-27T00:00:00Z",
        )

        assert create_response == {
            "evaluationId": "eval-123",
            "status": "queued",
            "acceptedAt": "2026-05-27T00:00:00Z",
        }

        initial_status = await store.get_evaluation_status("eval-123")
        assert initial_status["status"] == "queued"
        assert initial_status["terminal"] is False
        assert initial_status["progressPercent"] == 0

        running_status = await store.update_evaluation_status(
            "eval-123",
            status="running",
            stage="crawl",
            progress_percent=35,
            message="Crawling target pages",
            started_at="2026-05-27T00:00:30Z",
        )
        assert running_status["status"] == "running"
        assert running_status["stage"] == "crawl"
        assert running_status["progressPercent"] == 35
        assert running_status["message"] == "Crawling target pages"

        report = {
            "targetUrl": "https://example.com",
            "domains": [
                {
                    "name": "Technical SEO",
                    "score": 8.8,
                    "issues": [
                        {
                            "id": "SEO-1",
                            "severity": "warning",
                            "message": "Missing meta description",
                            "location": "head",
                            "remedy": "Add a meta description tag.",
                        }
                    ],
                    "metadata": {"source": "unit-test"},
                }
            ],
        }

        result = await store.complete_evaluation(
            "eval-123",
            report,
            base_url="http://127.0.0.1:8000",
            completed_at="2026-05-27T00:01:00Z",
        )

        assert result["evaluationId"] == "eval-123"
        assert result["status"] == "completed"
        assert result["summary"]["target_url"] == "https://example.com"
        assert result["severityCounts"] == {"warning": 1}
        assert result["findings"][0]["ruleId"] == "SEO-1"
        assert result["findings"][0]["status"] == "open"
        assert result["startedAt"] == "2026-05-27T00:00:30Z"
        assert result["completedAt"] == "2026-05-27T00:01:00Z"

        completed_status = await store.get_evaluation_status("eval-123")
        assert completed_status["status"] == "completed"
        assert completed_status["terminal"] is True
        assert completed_status["exitState"] == "success"
        assert completed_status["stage"] == "completed"

        stored_result = await store.get_evaluation_result("eval-123")
        assert stored_result == result

        artifacts = await store.get_evaluation_artifacts("eval-123", base_url="http://127.0.0.1:8000")
        assert [artifact["name"] for artifact in artifacts] == [
            "report.json",
            "report.html",
            "report.md",
            "report.xml",
        ]
        assert all(artifact["downloadUrl"].startswith("http://127.0.0.1:8000/evaluations/eval-123/") for artifact in artifacts)
        assert artifacts[0]["mediaType"] == "application/json"
        assert artifacts[1]["mediaType"] == "text/html"
        assert artifacts[2]["mediaType"] == "text/markdown"
        assert artifacts[3]["mediaType"] == "application/xml"

        evaluation_rows = store.duck_conn.tables["evaluations"]
        assert len(evaluation_rows) == 1
        assert json.loads(evaluation_rows[0]["artifacts_json"])[0]["name"] == "report.json"
        assert evaluation_rows[0]["terminal"] is True
    finally:
        store.close()


@pytest.mark.asyncio
async def test_recon_service_response_matches_contract_shape(monkeypatch):
    recommendation = ReconRecommendation(
        url="https://example.com",
        posture="browser",
        recommended_engine="stealth",
        confidence=0.91,
        evidence=["cloudflare", "captcha"],
        signals=["cloudflare"],
        auto_select_allowed=False,
    )

    payload = recon.build_recon_response("https://example.com", recommendation)
    assert payload == {
        "target": "https://example.com",
        "recommendation": "stealth",
        "posture": "browser",
        "confidence": 0.91,
        "evidence": ["cloudflare", "captcha"],
        "evidenceSummary": "cloudflare, captcha",
        "signals": ["cloudflare"],
        "autoSelectAllowed": False,
    }

    class _FakeAdvisor:
        async def inspect(self, url, client=None):
            return recommendation

    monkeypatch.setattr(recon, "ReconAdvisor", lambda: _FakeAdvisor())

    inspected = await recon.inspect_recon("https://example.com")
    assert inspected == payload


@pytest.mark.asyncio
async def test_ontology_service_edge_paths(tmp_path, monkeypatch):
    monkeypatch.setattr(ontology, "DUCKDB_AVAILABLE", False)
    monkeypatch.setattr(ontology, "LANCEDB_AVAILABLE", False)

    store = OntologyStore(root_dir=str(tmp_path / "service-store"), vector_dimensions=8)

    try:
        assert store._normalize_output_formats(["both", "json", "llm", "geo-xml"]) == [
            "json",
            "html",
            "llm",
            "geo-xml",
        ]

        with pytest.raises(ValueError, match="At least one supported output format is required"):
            store._normalize_output_formats([" ", "\t"])

        with pytest.raises(ValueError, match="Evaluation target is required"):
            await store.create_evaluation({"profile": "default", "outputFormats": ["json"]})

        with pytest.raises(ValueError, match="Evaluation profile is required"):
            await store.create_evaluation({"target": "https://example.com", "outputFormats": ["json"]})

        with pytest.raises(ValueError, match="At least one output format is required"):
            await store.create_evaluation(
                {
                    "target": "https://example.com",
                    "profile": "default",
                    "outputFormats": [],
                }
            )

        await store.create_evaluation(
            {
                "target": "https://example.com",
                "profile": "default",
                "outputFormats": ["both"],
                "maxDepth": 0,
                "maxUrls": 0,
                "failOnCritical": False,
                "budgetGate": False,
            },
            evaluation_id="eval-edge",
            accepted_at="2026-05-27T00:00:00Z",
        )

        running = await store.update_evaluation_status("eval-edge", status="running")
        assert running["status"] == "running"
        assert running["stage"] == "queued"
        assert store._load_evaluation_row("eval-edge")["started_at"] is not None

        with pytest.raises(ValueError, match="Missing terminal result for evaluation"):
            await store.get_evaluation_result("eval-edge")

        assert await store.get_evaluation_artifacts("eval-edge") == []

        with pytest.raises(ValueError, match="Unknown persistence item kind"):
            store._process_persistence_item({"kind": "bogus"})

        health = store.health()
        assert health["duckDbReady"] is True
        assert health["lanceDbReady"] is False

        store.vector_store.insert(
            [
                {
                    "id": "run:edge",
                    "kind": "run",
                    "label": "https://example.com",
                    "runId": "edge",
                    "text": "edge search row",
                    "url": "https://example.com",
                    "score": 1.0,
                    "metadata": json.dumps({"source": "edge"}),
                    "vector": [0.0] * 8,
                }
            ]
        )
        results = store.search("edge search row", limit=1)
        assert results[0]["metadata"] == {"source": "edge"}
    finally:
        store.close()


@pytest.mark.asyncio
async def test_ontology_service_exit_state_variants(tmp_path, monkeypatch):
    monkeypatch.setattr(ontology, "DUCKDB_AVAILABLE", False)
    monkeypatch.setattr(ontology, "LANCEDB_AVAILABLE", False)

    store = OntologyStore(root_dir=str(tmp_path / "service-store"), vector_dimensions=8)

    try:
        budget_request = {
            "target": "https://example.com/budget",
            "profile": "default",
            "outputFormats": ["json"],
            "maxDepth": 1,
            "maxUrls": 5,
            "failOnCritical": False,
            "budgetGate": True,
        }
        await store.create_evaluation(
            budget_request,
            evaluation_id="eval-budget",
            accepted_at="2026-05-27T00:00:00Z",
        )
        budget_result = await store.complete_evaluation(
            "eval-budget",
            {
                "targetUrl": "https://example.com/budget",
                "average_score": 7.5,
                "domains": [
                    {
                        "name": "Technical SEO",
                        "score": 7.5,
                        "issues": [],
                    }
                ],
            },
        )
        assert budget_result["status"] == "completed"
        assert (await store.get_evaluation_status("eval-budget"))["exitState"] == "budget_breach"
        assert (await store.get_evaluation_artifacts("eval-budget"))[0]["name"] == "report.json"

        failure_request = {
            "target": "https://example.com/failure",
            "profile": "default",
            "outputFormats": ["json"],
            "maxDepth": 1,
            "maxUrls": 5,
            "failOnCritical": True,
            "budgetGate": False,
        }
        await store.create_evaluation(
            failure_request,
            evaluation_id="eval-failure",
            accepted_at="2026-05-27T00:01:00Z",
        )
        failure_result = await store.complete_evaluation(
            "eval-failure",
            {
                "targetUrl": "https://example.com/failure",
                "average_score": 9.0,
                "domains": [
                    {
                        "name": "Technical SEO",
                        "score": 4.0,
                        "issues": [
                            {
                                "id": "SEO-CRIT-1",
                                "severity": "critical",
                                "message": "Critical issue",
                                "location": "head",
                                "remedy": "Fix it",
                            }
                        ],
                    }
                ],
            },
        )
        assert failure_result["severityCounts"] == {"critical": 1}
        assert (await store.get_evaluation_status("eval-failure"))["exitState"] == "failure"
        assert (await store.get_evaluation_artifacts("eval-failure"))[0]["downloadUrl"].endswith(
            "/evaluations/eval-failure/artifacts/report.json"
        )
    finally:
        store.close()


@pytest.mark.asyncio
async def test_ontology_status_updates_and_artifact_generation(tmp_path, monkeypatch):
    monkeypatch.setattr(ontology, "DUCKDB_AVAILABLE", False)
    monkeypatch.setattr(ontology, "LANCEDB_AVAILABLE", False)

    store = OntologyStore(root_dir=str(tmp_path / "service-store"), vector_dimensions=8)

    try:
        await store.create_evaluation(
            {
                "target": "https://example.com/status",
                "profile": "default",
                "outputFormats": ["both"],
                "maxDepth": 1,
                "maxUrls": 5,
                "failOnCritical": False,
                "budgetGate": False,
            },
            evaluation_id="eval-status",
            accepted_at="2026-05-27T00:02:00Z",
        )

        status = await store.update_evaluation_status(
            "eval-status",
            status="completed",
            terminal=True,
            progress_percent=150,
            message="Evaluation finished",
            exit_state="success",
        )
        assert status["terminal"] is True
        assert status["progressPercent"] == 100
        assert status["message"] == "Evaluation finished"

        row = store._load_evaluation_row("eval-status")
        assert row["completed_at"] is not None

        artifacts = await store.get_evaluation_artifacts("eval-status", base_url="http://127.0.0.1:8000")
        assert [artifact["name"] for artifact in artifacts] == ["report.json", "report.html"]
        assert await store.get_evaluation_artifacts("eval-status") == artifacts
    finally:
        store.close()

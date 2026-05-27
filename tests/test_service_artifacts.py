from __future__ import annotations

from modules.base import EvaluationResult, Issue

from service.artifacts import build_artifact_bundle
from service.state import ServiceState


def _sample_results() -> list[EvaluationResult]:
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
        )
    ]


def test_service_state_persists_evaluations(tmp_path):
    state = ServiceState(root_dir=str(tmp_path / "service"))
    record = state.create_evaluation({"targetUrl": "https://example.com"})
    state.mark_running(record.evaluation_id)
    state.complete_evaluation(
        record.evaluation_id,
        result={"target_url": "https://example.com", "domains": []},
        artifacts=[],
        recon={"posture": "http"},
    )

    loaded = state.get_evaluation(record.evaluation_id)
    assert loaded.status == "completed"
    assert loaded.recon == {"posture": "http"}
    assert loaded.result["target_url"] == "https://example.com"


def test_build_artifact_bundle_emits_all_expected_formats(tmp_path):
    bundle = build_artifact_bundle(
        evaluation_id="eval_123",
        target_url="https://example.com",
        results=_sample_results(),
        output_dir=str(tmp_path / "artifacts"),
    )

    names = {artifact.name for artifact in bundle.descriptors}
    assert {"report.json", "report.md", "report.xml", "report.html"} <= names
    assert (tmp_path / "artifacts" / "eval_123" / "report.json").exists()
    assert (tmp_path / "artifacts" / "eval_123" / "html" / "report.html").exists()

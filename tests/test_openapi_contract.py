import json
from pathlib import Path

from companion.catalog import SUPPORTED_OUTPUT_FORMATS, SUPPORTED_PROFILES
from contracts.backend_api import CONTRACT_DESCRIPTION, build_openapi_document


ROOT = Path(__file__).resolve().parents[1]
CONTRACT = ROOT / "contracts" / "backend-api.openapi.json"


def test_generated_contract_has_required_desktop_paths_and_schemas():
    doc = build_openapi_document()

    assert doc["openapi"] == "3.1.0"
    assert doc["info"]["description"] == CONTRACT_DESCRIPTION

    paths = doc["paths"]
    assert "/health" in paths
    assert "/capabilities" in paths
    assert "/evaluations" in paths
    assert "/evaluations/{evaluation_id}" in paths
    assert "/evaluations/{evaluation_id}/result" in paths
    assert "/evaluations/{evaluation_id}/artifacts" in paths
    assert "/recon" in paths

    schemas = doc["components"]["schemas"]
    required = {
        "HealthResponse",
        "CompatibilityResponse",
        "CapabilitiesResponse",
        "CreateEvaluationRequest",
        "CreateEvaluationResponse",
        "EvaluationStatusResponse",
        "EvaluationResultResponse",
        "ArtifactDescriptor",
        "ReconRequest",
        "ReconResponse",
        "ApiError",
    }
    assert required.issubset(set(schemas))


def test_capabilities_and_recon_examples_track_existing_backend_seams():
    doc = build_openapi_document()

    health_example = doc["paths"]["/health"]["get"]["responses"]["200"]["content"][
        "application/json"
    ]["example"]
    assert health_example["authRequired"] is False
    assert health_example["compatibility"]["minimumDesktopVersion"] == "0.1.0"

    capabilities_example = doc["paths"]["/capabilities"]["get"]["responses"]["200"][
        "content"
    ]["application/json"]["example"]
    assert capabilities_example["evaluationProfiles"] == list(SUPPORTED_PROFILES)
    assert capabilities_example["outputFormats"] == list(SUPPORTED_OUTPUT_FORMATS)
    assert capabilities_example["supportsRecon"] is True
    assert capabilities_example["supportsArtifacts"] is True

    recon_example = doc["paths"]["/recon"]["post"]["responses"]["200"]["content"][
        "application/json"
    ]["example"]
    assert recon_example["recommendation"] == "stealth"
    assert recon_example["confidence"] == 0.9
    assert "cloudflare" in recon_example["evidenceSummary"]


def test_exported_snapshot_matches_generated_contract():
    exported = json.loads(CONTRACT.read_text(encoding="utf-8"))
    assert exported == build_openapi_document()

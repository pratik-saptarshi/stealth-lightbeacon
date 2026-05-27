import json
from pathlib import Path

from utils.service_contract import build_service_contract
from contracts.backend_api import CONTRACT_DESCRIPTION, build_openapi_document


ROOT = Path(__file__).resolve().parents[1]
CONTRACT = ROOT / "contracts" / "backend-api.openapi.json"


def test_generated_contract_matches_service_contract():
    doc = build_openapi_document()

    assert doc == build_service_contract()
    assert doc["openapi"] == "3.1.0"
    assert doc["info"]["title"] == "Stealth Lightbeacon Service API"
    assert doc["info"]["description"] == CONTRACT_DESCRIPTION

    paths = doc["paths"]
    assert "/health" in paths
    assert "/capabilities" in paths
    assert "/evaluations" in paths
    assert "/evaluations/{evaluation_id}" in paths
    assert "/evaluations/{evaluation_id}/result" in paths
    assert "/evaluations/{evaluation_id}/artifacts" in paths
    assert "/recon" in paths


def test_contract_tracks_transport_surface():
    doc = build_openapi_document()

    transport = doc["x-transport"]
    assert transport["local"]["base_url"] == "http://127.0.0.1:8000"
    assert transport["cloud"]["scheme"] == "https"
    assert transport["stdin"]["adapter"] == "stdin"


def test_exported_snapshot_matches_generated_contract():
    exported = json.loads(CONTRACT.read_text(encoding="utf-8"))
    assert exported == build_openapi_document()

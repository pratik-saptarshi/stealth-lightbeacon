from companion.errors import ApiRouteError
from companion.recon_api import map_recon_response, validate_recon_request
from utils.recon import ReconRecommendation


def test_validate_recon_request_rejects_non_absolute_targets():
    try:
        validate_recon_request({"target": "example"})
    except ApiRouteError as exc:
        payload = exc.to_payload()
    else:  # pragma: no cover - defensive branch
        raise AssertionError("expected ApiRouteError")

    assert payload == {
        "code": "invalid_request",
        "message": "Recon target URL must be an absolute HTTP or HTTPS URL.",
        "status": 400,
        "details": "example",
    }


def test_map_recon_response_preserves_backend_advisory_fields():
    recommendation = ReconRecommendation(
        url="https://example.com",
        posture="browser",
        recommended_engine="stealth",
        confidence=0.9,
        evidence=["cloudflare", "status:403"],
        signals=["cloudflare"],
        auto_select_allowed=True,
    )

    payload = map_recon_response(recommendation)

    assert payload == {
        "target": "https://example.com",
        "recommendation": "stealth",
        "posture": "browser",
        "confidence": 0.9,
        "evidence": ["cloudflare", "status:403"],
        "evidenceSummary": "cloudflare, status:403",
        "signals": ["cloudflare"],
        "autoSelectAllowed": True,
    }

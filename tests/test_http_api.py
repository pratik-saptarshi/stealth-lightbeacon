from contracts.backend_api import API_VERSION, APP_VERSION, build_openapi_document
from utils.agent_card import build_agent_card

from companion.http_api import ApiRouteError, CompanionApi


BASE_URL = "http://127.0.0.1:8000"


def test_health_route_returns_contract_fields():
    api = CompanionApi(base_url=BASE_URL)

    status, payload = api.dispatch("GET", "/health")

    assert status == 200
    assert payload == {
        "status": "ok",
        "service": "stealth-lightbeacon-api",
        "apiVersion": API_VERSION,
        "appVersion": APP_VERSION,
    }


def test_capabilities_route_tracks_backend_surface():
    card = build_agent_card()
    api = CompanionApi(base_url=BASE_URL)

    status, payload = api.dispatch("GET", "/capabilities")

    assert status == 200
    assert payload == {
        "apiMode": {
            "mode": "local",
            "baseUrl": BASE_URL,
            "transport": "http",
            "apiVersion": API_VERSION,
            "supportsRemote": False,
        },
        "evaluationProfiles": list(card["audits"]),
        "outputFormats": list(card["outputs"]["formats"]),
        "supportsRecon": True,
        "supportsArtifacts": True,
    }


def test_openapi_route_serves_generated_contract():
    api = CompanionApi(base_url=BASE_URL)

    status, payload = api.dispatch("GET", "/openapi.json")

    assert status == 200
    assert payload == build_openapi_document()


def test_unknown_route_returns_structured_api_error():
    api = CompanionApi(base_url=BASE_URL)

    try:
        api.dispatch("GET", "/missing")
    except ApiRouteError as exc:
        payload = exc.to_payload()
    else:  # pragma: no cover - defensive branch
        raise AssertionError("expected ApiRouteError")

    assert payload == {
        "code": "not_found",
        "message": "Route not found.",
        "status": 404,
        "details": "/missing",
    }

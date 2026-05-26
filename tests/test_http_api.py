import json
import threading
import time
from urllib.request import urlopen

from contracts.backend_api import API_VERSION, APP_VERSION, build_openapi_document

from companion.http_api import ApiRouteError, CompanionApi, CompanionHealth, create_server
from companion.jobs import EvaluationJobManager
from companion.catalog import SUPPORTED_OUTPUT_FORMATS, SUPPORTED_PROFILES


BASE_URL = "http://127.0.0.1:8000"


def sample_request():
    return {
        "target": "https://example.com",
        "profile": "baseline",
        "outputFormats": ["json", "markdown"],
        "maxDepth": 2,
        "maxUrls": 25,
        "failOnCritical": True,
        "budgetGate": False,
    }


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


def test_health_route_reports_booting_until_startup_delay_elapses():
    api = CompanionApi(
        base_url=BASE_URL,
        health=CompanionHealth(startup_delay_ms=25),
    )

    _, booting = api.dispatch("GET", "/health")
    assert booting["status"] == "booting"

    time.sleep(0.03)

    _, healthy = api.dispatch("GET", "/health")
    assert healthy["status"] == "ok"


def test_health_route_reports_degraded_state_after_startup():
    api = CompanionApi(
        base_url=BASE_URL,
        health=CompanionHealth(degraded_reason="fixture"),
    )

    _, payload = api.dispatch("GET", "/health")

    assert payload["status"] == "degraded"


def test_capabilities_route_tracks_backend_surface():
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
        "evaluationProfiles": list(SUPPORTED_PROFILES),
        "outputFormats": list(SUPPORTED_OUTPUT_FORMATS),
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


def test_create_evaluation_route_accepts_request_and_exposes_queued_status():
    api = CompanionApi(
        base_url=BASE_URL,
        job_manager=EvaluationJobManager(auto_start=False),
    )

    status, accepted = api.dispatch("POST", "/evaluations", body=sample_request())

    assert status == 202
    assert accepted["status"] == "accepted"
    assert accepted["evaluationId"]
    assert accepted["acceptedAt"]

    status_code, evaluation_status = api.dispatch(
        "GET",
        f"/evaluations/{accepted['evaluationId']}",
    )

    assert status_code == 200
    assert evaluation_status["evaluationId"] == accepted["evaluationId"]
    assert evaluation_status["status"] == "accepted"
    assert evaluation_status["stage"] == "queued"
    assert evaluation_status["terminal"] is False


def test_create_evaluation_route_rejects_invalid_profile():
    api = CompanionApi(
        base_url=BASE_URL,
        job_manager=EvaluationJobManager(auto_start=False),
    )
    request = sample_request()
    request["profile"] = "unsupported"

    try:
        api.dispatch("POST", "/evaluations", body=request)
    except ApiRouteError as exc:
        payload = exc.to_payload()
    else:  # pragma: no cover - defensive branch
        raise AssertionError("expected ApiRouteError")

    assert payload == {
        "code": "invalid_request",
        "message": "Evaluation profile is not supported.",
        "status": 400,
        "details": "unsupported",
    }


def test_result_route_rejects_non_terminal_evaluations():
    api = CompanionApi(
        base_url=BASE_URL,
        job_manager=EvaluationJobManager(auto_start=False),
    )
    _, accepted = api.dispatch("POST", "/evaluations", body=sample_request())

    try:
        api.dispatch("GET", f"/evaluations/{accepted['evaluationId']}/result")
    except ApiRouteError as exc:
        payload = exc.to_payload()
    else:  # pragma: no cover - defensive branch
        raise AssertionError("expected ApiRouteError")

    assert payload == {
        "code": "conflict",
        "message": "Evaluation result is not ready.",
        "status": 409,
        "details": accepted["evaluationId"],
    }


def test_artifacts_route_rejects_non_terminal_evaluations():
    api = CompanionApi(
        base_url=BASE_URL,
        job_manager=EvaluationJobManager(auto_start=False),
    )
    _, accepted = api.dispatch("POST", "/evaluations", body=sample_request())

    try:
        api.dispatch("GET", f"/evaluations/{accepted['evaluationId']}/artifacts")
    except ApiRouteError as exc:
        payload = exc.to_payload()
    else:  # pragma: no cover - defensive branch
        raise AssertionError("expected ApiRouteError")

    assert payload == {
        "code": "conflict",
        "message": "Evaluation artifacts are not ready.",
        "status": 409,
        "details": accepted["evaluationId"],
    }


def test_companion_server_serves_health_on_loopback():
    server = create_server(host="127.0.0.1", port=0)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        with urlopen(f"{server.base_url}/health", timeout=1) as response:
            assert response.status == 200
            payload = json.loads(response.read().decode("utf-8"))
    finally:
        server.shutdown()
        thread.join(timeout=1)
        server.server_close()

    assert payload["status"] == "ok"
    assert payload["service"] == "stealth-lightbeacon-api"

import config


def test_build_request_headers_prefers_explicit_token(monkeypatch):
    monkeypatch.setenv("SLB_AUTH_TOKEN", "from-env")

    headers = config.build_request_headers("from-arg")

    assert headers["Authorization"] == "Bearer from-arg"
    assert headers["User-Agent"] == config.REQUEST_HEADERS["User-Agent"]


def test_build_request_headers_falls_back_to_env_token(monkeypatch):
    monkeypatch.setenv("SLB_AUTH_TOKEN", "from-env")

    headers = config.build_request_headers()

    assert headers["Authorization"] == "Bearer from-env"
    assert headers["User-Agent"] == config.REQUEST_HEADERS["User-Agent"]


def test_service_connection_defaults_pin_loopback_and_stdio_adapter():
    snapshot = config.describe_service_connection()

    assert snapshot["default_host"] == "127.0.0.1"
    assert snapshot["default_port"] == 8000
    assert snapshot["default_scheme"] == "http"
    assert snapshot["default_base_url"] == "http://127.0.0.1:8000"
    assert snapshot["remote_scheme"] == "https"
    assert snapshot["stdin_adapter"] == "stdin"

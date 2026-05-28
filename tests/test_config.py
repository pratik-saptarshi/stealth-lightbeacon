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

from main import build_runtime_settings, select_active_evaluators


def test_runtime_settings_prefer_environment_over_missing_url(monkeypatch):
    monkeypatch.setenv("SLB_TARGET_URL", "https://env.example.com")
    monkeypatch.setenv("SLB_AUTH_TOKEN", "token-123")
    monkeypatch.setenv("SLB_AUDITS", "security,performance")
    monkeypatch.setenv("SLB_FAIL_ON_CRITICAL", "1")

    settings = build_runtime_settings(url=None, audits=None, fail_on_critical=False)

    assert settings.url == "https://env.example.com"
    assert settings.auth_token == "token-123"
    assert settings.audits == ["security", "performance"]
    assert settings.fail_on_critical is True


def test_select_active_evaluators_supports_audit_subset():
    evaluators = select_active_evaluators("security,performance")
    domains = [e.domain for e in evaluators]

    assert "Drupal & Security Headers" in domains
    assert "PageSpeed & Performance" in domains
    assert "Technical SEO" not in domains


def test_select_active_evaluators_supports_aliases():
    evaluators = select_active_evaluators("drupal,aeo,geo")
    domains = {e.domain for e in evaluators}

    assert domains == {
        "Drupal & Security Headers",
        "AEO & GEO Optimization",
    }

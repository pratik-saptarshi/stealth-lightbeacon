from utils.service_contract import validate_service_contract


def test_validate_service_contract_handles_malformed_sections_gracefully():
    errors = validate_service_contract(
        {
            "openapi": "3.1.0",
            "info": ["bad", "info"],
            "servers": [
                {"url": "http://127.0.0.1:8000"},
                {"url": "https://wrong.example"},
            ],
            "paths": {},
            "x-transport": {"local": ["bad-local"]},
        }
    )

    assert "info.title drift: None" in errors
    assert "info.version drift: None" in errors
    assert "cloud server url drift: 'https://wrong.example'" in errors
    assert "local host drift: None" in errors
    assert "local port drift: None" in errors
    assert "local base url drift: None" in errors
    assert "cloud scheme drift: None" in errors
    assert "cloud auth drift: None" in errors
    assert "stdin adapter drift: None" in errors

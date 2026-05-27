from utils.service_contract import (
    CONTRACT_PATH,
    CONTRACT_ROUTE_SET,
    build_service_contract,
    load_service_contract,
    validate_service_contract,
    validate_service_contract_snapshot,
)


def test_canonical_contract_snapshot_matches_helper():
    contract = load_service_contract(CONTRACT_PATH)
    generated = build_service_contract()

    assert CONTRACT_PATH.exists()
    assert contract == generated
    assert validate_service_contract(contract) == []
    assert validate_service_contract_snapshot(CONTRACT_PATH) == []


def test_canonical_contract_pins_transport_defaults():
    contract = build_service_contract()

    assert contract["servers"][0]["url"] == "http://127.0.0.1:8000"
    assert contract["servers"][1]["url"].startswith("https://")
    assert contract["x-transport"]["local"]["host"] == "127.0.0.1"
    assert contract["x-transport"]["local"]["port"] == 8000
    assert contract["x-transport"]["stdin"]["adapter"] == "stdin"
    assert tuple(contract["paths"]) == CONTRACT_ROUTE_SET

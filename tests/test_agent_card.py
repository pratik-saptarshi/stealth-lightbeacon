from utils.agent_card import build_agent_card


def test_agent_card_has_versioned_canary_contract():
    card = build_agent_card()

    assert card["schemaVersion"] == "1"
    assert card["name"] == "stealth-lightbeacon"
    assert "audits" in card["inputs"]
    assert "llm" in card["outputs"]["formats"]
    assert "geo-xml" in card["outputs"]["formats"]
    assert card["canary"]["supported"] is True

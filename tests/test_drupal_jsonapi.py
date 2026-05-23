"""
test_drupal_jsonapi.py — Unit tests verifying exposure checks on standard Drupal REST/JSON:API gateways.
"""

import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from modules.drupal import DrupalEvaluator

@pytest.mark.asyncio
async def test_drupal_jsonapi_endpoint_exposed():
    """
    DrupalEvaluator must audit default JSON:API routers and alert if they return 200 OK user listings.
    """
    evaluator = DrupalEvaluator()
    
    # Mocking active requests:
    # 1. Probing /jsonapi returns 200 OK with valid Drupal JSON:API payload
    # 2. Probing /jsonapi/user/user returns 200 OK indicating user profile structural exposure
    
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.text = '{"data": [{"type": "user--user", "attributes": {"name": "admin"}}]}'
    mock_resp.url = "https://example.com/jsonapi/user/user"
    
    client = MagicMock()
    client.get = AsyncMock(return_value=mock_resp)
    
    with patch("utils.ssrf_guard.resolve_ips", return_value=["93.184.216.34"]):
        result = await evaluator.evaluate(html="", url="https://example.com", client=client)
        
    assert result.score < 8.0
    issues = [issue.id for issue in result.issues]
    assert "R-DRUP-API-EXPOSED" in issues
    
    exposed_issue = next(issue for issue in result.issues if issue.id == "R-DRUP-API-EXPOSED")
    assert exposed_issue.severity == "critical"
    assert "exposed JSON:API user directory" in exposed_issue.message.lower()

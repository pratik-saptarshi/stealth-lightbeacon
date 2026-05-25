from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from utils.recon import ReconAdvisor


@pytest.mark.asyncio
async def test_recon_recommends_stealth_mode_for_bot_defenses():
    client = MagicMock()
    response = MagicMock()
    response.status_code = 403
    response.headers = {"Server": "cloudflare", "X-Captcha": "present"}
    response.text = "<html><title>Just a moment...</title><body>captcha</body></html>"
    client.get = AsyncMock(return_value=response)

    with patch("httpx.AsyncClient", return_value=client):
        recommendation = await ReconAdvisor().inspect("https://example.com")

    assert recommendation.recommended_engine == "stealth"
    assert recommendation.posture == "browser"
    assert "cloudflare" in " ".join(recommendation.evidence).lower()
    assert recommendation.auto_select_allowed is True


@pytest.mark.asyncio
async def test_recon_defaults_to_http_for_benign_sites():
    client = MagicMock()
    response = MagicMock()
    response.status_code = 200
    response.headers = {"Server": "nginx"}
    response.text = "<html><body>hello</body></html>"
    client.get = AsyncMock(return_value=response)

    with patch("httpx.AsyncClient", return_value=client):
        recommendation = await ReconAdvisor().inspect("https://example.com")

    assert recommendation.recommended_engine == "http"
    assert recommendation.posture == "http"
    assert recommendation.evidence

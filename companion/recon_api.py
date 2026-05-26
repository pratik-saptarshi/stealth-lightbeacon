"""Recon request validation and contract mapping for the companion API."""

from __future__ import annotations

import asyncio
from http import HTTPStatus
from typing import Any, Dict
from urllib.parse import urlparse

from companion.errors import ApiRouteError
from utils.recon import ReconAdvisor, ReconRecommendation


def validate_recon_request(payload: Dict[str, Any]) -> str:
    target = payload.get("target")
    if not isinstance(target, str) or not target.strip():
        raise ApiRouteError(
            status=HTTPStatus.BAD_REQUEST,
            code="invalid_request",
            message="Recon target URL is required.",
        )

    normalized = target.strip()
    parsed = urlparse(normalized)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise ApiRouteError(
            status=HTTPStatus.BAD_REQUEST,
            code="invalid_request",
            message="Recon target URL must be an absolute HTTP or HTTPS URL.",
            details=normalized,
        )
    return normalized


def map_recon_response(recommendation: ReconRecommendation) -> Dict[str, Any]:
    return {
        "target": recommendation.url,
        "recommendation": recommendation.recommended_engine,
        "posture": recommendation.posture,
        "confidence": recommendation.confidence,
        "evidence": list(recommendation.evidence),
        "evidenceSummary": ", ".join(recommendation.evidence),
        "signals": list(recommendation.signals),
        "autoSelectAllowed": recommendation.auto_select_allowed,
    }


def run_recon_request(payload: Dict[str, Any]) -> Dict[str, Any]:
    target = validate_recon_request(payload)
    recommendation = asyncio.run(ReconAdvisor().inspect(target))
    return map_recon_response(recommendation)

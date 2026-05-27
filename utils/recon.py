"""Advisory anti-bot reconnaissance for choosing a scraping posture."""

from __future__ import annotations

from dataclasses import dataclass, field
import inspect
from typing import List, Optional

import httpx

import config


@dataclass(frozen=True)
class ReconRecommendation:
    url: str
    posture: str
    recommended_engine: str
    confidence: float
    evidence: List[str] = field(default_factory=list)
    signals: List[str] = field(default_factory=list)
    auto_select_allowed: bool = True


class ReconAdvisor:
    BOT_MARKERS = {
        "cloudflare": ("browser", "stealth"),
        "akamai": ("browser", "stealth"),
        "datadome": ("browser", "stealth"),
        "perimeterx": ("browser", "stealth"),
        "captcha": ("browser", "stealth"),
        "just a moment": ("browser", "stealth"),
        "verify you are human": ("browser", "stealth"),
    }

    async def inspect(self, url: str, client: Optional[httpx.AsyncClient] = None) -> ReconRecommendation:
        close_client = False
        if client is None:
            client = httpx.AsyncClient(timeout=config.REQUEST_TIMEOUT, headers=config.build_request_headers())
            close_client = True

        evidence: List[str] = []
        signals: List[str] = []
        posture = "http"
        engine = "http"
        confidence = 0.2

        try:
            response = await client.get(url, follow_redirects=True)
            header_blob = " ".join(f"{k}: {v}" for k, v in getattr(response, "headers", {}).items()).lower()
            body_blob = (getattr(response, "text", "") or "").lower()
            combined = f"{header_blob} {body_blob}"

            for marker, (marker_posture, marker_engine) in self.BOT_MARKERS.items():
                if marker in combined:
                    evidence.append(marker)
                    signals.append(marker)
                    posture = marker_posture
                    engine = marker_engine
                    confidence = 0.9
                    break

            if confidence < 0.8 and getattr(response, "status_code", 200) in {403, 429, 503}:
                evidence.append(f"status:{getattr(response, 'status_code', 0)}")
                posture = "browser"
                engine = "stealth"
                confidence = max(confidence, 0.7)
        finally:
            if close_client and hasattr(client, "aclose"):
                close_result = client.aclose()
                if inspect.isawaitable(close_result):
                    await close_result

        if not evidence:
            evidence.append("no-anti-bot-signals")

        return ReconRecommendation(
            url=url,
            posture=posture,
            recommended_engine=engine,
            confidence=confidence,
            evidence=evidence,
            signals=signals,
            auto_select_allowed=True,
        )


def build_recon_response(target: str, recommendation: ReconRecommendation) -> dict:
    evidence_summary = "No anti-bot signals detected."
    if recommendation.evidence and recommendation.evidence != ["no-anti-bot-signals"]:
        evidence_summary = ", ".join(recommendation.evidence)

    return {
        "target": target,
        "recommendation": recommendation.recommended_engine,
        "posture": recommendation.posture,
        "confidence": recommendation.confidence,
        "evidence": list(recommendation.evidence),
        "evidenceSummary": evidence_summary,
        "signals": list(recommendation.signals),
        "autoSelectAllowed": recommendation.auto_select_allowed,
    }


async def inspect_recon(target: str, client: Optional[httpx.AsyncClient] = None) -> dict:
    recommendation = await ReconAdvisor().inspect(target, client=client)
    return build_recon_response(target, recommendation)

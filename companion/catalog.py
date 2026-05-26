"""Stable evaluation profiles and format vocabulary for the companion API."""

from __future__ import annotations

from utils.agent_card import build_agent_card

ALL_AUDITS = tuple(build_agent_card()["audits"])

PROFILE_AUDITS = {
    "baseline": ("seo", "accessibility", "security", "ux"),
    "deep": ALL_AUDITS,
    "export": ("seo", "accessibility", "security", "ux", "aeo-geo"),
}

SUPPORTED_PROFILES = tuple(PROFILE_AUDITS.keys())
SUPPORTED_OUTPUT_FORMATS = ("json", "markdown", "html")


def resolve_profile_audits(profile: str) -> tuple[str, ...]:
    return PROFILE_AUDITS[profile]

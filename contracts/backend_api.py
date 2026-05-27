"""Compatibility wrapper for the canonical service contract."""

from __future__ import annotations

from copy import deepcopy
from typing import Any, Dict

from utils.service_contract import (
    CONTRACT_API_VERSION,
    build_service_contract,
)

API_VERSION = CONTRACT_API_VERSION
APP_VERSION = "1.2.2"
CONTRACT_DESCRIPTION = "Canonical contract for local and remote Stealth Lightbeacon clients."


def build_openapi_document() -> Dict[str, Any]:
    return deepcopy(build_service_contract())

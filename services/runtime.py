"""Runtime settings resolution shared by CLI and future adapters."""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import List, Optional

import config


@dataclass(frozen=True)
class RuntimeSettings:
    url: Optional[str]
    output_dir: str
    audits: List[str]
    auth_token: str
    fail_on_critical: bool


def _env_flag(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def build_runtime_settings(
    url: Optional[str],
    audits: Optional[str],
    fail_on_critical: bool,
    output_dir: Optional[str] = None,
    auth_token: Optional[str] = None,
) -> RuntimeSettings:
    resolved_url = (url or os.getenv("SLB_TARGET_URL", "")).strip() or None
    resolved_audits = (audits or os.getenv("SLB_AUDITS", "")).strip()
    resolved_auth = (auth_token or os.getenv("SLB_AUTH_TOKEN", "")).strip()
    resolved_fail = fail_on_critical or _env_flag("SLB_FAIL_ON_CRITICAL", False)
    audit_list = (
        [item.strip() for item in resolved_audits.split(",") if item.strip()]
        if resolved_audits
        else []
    )
    return RuntimeSettings(
        url=resolved_url,
        output_dir=output_dir or config.REPORT_OUTPUT_DIR,
        audits=audit_list,
        auth_token=resolved_auth,
        fail_on_critical=resolved_fail,
    )

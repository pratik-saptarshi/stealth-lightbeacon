"""Service-layer exceptions."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class AuditServiceError(Exception):
    title: str
    detail: str
    exit_code: int = 1

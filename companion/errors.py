"""Shared HTTP companion transport errors."""

from __future__ import annotations

from typing import Any, Dict


class ApiRouteError(Exception):
    """Structured transport error for HTTP responses."""

    def __init__(
        self,
        status: int,
        code: str,
        message: str,
        details: str | None = None,
    ) -> None:
        super().__init__(message)
        self.status = status
        self.code = code
        self.message = message
        self.details = details

    def to_payload(self) -> Dict[str, Any]:
        payload: Dict[str, Any] = {
            "code": self.code,
            "message": self.message,
            "status": self.status,
        }
        if self.details is not None:
            payload["details"] = self.details
        return payload

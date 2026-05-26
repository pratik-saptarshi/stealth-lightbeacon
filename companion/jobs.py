"""Evaluation submission and polling state for the desktop companion API."""

from __future__ import annotations

import asyncio
import json
import os
import threading
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Dict, List
from urllib.parse import urlparse

import config
from companion.catalog import (
    SUPPORTED_OUTPUT_FORMATS,
    SUPPORTED_PROFILES,
    resolve_profile_audits,
)
from companion.errors import ApiRouteError
from modules.base import EvaluationResult
from report.formats import build_report_payload, render_report_format
from report.generator import ReportGenerator
from services.audit_service import run_evaluation
from services.evaluators import select_active_evaluators


def _utcnow() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _env_flag(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


@dataclass(frozen=True)
class EvaluationRequest:
    target: str
    profile: str
    output_formats: tuple[str, ...]
    max_depth: int
    max_urls: int
    fail_on_critical: bool
    budget_gate: bool


@dataclass(frozen=True)
class JobExecutionOutcome:
    status: str
    exit_state: str
    message: str
    result_payload: Dict[str, Any]
    artifacts: List[Dict[str, Any]]


@dataclass
class EvaluationRecord:
    evaluation_id: str
    request: EvaluationRequest
    accepted_at: str
    output_dir: str
    status: str = "accepted"
    stage: str = "queued"
    progress_percent: int = 0
    message: str = "Evaluation accepted by backend."
    exit_state: str | None = None
    terminal: bool = False
    started_at: str | None = None
    completed_at: str | None = None
    result_payload: Dict[str, Any] | None = None
    artifacts: List[Dict[str, Any]] = field(default_factory=list)

    def to_create_response(self) -> Dict[str, Any]:
        return {
            "evaluationId": self.evaluation_id,
            "status": self.status,
            "acceptedAt": self.accepted_at,
        }

    def to_status_response(self) -> Dict[str, Any]:
        return {
            "evaluationId": self.evaluation_id,
            "status": self.status,
            "stage": self.stage,
            "progressPercent": self.progress_percent,
            "message": self.message,
            "exitState": self.exit_state,
            "terminal": self.terminal,
        }


def _validate_request(payload: Dict[str, Any]) -> EvaluationRequest:
    if not isinstance(payload, dict):
        raise ApiRouteError(
            status=400,
            code="invalid_request",
            message="Request body must be a JSON object.",
        )

    target = payload.get("target")
    if not isinstance(target, str) or not target.strip():
        raise ApiRouteError(
            status=400,
            code="invalid_request",
            message="Target URL is required.",
        )
    target = target.strip()
    parsed_target = urlparse(target)
    if parsed_target.scheme not in {"http", "https"} or not parsed_target.netloc:
        raise ApiRouteError(
            status=400,
            code="invalid_request",
            message="Target URL must be an absolute HTTP or HTTPS URL.",
            details=target,
        )

    profile = payload.get("profile")
    if not isinstance(profile, str) or not profile.strip():
        raise ApiRouteError(
            status=400,
            code="invalid_request",
            message="Evaluation profile is required.",
        )
    profile = profile.strip()
    if profile not in SUPPORTED_PROFILES:
        raise ApiRouteError(
            status=400,
            code="invalid_request",
            message="Evaluation profile is not supported.",
            details=profile,
        )

    output_formats = payload.get("outputFormats")
    if not isinstance(output_formats, list) or not output_formats:
        raise ApiRouteError(
            status=400,
            code="invalid_request",
            message="At least one output format is required.",
        )
    normalized_formats: list[str] = []
    for value in output_formats:
        if not isinstance(value, str) or not value.strip():
            raise ApiRouteError(
                status=400,
                code="invalid_request",
                message="Output formats must be non-empty strings.",
            )
        normalized = value.strip()
        if normalized not in SUPPORTED_OUTPUT_FORMATS:
            raise ApiRouteError(
                status=400,
                code="invalid_request",
                message="Output format is not supported.",
                details=normalized,
            )
        if normalized not in normalized_formats:
            normalized_formats.append(normalized)

    def require_bounded_int(name: str, minimum: int, maximum: int) -> int:
        value = payload.get(name)
        if not isinstance(value, int) or isinstance(value, bool):
            raise ApiRouteError(
                status=400,
                code="invalid_request",
                message=f"{name} must be an integer.",
            )
        if value < minimum or value > maximum:
            raise ApiRouteError(
                status=400,
                code="invalid_request",
                message=f"{name} must be between {minimum} and {maximum}.",
                details=str(value),
            )
        return value

    max_depth = require_bounded_int("maxDepth", 1, 8)
    max_urls = require_bounded_int("maxUrls", 1, 5000)

    fail_on_critical = payload.get("failOnCritical")
    if not isinstance(fail_on_critical, bool):
        raise ApiRouteError(
            status=400,
            code="invalid_request",
            message="failOnCritical must be a boolean.",
        )

    budget_gate = payload.get("budgetGate")
    if not isinstance(budget_gate, bool):
        raise ApiRouteError(
            status=400,
            code="invalid_request",
            message="budgetGate must be a boolean.",
        )

    return EvaluationRequest(
        target=target,
        profile=profile,
        output_formats=tuple(normalized_formats),
        max_depth=max_depth,
        max_urls=max_urls,
        fail_on_critical=fail_on_critical,
        budget_gate=budget_gate,
    )


def _artifact_descriptor(
    *,
    name: str,
    kind: str,
    media_type: str,
    path: Path,
) -> Dict[str, Any]:
    return {
        "name": name,
        "kind": kind,
        "mediaType": media_type,
        "downloadUrl": None,
        "path": str(path),
    }


def _write_artifacts(
    request: EvaluationRequest,
    payload: Dict[str, Any],
    results: List[EvaluationResult],
    output_dir: Path,
) -> List[Dict[str, Any]]:
    output_dir.mkdir(parents=True, exist_ok=True)
    artifacts: List[Dict[str, Any]] = []

    if "json" in request.output_formats:
        json_path = output_dir / "report.json"
        json_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        artifacts.append(
            _artifact_descriptor(
                name="normalized-report",
                kind="normalized_report",
                media_type="application/json",
                path=json_path,
            )
        )

    if "markdown" in request.output_formats:
        markdown_path = output_dir / "report.md"
        markdown_path.write_text(
            render_report_format("llm", payload),
            encoding="utf-8",
        )
        artifacts.append(
            _artifact_descriptor(
                name="markdown-report",
                kind="markdown",
                media_type="text/markdown",
                path=markdown_path,
            )
        )

    if "html" in request.output_formats:
        ReportGenerator.generate_report(request.target, results, str(output_dir))
        html_path = output_dir / "report.html"
        artifacts.append(
            _artifact_descriptor(
                name="html-report",
                kind="html",
                media_type="text/html",
                path=html_path,
            )
        )

    return artifacts


def execute_evaluation_job(
    request: EvaluationRequest,
    evaluation_id: str,
    output_dir: str,
) -> JobExecutionOutcome:
    audits = resolve_profile_audits(request.profile)
    active_evaluators = select_active_evaluators(",".join(audits))
    if not active_evaluators:
        raise ApiRouteError(
            status=400,
            code="invalid_request",
            message="No evaluators are available for the requested profile.",
            details=request.profile,
        )

    results = asyncio.run(
        run_evaluation(
            request.target,
            active_evaluators,
            allow_private=_env_flag("SLB_ALLOW_PRIVATE", False),
            crawl_depth=request.max_depth,
            max_urls=request.max_urls,
            render=False,
            http2=False,
            check_links=False,
            check_api=False,
            auth_token=os.getenv("SLB_AUTH_TOKEN", "").strip() or None,
        )
    )
    payload = build_report_payload(request.target, results)
    artifacts = _write_artifacts(request, payload, results, Path(output_dir))

    critical_found = any(
        issue.severity == config.SEVERITY_CRITICAL
        for result in results
        for issue in result.issues
    )
    if request.fail_on_critical and critical_found:
        return JobExecutionOutcome(
            status="failure",
            exit_state="failure",
            message="Critical findings detected.",
            result_payload=payload,
            artifacts=artifacts,
        )

    return JobExecutionOutcome(
        status="success",
        exit_state="success",
        message="Evaluation complete.",
        result_payload=payload,
        artifacts=artifacts,
    )


class EvaluationJobManager:
    """Thread-safe in-memory evaluation queue and status store."""

    def __init__(
        self,
        *,
        output_root: str | None = None,
        executor: Callable[[EvaluationRequest, str, str], JobExecutionOutcome] | None = None,
        auto_start: bool = True,
    ) -> None:
        self._lock = threading.Lock()
        self._records: Dict[str, EvaluationRecord] = {}
        self._output_root = Path(
            output_root or os.getenv("SLB_COMPANION_OUTPUT_ROOT", "reports/companion")
        )
        self._executor = executor or execute_evaluation_job
        self._auto_start = auto_start

    def submit(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        request = _validate_request(payload)
        evaluation_id = f"eval-{uuid.uuid4().hex[:12]}"
        record = EvaluationRecord(
            evaluation_id=evaluation_id,
            request=request,
            accepted_at=_utcnow(),
            output_dir=str(self._output_root / evaluation_id),
        )
        with self._lock:
            self._records[evaluation_id] = record

        accepted_response = record.to_create_response()
        if self._auto_start:
            worker = threading.Thread(
                target=self._run_job,
                args=(evaluation_id,),
                daemon=True,
            )
            worker.start()

        return accepted_response

    def get_status(self, evaluation_id: str) -> Dict[str, Any]:
        return self._get_record(evaluation_id).to_status_response()

    def _get_record(self, evaluation_id: str) -> EvaluationRecord:
        if not evaluation_id.strip():
            raise ApiRouteError(
                status=400,
                code="invalid_request",
                message="Evaluation ID is required.",
            )
        with self._lock:
            record = self._records.get(evaluation_id)
        if record is None:
            raise ApiRouteError(
                status=404,
                code="not_found",
                message="Evaluation was not found.",
                details=evaluation_id,
            )
        return record

    def _update_record(self, evaluation_id: str, **changes: Any) -> None:
        with self._lock:
            record = self._records[evaluation_id]
            for key, value in changes.items():
                setattr(record, key, value)

    def _run_job(self, evaluation_id: str) -> None:
        record = self._get_record(evaluation_id)
        self._update_record(
            evaluation_id,
            status="running",
            stage="evaluating",
            progress_percent=20,
            message="Evaluation is running.",
            started_at=_utcnow(),
        )
        try:
            outcome = self._executor(
                record.request,
                evaluation_id,
                record.output_dir,
            )
        except Exception as exc:
            self._update_record(
                evaluation_id,
                status="failure",
                stage="completed",
                progress_percent=100,
                message=str(exc),
                exit_state="failure",
                terminal=True,
                completed_at=_utcnow(),
            )
            return

        self._update_record(
            evaluation_id,
            status=outcome.status,
            stage="completed",
            progress_percent=100,
            message=outcome.message,
            exit_state=outcome.exit_state,
            terminal=True,
            completed_at=_utcnow(),
            result_payload=outcome.result_payload,
            artifacts=outcome.artifacts,
        )


DEFAULT_JOB_MANAGER = EvaluationJobManager()

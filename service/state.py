from __future__ import annotations

import json
import threading
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class ArtifactDescriptor:
    id: str
    name: str
    format: str
    media_type: str
    path: str
    size_bytes: int
    content: str = ""


@dataclass
class EvaluationRecord:
    evaluation_id: str
    target_url: str
    request: Dict[str, Any]
    status: str = "queued"
    created_at: str = field(default_factory=_now)
    updated_at: str = field(default_factory=_now)
    completed_at: Optional[str] = None
    result: Optional[Dict[str, Any]] = None
    error: Optional[Dict[str, Any]] = None
    recon: Optional[Dict[str, Any]] = None
    artifacts: List[ArtifactDescriptor] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        payload = asdict(self)
        payload["artifacts"] = [asdict(item) for item in self.artifacts]
        return payload


class ServiceState:
    def __init__(self, root_dir: str = ".data/service") -> None:
        self.root_dir = Path(root_dir)
        self.state_dir = self.root_dir / "evaluations"
        self.state_dir.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()
        self._cache: Dict[str, EvaluationRecord] = {}

    def _path_for(self, evaluation_id: str) -> Path:
        return self.state_dir / f"{evaluation_id}.json"

    def _save(self, record: EvaluationRecord) -> None:
        self._cache[record.evaluation_id] = record
        self._path_for(record.evaluation_id).write_text(
            json.dumps(record.to_dict(), indent=2, sort_keys=True),
            encoding="utf-8",
        )

    def _load(self, evaluation_id: str) -> EvaluationRecord:
        cached = self._cache.get(evaluation_id)
        if cached is not None:
            return cached
        path = self._path_for(evaluation_id)
        if not path.exists():
            raise KeyError(evaluation_id)
        raw = json.loads(path.read_text(encoding="utf-8"))
        record = EvaluationRecord(
            evaluation_id=raw["evaluation_id"],
            target_url=raw["target_url"],
            request=raw.get("request", {}),
            status=raw.get("status", "queued"),
            created_at=raw.get("created_at", _now()),
            updated_at=raw.get("updated_at", _now()),
            completed_at=raw.get("completed_at"),
            result=raw.get("result"),
            error=raw.get("error"),
            recon=raw.get("recon"),
            artifacts=[ArtifactDescriptor(**item) for item in raw.get("artifacts", [])],
        )
        self._cache[evaluation_id] = record
        return record

    def create_evaluation(self, request: Dict[str, Any]) -> EvaluationRecord:
        target_url = str(request.get("targetUrl") or request.get("target_url") or "").strip()
        evaluation_id = str(request.get("evaluationId") or request.get("evaluation_id") or f"eval_{uuid.uuid4().hex[:12]}")
        record = EvaluationRecord(
            evaluation_id=evaluation_id,
            target_url=target_url,
            request=dict(request),
        )
        with self._lock:
            self._save(record)
        return record

    def list_evaluations(self) -> List[EvaluationRecord]:
        with self._lock:
            ids = set(self._cache)
            ids.update(path.stem for path in self.state_dir.glob("*.json"))
            return [self.get_evaluation(evaluation_id) for evaluation_id in sorted(ids)]

    def get_evaluation(self, evaluation_id: str) -> EvaluationRecord:
        with self._lock:
            return self._load(evaluation_id)

    def patch_evaluation(self, evaluation_id: str, **updates: Any) -> EvaluationRecord:
        with self._lock:
            record = self._load(evaluation_id)
            for key, value in updates.items():
                setattr(record, key, value)
            record.updated_at = _now()
            self._save(record)
            return record

    def mark_running(self, evaluation_id: str) -> EvaluationRecord:
        return self.patch_evaluation(evaluation_id, status="running")

    def complete_evaluation(
        self,
        evaluation_id: str,
        *,
        result: Dict[str, Any],
        artifacts: Iterable[ArtifactDescriptor],
        recon: Optional[Dict[str, Any]] = None,
    ) -> EvaluationRecord:
        return self.patch_evaluation(
            evaluation_id,
            status="completed",
            completed_at=_now(),
            result=result,
            recon=recon,
            artifacts=list(artifacts),
            error=None,
        )

    def fail_evaluation(self, evaluation_id: str, error: str) -> EvaluationRecord:
        return self.patch_evaluation(
            evaluation_id,
            status="failed",
            completed_at=_now(),
            error={"message": error},
        )

    def attach_recon(self, evaluation_id: str, recon: Dict[str, Any]) -> EvaluationRecord:
        return self.patch_evaluation(evaluation_id, recon=recon)

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

from modules.base import EvaluationResult
from report.formats import build_report_payload, render_report_format
from report.generator import ReportGenerator

from .state import ArtifactDescriptor


@dataclass(frozen=True)
class ArtifactBundle:
    descriptors: list[ArtifactDescriptor]
    root_dir: str


def _artifact_media_type(format_name: str) -> str:
    return {
        "json": "application/json",
        "llm": "text/markdown",
        "geo-xml": "application/xml",
        "html": "text/html",
    }.get(format_name, "application/octet-stream")


def _artifact_name(format_name: str) -> str:
    return {
        "json": "report.json",
        "llm": "report.md",
        "geo-xml": "report.xml",
        "html": "report.html",
    }.get(format_name, f"report.{format_name}")


def build_artifact_bundle(
    *,
    evaluation_id: str,
    target_url: str,
    results: Iterable[EvaluationResult],
    output_dir: str,
) -> ArtifactBundle:
    results = list(results)
    payload = build_report_payload(target_url, results)
    root = Path(output_dir) / evaluation_id
    root.mkdir(parents=True, exist_ok=True)
    descriptors: list[ArtifactDescriptor] = []

    for format_name in ("json", "llm", "geo-xml"):
        content = render_report_format(format_name, payload)
        path = root / _artifact_name(format_name)
        path.write_text(content, encoding="utf-8")
        descriptors.append(
            ArtifactDescriptor(
                id=f"{evaluation_id}:{format_name}",
                name=path.name,
                format=format_name,
                media_type=_artifact_media_type(format_name),
                path=str(path),
                size_bytes=len(content.encode("utf-8")),
                content=content,
            )
        )

    html_dir = root / "html"
    ReportGenerator.generate_report(target_url, results, str(html_dir))
    html_path = html_dir / "report.html"
    html_content = html_path.read_text(encoding="utf-8")
    descriptors.append(
        ArtifactDescriptor(
            id=f"{evaluation_id}:html",
            name="report.html",
            format="html",
            media_type=_artifact_media_type("html"),
            path=str(html_path),
            size_bytes=len(html_content.encode("utf-8")),
            content=html_content,
        )
    )

    return ArtifactBundle(descriptors=descriptors, root_dir=str(root))

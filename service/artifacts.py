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
        "pdf": "application/pdf",
    }.get(format_name, "application/octet-stream")


def _artifact_name(format_name: str) -> str:
    return {
        "json": "report.json",
        "llm": "report.md",
        "geo-xml": "report.xml",
        "html": "report.html",
        "pdf": "report.pdf",
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

    html_dir = root / "html"
    report_paths = ReportGenerator.generate_report(target_url, results, str(html_dir))
    report_dir = Path(report_paths["report_dir"])
    report_stem = report_paths["report_stem"]
    descriptors: list[ArtifactDescriptor] = []

    for format_name, extension in (("json", "json"), ("llm", "md"), ("geo-xml", "xml")):
        content = render_report_format(format_name, payload)
        path = report_dir / f"{report_stem}.{extension}"
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

    html_path = Path(report_paths["html_path"])
    html_content = html_path.read_text(encoding="utf-8")
    descriptors.append(
        ArtifactDescriptor(
            id=f"{evaluation_id}:html",
            name=html_path.name,
            format="html",
            media_type=_artifact_media_type("html"),
            path=str(html_path),
            size_bytes=len(html_content.encode("utf-8")),
            content=html_content,
        )
    )

    pdf_path = Path(report_paths["pdf_path"])
    descriptors.append(
        ArtifactDescriptor(
            id=f"{evaluation_id}:pdf",
            name=pdf_path.name,
            format="pdf",
            media_type=_artifact_media_type("pdf"),
            path=str(pdf_path),
            size_bytes=pdf_path.stat().st_size,
            content="",
        )
    )

    return ArtifactBundle(descriptors=descriptors, root_dir=str(root))

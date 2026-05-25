"""
formats.py - Shared normalized audit payload and renderers.
"""

from __future__ import annotations

import json
from dataclasses import asdict
from typing import Any, Dict, Iterable, List
from xml.etree import ElementTree as ET

from modules.base import EvaluationResult, Issue


def _issue_to_dict(issue: Issue) -> Dict[str, Any]:
    return {
        "id": issue.id,
        "severity": issue.severity,
        "message": issue.message,
        "location": issue.location,
        "remedy": issue.remedy,
    }


def _domain_to_dict(result: EvaluationResult) -> Dict[str, Any]:
    return {
        "name": result.domain,
        "score": result.score,
        "issues": [_issue_to_dict(issue) for issue in result.issues],
        "metadata": dict(result.metadata),
    }


def build_report_payload(target_url: str, results: Iterable[EvaluationResult]) -> Dict[str, Any]:
    results = list(results)
    payload = {
        "target_url": target_url,
        "average_score": round(sum(r.score for r in results) / len(results), 2) if results else 0.0,
        "total_issues": sum(len(r.issues) for r in results),
        "domains": [_domain_to_dict(result) for result in results],
    }
    return payload


def _render_markdown(payload: Dict[str, Any]) -> str:
    lines = [
        "# Stealth Lightbeacon Audit Report",
        "",
        f"- Target: `{payload['target_url']}`",
        f"- Average score: `{payload['average_score']:.2f}`",
        f"- Total issues: `{payload['total_issues']}`",
        "",
    ]
    for domain in payload["domains"]:
        lines.extend(
            [
                f"## {domain['name']}",
                f"- Score: `{domain['score']:.1f}`",
                f"- Issues: `{len(domain['issues'])}`",
            ]
        )
        if domain["metadata"]:
            lines.append(f"- Metadata: `{json.dumps(domain['metadata'], sort_keys=True)}`")
        if domain["issues"]:
            lines.append("- Findings:")
            for issue in domain["issues"]:
                lines.append(f"  - `{issue['id']}` [{issue['severity']}] {issue['message']}")
                if issue.get("location"):
                    lines.append(f"    - Location: `{issue['location']}`")
                if issue.get("remedy"):
                    lines.append(f"    - Remedy: {issue['remedy']}")
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def _render_geo_xml(payload: Dict[str, Any]) -> str:
    root = ET.Element("geoAuditReport", version="1")
    ET.SubElement(root, "targetUrl").text = payload["target_url"]
    ET.SubElement(root, "averageScore").text = f"{payload['average_score']:.2f}"
    ET.SubElement(root, "totalIssues").text = str(payload["total_issues"])
    domains_el = ET.SubElement(root, "domains")
    for domain in payload["domains"]:
        domain_el = ET.SubElement(domains_el, "domain")
        ET.SubElement(domain_el, "name").text = domain["name"]
        ET.SubElement(domain_el, "score").text = f"{domain['score']:.1f}"
        ET.SubElement(domain_el, "issueCount").text = str(len(domain["issues"]))
        metadata_el = ET.SubElement(domain_el, "metadata")
        for key, value in sorted(domain["metadata"].items()):
            item = ET.SubElement(metadata_el, "item", key=str(key))
            item.text = json.dumps(value, sort_keys=True) if isinstance(value, (dict, list)) else str(value)
        issues_el = ET.SubElement(domain_el, "issues")
        for issue in domain["issues"]:
            issue_el = ET.SubElement(issues_el, "issue", id=issue["id"], severity=issue["severity"])
            ET.SubElement(issue_el, "message").text = issue["message"]
            ET.SubElement(issue_el, "location").text = issue.get("location", "")
            ET.SubElement(issue_el, "remedy").text = issue.get("remedy", "")
    return ET.tostring(root, encoding="unicode")


def render_report_format(report_format: str, payload: Dict[str, Any]) -> str:
    normalized = report_format.lower().strip()
    if normalized == "json":
        return json.dumps(payload, indent=2)
    if normalized == "llm":
        return _render_markdown(payload)
    if normalized == "geo-xml":
        return _render_geo_xml(payload)
    raise ValueError(f"Unsupported report format: {report_format}")


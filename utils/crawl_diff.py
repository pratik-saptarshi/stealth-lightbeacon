"""Historical crawl diff helpers."""

from __future__ import annotations

import json
from typing import Any, Dict, List

from report.formats import normalize_report_payload


def _domain_name(domain: Dict[str, Any]) -> str:
    return domain.get("domain") or domain.get("name") or ""


def _issue_ids(domain: Dict[str, Any]) -> set[str]:
    return {issue.get("id") for issue in domain.get("issues", []) if issue.get("id")}


def compare_audit_reports(previous: Dict[str, Any], current: Dict[str, Any]) -> Dict[str, Any]:
    previous = normalize_report_payload(previous)
    current = normalize_report_payload(current)
    previous_domains = { _domain_name(domain): domain for domain in previous.get("domains", []) }
    current_domains = { _domain_name(domain): domain for domain in current.get("domains", []) }
    all_domain_names = sorted(set(previous_domains) | set(current_domains))

    added_domains = sorted(set(current_domains) - set(previous_domains))
    removed_domains = sorted(set(previous_domains) - set(current_domains))
    regressions: List[str] = []
    improvements: List[str] = []
    new_issue_ids: List[str] = []
    resolved_issue_ids: List[str] = []
    def _avg(report: Dict[str, Any]) -> float:
        if "average_score" in report:
            return float(report.get("average_score", 0.0))
        domains = report.get("domains", [])
        if not domains:
            return 0.0
        return sum(float(domain.get("score", 0.0)) for domain in domains) / len(domains)

    score_delta = _avg(current) - _avg(previous)

    for domain_name in all_domain_names:
        before = previous_domains.get(domain_name, {})
        after = current_domains.get(domain_name, {})
        before_score = float(before.get("score", 0.0))
        after_score = float(after.get("score", 0.0))
        if after_score < before_score:
            regressions.append(domain_name)
        elif after_score > before_score:
            improvements.append(domain_name)

        before_ids = _issue_ids(before)
        after_ids = _issue_ids(after)
        new_issue_ids.extend(sorted(after_ids - before_ids))
        resolved_issue_ids.extend(sorted(before_ids - after_ids))

    return {
        "score_delta": score_delta,
        "added_domains": added_domains,
        "removed_domains": removed_domains,
        "regressions": sorted(set(regressions)),
        "improvements": sorted(set(improvements)),
        "new_issue_ids": sorted(set(new_issue_ids)),
        "resolved_issue_ids": sorted(set(resolved_issue_ids)),
    }


async def compare_audit_runs(store: Any, previous_run_id: str, current_run_id: str) -> Dict[str, Any]:
    async def _load_report(run_id: str) -> Dict[str, Any]:
        if hasattr(store, "get_run_report"):
            return await store.get_run_report(run_id)
        row = store.duck_conn.execute("SELECT report_json FROM audit_runs WHERE run_id = ?", [run_id]).fetchone()
        if not row or row[0] is None:
            raise ValueError(f"Missing audit run: {run_id}")
        raw = row[0]
        return json.loads(raw) if isinstance(raw, str) else raw

    previous = await _load_report(previous_run_id)
    current = await _load_report(current_run_id)
    return compare_audit_reports(previous, current)

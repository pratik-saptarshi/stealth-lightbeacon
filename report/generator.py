"""
generator.py - Executive HTML and PDF report generator.
"""

from __future__ import annotations

import os
import json
import re
import subprocess
import textwrap
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, List
from urllib.parse import urlparse

import config
from jinja2 import Environment, select_autoescape

from modules.base import EvaluationResult
from report.formats import build_report_payload


_SEVERITY_ORDER = {
    "critical": 0,
    "warning": 1,
    "info": 2,
    "pass": 3,
}


class ReportGenerator:
    """
    Builds an executive HTML report and a print-ready PDF from audit results.
    """

    HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Stealth Lightbeacon Executive Audit Report</title>
  <style>
    :root {
      color-scheme: dark;
      --bg: #0b1020;
      --bg-soft: rgba(18, 24, 43, 0.9);
      --bg-panel: rgba(255, 255, 255, 0.06);
      --bg-panel-strong: rgba(255, 255, 255, 0.1);
      --border: rgba(255, 255, 255, 0.12);
      --text: #e8eefc;
      --muted: #9ba8c7;
      --accent: #77b7ff;
      --accent-2: #7cdbca;
      --critical: #ff6b7a;
      --warning: #f4b860;
      --info: #7db3ff;
      --pass: #4cd38a;
      --mono: "SFMono-Regular", Consolas, "Liberation Mono", Menlo, monospace;
      --sans: Inter, "Segoe UI", system-ui, -apple-system, BlinkMacSystemFont, sans-serif;
    }

    * { box-sizing: border-box; }
    html, body { margin: 0; padding: 0; }
    body {
      font-family: var(--sans);
      background:
        radial-gradient(circle at top left, rgba(119, 183, 255, 0.18), transparent 30%),
        radial-gradient(circle at top right, rgba(124, 219, 202, 0.12), transparent 24%),
        linear-gradient(180deg, #090d17 0%, #0b1020 100%);
      color: var(--text);
      line-height: 1.5;
    }

    .shell {
      position: relative;
      max-width: 1280px;
      margin: 0 auto;
      padding: 28px 20px 48px;
    }

    .shell::before,
    .shell::after {
      content: "";
      position: fixed;
      inset: auto;
      width: 360px;
      height: 360px;
      border-radius: 50%;
      filter: blur(80px);
      opacity: 0.18;
      pointer-events: none;
      z-index: -1;
    }

    .shell::before { top: -120px; left: -100px; background: var(--accent); }
    .shell::after { bottom: -120px; right: -120px; background: var(--accent-2); }

    .banner {
      background: linear-gradient(180deg, rgba(255,255,255,0.09), rgba(255,255,255,0.05));
      border: 1px solid var(--border);
      border-radius: 24px;
      padding: 28px;
      box-shadow: 0 24px 80px rgba(0,0,0,0.28);
      margin-bottom: 22px;
    }

    .banner-top {
      display: flex;
      justify-content: space-between;
      gap: 20px;
      align-items: flex-start;
      margin-bottom: 20px;
    }

    .eyebrow {
      margin: 0 0 8px;
      text-transform: uppercase;
      letter-spacing: 0.14em;
      font-size: 0.78rem;
      color: var(--accent-2);
      font-weight: 700;
    }

    h1, h2, h3 {
      margin: 0;
      line-height: 1.15;
    }

    h1 {
      font-size: clamp(1.8rem, 3vw, 3rem);
      letter-spacing: -0.04em;
    }

    .banner-copy p {
      margin: 10px 0 0;
      max-width: 72ch;
      color: var(--muted);
    }

    .meta-grid {
      display: grid;
      grid-template-columns: repeat(4, minmax(0, 1fr));
      gap: 12px;
    }

    .meta-chip,
    .card,
    .score-card,
    .table-wrap {
      background: var(--bg-panel);
      border: 1px solid var(--border);
      border-radius: 18px;
    }

    .meta-chip {
      padding: 14px 16px;
      min-height: 84px;
      display: flex;
      flex-direction: column;
      justify-content: space-between;
      gap: 8px;
    }

    .meta-chip span {
      color: var(--muted);
      font-size: 0.8rem;
      text-transform: uppercase;
      letter-spacing: 0.08em;
    }

    .meta-chip strong {
      font-size: 1.05rem;
      overflow-wrap: anywhere;
    }

    .summary-grid {
      display: grid;
      grid-template-columns: 1.1fr 1fr;
      gap: 18px;
      margin-bottom: 22px;
    }

    .card {
      padding: 22px;
      box-shadow: 0 18px 40px rgba(0,0,0,0.18);
    }

    .card h2 {
      margin-bottom: 14px;
      font-size: 1.15rem;
    }

    .score-wrap {
      display: flex;
      align-items: center;
      gap: 22px;
      flex-wrap: wrap;
    }

    .score-circle {
      --score-percent: 0%;
      width: 156px;
      height: 156px;
      border-radius: 50%;
      background: conic-gradient(var(--accent) 0 var(--score-percent), rgba(255,255,255,0.12) var(--score-percent) 100%);
      display: grid;
      place-items: center;
      position: relative;
      flex: none;
    }

    .score-circle::after {
      content: "";
      position: absolute;
      inset: 14px;
      border-radius: 50%;
      background: rgba(9, 13, 23, 0.92);
      border: 1px solid rgba(255, 255, 255, 0.08);
    }

    .score-inner {
      position: relative;
      z-index: 1;
      text-align: center;
    }

    .score-value {
      display: block;
      font-size: 2.45rem;
      font-weight: 800;
      letter-spacing: -0.05em;
    }

    .score-max {
      color: var(--muted);
      font-size: 0.85rem;
    }

    .verdict {
      display: inline-flex;
      align-items: center;
      gap: 8px;
      padding: 8px 12px;
      border-radius: 999px;
      font-size: 0.82rem;
      font-weight: 700;
      text-transform: uppercase;
      letter-spacing: 0.08em;
      margin-bottom: 12px;
    }

    .verdict-good { color: var(--pass); background: rgba(76, 211, 138, 0.1); border: 1px solid rgba(76, 211, 138, 0.18); }
    .verdict-warn { color: var(--warning); background: rgba(244, 184, 96, 0.1); border: 1px solid rgba(244, 184, 96, 0.18); }
    .verdict-bad { color: var(--critical); background: rgba(255, 107, 122, 0.1); border: 1px solid rgba(255, 107, 122, 0.18); }

    .summary-text p {
      margin: 0;
      color: var(--muted);
    }

    .cards-grid {
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(190px, 1fr));
      gap: 12px;
      margin-top: 8px;
    }

    .score-card {
      padding: 16px;
    }

    .score-card .domain-name {
      font-size: 0.9rem;
      color: var(--muted);
      text-transform: uppercase;
      letter-spacing: 0.08em;
      margin-bottom: 8px;
    }

    .score-card .domain-score {
      font-size: 1.45rem;
      font-weight: 800;
      letter-spacing: -0.03em;
    }

    .score-card .domain-meta {
      margin-top: 8px;
      color: var(--muted);
      font-size: 0.9rem;
    }

    .table-wrap {
      overflow-x: auto;
      margin-top: 12px;
    }

    table {
      width: 100%;
      min-width: 880px;
      border-collapse: collapse;
      table-layout: fixed;
    }

    th, td {
      padding: 12px 14px;
      text-align: left;
      border-bottom: 1px solid rgba(255,255,255,0.09);
      vertical-align: top;
      overflow-wrap: anywhere;
      word-break: break-word;
    }

    th {
      text-transform: uppercase;
      letter-spacing: 0.08em;
      font-size: 0.74rem;
      color: var(--muted);
      background: rgba(255,255,255,0.04);
    }

    tbody tr:hover td {
      background: rgba(255,255,255,0.03);
    }

    .status-badge,
    .severity-badge {
      display: inline-flex;
      align-items: center;
      gap: 6px;
      padding: 6px 10px;
      border-radius: 999px;
      font-size: 0.76rem;
      font-weight: 700;
      text-transform: uppercase;
      letter-spacing: 0.08em;
      white-space: nowrap;
    }

    .status-good { color: var(--pass); background: rgba(76, 211, 138, 0.1); border: 1px solid rgba(76, 211, 138, 0.18); }
    .status-warn { color: var(--warning); background: rgba(244, 184, 96, 0.1); border: 1px solid rgba(244, 184, 96, 0.18); }
    .status-bad { color: var(--critical); background: rgba(255, 107, 122, 0.1); border: 1px solid rgba(255, 107, 122, 0.18); }
    .sev-critical { color: var(--critical); background: rgba(255, 107, 122, 0.08); border: 1px solid rgba(255, 107, 122, 0.18); }
    .sev-warning { color: var(--warning); background: rgba(244, 184, 96, 0.08); border: 1px solid rgba(244, 184, 96, 0.18); }
    .sev-info { color: var(--info); background: rgba(125, 179, 255, 0.08); border: 1px solid rgba(125, 179, 255, 0.18); }
    .sev-pass { color: var(--pass); background: rgba(76, 211, 138, 0.08); border: 1px solid rgba(76, 211, 138, 0.18); }

    .mono {
      font-family: var(--mono);
      font-size: 0.88rem;
    }

    .section {
      margin-top: 22px;
    }

    .section-title {
      display: flex;
      justify-content: space-between;
      gap: 12px;
      align-items: baseline;
      margin-bottom: 12px;
    }

    .section-title p {
      margin: 0;
      color: var(--muted);
      font-size: 0.92rem;
    }

    .grouped-table th:nth-child(1) { width: 14%; }
    .grouped-table th:nth-child(2) { width: 11%; }
    .grouped-table th:nth-child(3) { width: 15%; }
    .grouped-table th:nth-child(4) { width: 9%; }
    .grouped-table th:nth-child(5) { width: 25%; }
    .grouped-table th:nth-child(6) { width: 18%; }
    .grouped-table th:nth-child(7) { width: 8%; }

    .footer {
      margin-top: 26px;
      padding-top: 16px;
      border-top: 1px solid var(--border);
      color: var(--muted);
      display: flex;
      justify-content: space-between;
      gap: 16px;
      flex-wrap: wrap;
      font-size: 0.9rem;
    }

    .break-before { break-before: page; page-break-before: always; }

    @media (max-width: 960px) {
      .banner-top,
      .summary-grid {
        grid-template-columns: 1fr;
        display: grid;
      }

      .meta-grid {
        grid-template-columns: repeat(2, minmax(0, 1fr));
      }
    }

    @media (max-width: 680px) {
      .shell { padding-inline: 12px; }
      .meta-grid { grid-template-columns: 1fr; }
      .score-circle { width: 136px; height: 136px; }
      .score-value { font-size: 2rem; }
    }

    @media print {
      @page {
        size: A4;
        margin: 14mm;
      }

      :root {
        color-scheme: light;
        --bg: #fff;
        --bg-soft: #fff;
        --bg-panel: #fff;
        --bg-panel-strong: #fff;
        --border: #222;
        --text: #111;
        --muted: #444;
      }

      * {
        background-image: none !important;
        box-shadow: none !important;
        text-shadow: none !important;
      }

      body {
        background: #fff !important;
        color: #111 !important;
      }

      a {
        color: #111 !important;
        text-decoration: none !important;
      }

      .shell::before,
      .shell::after {
        display: none !important;
      }

      .banner,
      .card,
      .score-card,
      .table-wrap {
        break-inside: avoid;
        page-break-inside: avoid;
      }

      .break-before {
        break-before: page;
        page-break-before: always;
      }

      .table-wrap {
        overflow: visible;
      }

      table {
        min-width: 0;
        width: 100%;
      }

      th, td {
        color: #111 !important;
        border-color: #444 !important;
      }

      th {
        background: #f2f2f2 !important;
      }

      .meta-chip,
      .score-card,
      .card,
      .status-badge,
      .severity-badge,
      .verdict {
        background: #fff !important;
        color: #111 !important;
        border-color: #222 !important;
      }

      .score-circle {
        background: conic-gradient(#1f56d6 0 var(--score-percent), #e5e7eb var(--score-percent) 100%) !important;
        border: 1px solid #222;
      }

      .score-circle::after {
        background: #fff !important;
        border-color: #222 !important;
      }
    }
  </style>
</head>
<body>
  <div class="shell">
    <header class="banner">
      <div class="banner-top">
        <div class="banner-copy">
          <p class="eyebrow">Executive Audit Report</p>
          <h1>Stealth Lightbeacon</h1>
          <p>
            Target URL: <span class="mono">{{ target_url }}</span>
            | Concise grouped findings for executive review and print-ready delivery.
          </p>
        </div>
        <div class="verdict {{ verdict_class }}">{{ verdict }}</div>
      </div>

      <div class="meta-grid">
        <div class="meta-chip">
          <span>Average Score</span>
          <strong>{{ "%.1f" | format(average_score) }}/10</strong>
        </div>
        <div class="meta-chip">
          <span>Unique Issue Types</span>
          <strong>{{ unique_issue_types }}</strong>
        </div>
        <div class="meta-chip">
          <span>Total Original Issues</span>
          <strong>{{ total_issues }}</strong>
        </div>
        <div class="meta-chip">
          <span>Audit Version</span>
          <strong>{{ audit_version }}</strong>
        </div>
      </div>
    </header>

    <section class="summary-grid">
      <div class="card">
        <h2>Executive Summary</h2>
        <div class="score-wrap">
          <div class="score-circle" style="--score-percent: {{ score_percent }}%;">
            <div class="score-inner">
              <span class="score-value">{{ "%.1f" | format(average_score) }}</span>
              <span class="score-max">/ 10</span>
            </div>
          </div>
          <div class="summary-text">
            <p class="verdict {{ verdict_class }}" style="display:inline-flex;margin-bottom:10px;">{{ verdict }}</p>
            <p>{{ verdict_summary }}</p>
          </div>
        </div>
      </div>

      <div class="card">
        <h2>Domain Scorecards</h2>
        <div class="cards-grid">
          {% for domain in domains %}
          <div class="score-card">
            <div class="domain-name">{{ domain.name }}</div>
            <div class="domain-score">{{ "%.1f" | format(domain.score) }}/10</div>
            <div class="domain-meta">{{ domain.issue_count }} original issues</div>
          </div>
          {% endfor %}
        </div>
      </div>
    </section>

    <section class="section">
      <div class="section-title">
        <h2>Domain Breakdown Table</h2>
        <p>Original issue counts are preserved per domain. Status reflects the domain score.</p>
      </div>
      <div class="table-wrap">
        <table>
          <thead>
            <tr>
              <th>Domain</th>
              <th>Score</th>
              <th>Issue Count</th>
              <th>Status</th>
            </tr>
          </thead>
          <tbody>
            {% for domain in domains %}
            <tr>
              <td>{{ domain.name }}</td>
              <td class="mono">{{ "%.1f" | format(domain.score) }}/10</td>
              <td class="mono">{{ domain.issue_count }}</td>
              <td>
                <span class="status-badge {{ domain.status_class }}">{{ domain.status_label }}</span>
              </td>
            </tr>
            {% endfor %}
          </tbody>
        </table>
      </div>
    </section>

    <section class="section break-before">
      <div class="section-title">
        <h2>Grouped Issues Table</h2>
        <p>Identical issues are grouped by Issue ID + message and counted across pages.</p>
      </div>
      <div class="table-wrap">
        <table class="grouped-table">
          <thead>
            <tr>
              <th>Issue ID</th>
              <th>Severity</th>
              <th>Domain</th>
              <th>Occurrences</th>
              <th>Issue Message</th>
              <th>Recommendation</th>
              <th>Sample Location</th>
            </tr>
          </thead>
          <tbody>
            {% if grouped_issues %}
              {% for issue in grouped_issues %}
              <tr>
                <td class="mono">{{ issue.id }}</td>
                <td>
                  <span class="severity-badge {{ issue.severity_class }}">{{ issue.severity }}</span>
                </td>
                <td>{{ issue.domain }}</td>
                <td class="mono">{{ issue.occurrences }}</td>
                <td>{{ issue.message }}</td>
                <td>{{ issue.remedy }}</td>
                <td class="mono">{{ issue.sample_location }}</td>
              </tr>
              {% endfor %}
            {% else %}
            <tr>
              <td colspan="7">No grouped issues were detected.</td>
            </tr>
            {% endif %}
          </tbody>
        </table>
      </div>
    </section>

    <footer class="footer">
      <div>Generated {{ generated_at }}</div>
      <div>{{ generator_info }}</div>
    </footer>
  </div>
</body>
</html>
"""

    @classmethod
    def _severity_class(cls, severity: str) -> str:
        key = (severity or "").strip().lower()
        return {
            "critical": "sev-critical",
            "warning": "sev-warning",
            "info": "sev-info",
            "pass": "sev-pass",
        }.get(key, "sev-info")

    @classmethod
    def _status_label(cls, score: float) -> tuple[str, str]:
        if score >= 8.0:
            return "Excellent", "status-good"
        if score >= 5.0:
            return "Warning", "status-warn"
        return "Critical", "status-bad"

    @classmethod
    def _verdict(cls, score: float) -> tuple[str, str, str]:
        if score >= 8.0:
            return "Excellent", "Strong overall posture with only minor remediation items.", "verdict-good"
        if score >= 5.0:
            return "Warning", "Overall posture is serviceable, but several issues should be prioritized.", "verdict-warn"
        return "Critical Gaps", "Material remediation is required before this audit surface should be considered healthy.", "verdict-bad"

    @classmethod
    def _group_issues(cls, domains: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
        grouped: dict[tuple[str, str, str], dict[str, Any]] = {}
        for domain in domains:
            domain_name = str(domain.get("name", ""))
            for issue in domain.get("issues", []):
                key = (str(issue.get("id", "")), str(issue.get("message", "")), domain_name)
                entry = grouped.setdefault(
                    key,
                    {
                        "id": key[0],
                        "message": key[1],
                        "severity": str(issue.get("severity", "")),
                        "severity_class": cls._severity_class(str(issue.get("severity", ""))),
                        "domain": domain_name,
                        "occurrences": 0,
                        "remedy": str(issue.get("remedy", "")),
                        "sample_location": str(issue.get("location", "")),
                    },
                )
                entry["occurrences"] += 1
                if not entry["sample_location"] and issue.get("location"):
                    entry["sample_location"] = str(issue.get("location", ""))
                if not entry["remedy"] and issue.get("remedy"):
                    entry["remedy"] = str(issue.get("remedy", ""))
        ordered = sorted(
            grouped.values(),
            key=lambda item: (
                _SEVERITY_ORDER.get(str(item["severity"]).strip().lower(), 9),
                -int(item["occurrences"]),
                item["id"],
                item["message"],
            ),
        )
        return ordered

    @classmethod
    def _build_context(cls, url: str, results: List[EvaluationResult]) -> dict[str, Any]:
        payload = build_report_payload(url, results)
        grouped_issues = cls._group_issues(payload["domains"])
        domains = []
        for domain in payload["domains"]:
            status_label, status_class = cls._status_label(float(domain["score"]))
            domains.append(
                {
                    "name": domain["name"],
                    "score": float(domain["score"]),
                    "issue_count": len(domain["issues"]),
                    "status_label": status_label,
                    "status_class": status_class,
                }
            )
        verdict, verdict_summary, verdict_class = cls._verdict(float(payload["average_score"]))
        generated_at = datetime.now(timezone.utc).astimezone().strftime("%Y-%m-%d %H:%M %Z")
        return {
            "target_url": payload["target_url"],
            "average_score": float(payload["average_score"]),
            "score_percent": max(0, min(100, int(round(float(payload["average_score"]) * 10)))),
            "total_issues": int(payload["total_issues"]),
            "unique_issue_types": len(grouped_issues),
            "audit_version": f"v{config.SERVICE_VERSION}",
            "verdict": verdict,
            "verdict_summary": verdict_summary,
            "verdict_class": verdict_class,
            "generated_at": generated_at,
            "generator_info": "Stealth Lightbeacon HTML/PDF executive report",
            "domains": domains,
            "grouped_issues": grouped_issues,
        }

    @classmethod
    def _render_html(cls, context: dict[str, Any]) -> str:
        env = Environment(autoescape=select_autoescape(["html", "xml"]))
        return env.from_string(cls.HTML_TEMPLATE).render(**context)

    @classmethod
    def _slugify(cls, value: str) -> str:
        slug = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
        return slug or "report"

    @classmethod
    def _target_slug(cls, url: str) -> str:
        parsed = urlparse(url)
        host = parsed.netloc or parsed.path or url
        host = host.split("@")[-1].split(":")[0]
        if host.startswith("www."):
            host = host[4:]
        return cls._slugify(host)

    @classmethod
    def _result_token(cls, verdict_class: str) -> str:
        return {
            "verdict-good": "success",
            "verdict-warn": "warning",
            "verdict-bad": "failure",
        }.get(verdict_class, "success")

    @classmethod
    def _score_token(cls, score: float) -> str:
        return f"{score:.1f}".replace(".", "p")

    @classmethod
    def _report_stem(cls, url: str, context: dict[str, Any]) -> str:
        target_slug = cls._target_slug(url)
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        score_token = cls._score_token(float(context["average_score"]))
        result_token = cls._result_token(str(context["verdict_class"]))
        return f"{target_slug}_report_{timestamp}_score-{score_token}_result-{result_token}"

    @classmethod
    def build_report_paths(cls, url: str, results: List[EvaluationResult], output_dir: str) -> dict[str, str]:
        context = cls._build_context(url, results)
        output_path = Path(output_dir)
        report_dir = output_path / cls._target_slug(url)
        report_stem = cls._report_stem(url, context)
        return {
            "report_dir": str(report_dir),
            "report_stem": report_stem,
            "html_path": str(report_dir / f"{report_stem}.html"),
            "pdf_path": str(report_dir / f"{report_stem}.pdf"),
            "legacy_html_path": str(output_path / "report.html"),
            "legacy_pdf_path": str(output_path / "report.pdf"),
        }

    @classmethod
    def _find_chrome(cls) -> str | None:
        env_path = os.getenv("SLB_PDF_RENDERER", "").strip() or os.getenv("SLB_CHROME_PATH", "").strip()
        candidates = [
            env_path,
            "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
            "/Applications/Chromium.app/Contents/MacOS/Chromium",
            "/usr/local/bin/google-chrome",
            "/usr/local/bin/google-chrome-stable",
            "/usr/local/bin/msedge",
            "/opt/homebrew/bin/google-chrome",
            "/opt/homebrew/bin/google-chrome-stable",
            "/opt/homebrew/bin/msedge",
            "/usr/local/bin/chromium",
            "/usr/local/bin/chromium-browser",
        ]
        for candidate in candidates:
            if candidate and Path(candidate).exists():
                return candidate
        return None

    @classmethod
    def _pdf_escape(cls, text: str) -> str:
        return text.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")

    @classmethod
    def _build_pdf_lines(cls, context: dict[str, Any]) -> list[tuple[str, int, str, int]]:
        def add(lines: list[tuple[str, int, str, int]], font: str, size: int, text: str, leading: int | None = None) -> None:
            lines.append((font, size, text, leading if leading is not None else size + 3))

        def wrap_text(prefix: str, text: str, width: int = 96) -> list[str]:
            if not text:
                return [prefix]
            usable = max(16, width - len(prefix))
            wrapped = textwrap.wrap(text, width=usable, break_long_words=False, break_on_hyphens=False)
            if not wrapped:
                return [prefix]
            return [prefix + wrapped[0]] + [(" " * len(prefix)) + chunk for chunk in wrapped[1:]]

        lines: list[tuple[str, int, str, int]] = []
        add(lines, "F2", 16, "Stealth Lightbeacon Executive Audit Report", 22)
        add(lines, "F1", 10, f"Target URL: {context['target_url']}")
        add(
            lines,
            "F1",
            10,
            (
                f"Average score: {context['average_score']:.1f}/10.0   "
                f"Unique issue types: {context['unique_issue_types']}   "
                f"Total issues: {context['total_issues']}"
            ),
        )
        add(lines, "F1", 10, f"Audit version: {context['audit_version']}   Generated: {context['generated_at']}")
        add(lines, "F1", 10, f"Verdict: {context['verdict'].upper()} - {context['verdict_summary']}", 14)

        add(lines, "F2", 13, "Executive Summary", 18)
        for chunk in wrap_text("Summary: ", context["verdict_summary"], width=96):
            add(lines, "F1", 10, chunk)
        add(lines, "F1", 10, "")

        add(lines, "F2", 13, "Domain Scorecards", 18)
        for domain in context["domains"]:
            add(
                lines,
                "F3",
                9,
                (
                    f"{domain['name']:<24.24} "
                    f"score {domain['score']:.1f}/10.0  "
                    f"issues {domain['issue_count']:>3}  "
                    f"{domain['status_label']}"
                ),
                11,
            )
        add(lines, "F1", 10, "")

        add(lines, "F2", 13, "Grouped Issues", 18)
        header = "ID                   Severity  Domain                  Occ  Issue message"
        add(lines, "F3", 8, header, 10)
        for issue in context["grouped_issues"]:
            base = (
                f"{issue['id']:<20.20} "
                f"{issue['severity']:<8.8} "
                f"{issue['domain']:<22.22} "
                f"x{issue['occurrences']:>3}  "
                f"{issue['message']}"
            )
            for chunk in textwrap.wrap(base, width=104, break_long_words=False, break_on_hyphens=False) or [base]:
                add(lines, "F3", 8, chunk, 10)
            for label, value in (
                ("Recommendation", issue["remedy"]),
                ("Sample location", issue["sample_location"]),
            ):
                for chunk in wrap_text(f"  {label}: ", value, width=96):
                    add(lines, "F3", 8, chunk, 9)
            add(lines, "F1", 8, "")

        add(lines, "F1", 9, f"Generator: {context['generator_info']}")
        return lines

    @classmethod
    def _write_pdf_document(cls, pdf_path: Path, lines: list[tuple[str, int, str, int]]) -> None:
        page_width = 792.0
        page_height = 612.0
        margin_left = 36.0
        margin_top = 34.0
        margin_bottom = 34.0

        pages: list[list[tuple[str, int, str, float]]] = []
        current: list[tuple[str, int, str, float]] = []
        cursor_y = page_height - margin_top
        for font, size, text, leading in lines:
            if text and cursor_y - leading < margin_bottom:
                pages.append(current)
                current = []
                cursor_y = page_height - margin_top
            if text:
                current.append((font, size, text, cursor_y))
            cursor_y -= leading
        if current:
            pages.append(current)

        font_objects = {
            "F1": 3,
            "F2": 4,
            "F3": 5,
        }

        objects: list[bytes] = []
        objects.append(b"<< /Type /Catalog /Pages 2 0 R >>")
        objects.append(b"")
        objects.append(b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>")
        objects.append(b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica-Bold >>")
        objects.append(b"<< /Type /Font /Subtype /Type1 /BaseFont /Courier >>")

        page_object_ids: list[int] = []
        content_object_ids: list[int] = []
        next_object_id = 6
        for page in pages or [[]]:
            page_object_ids.append(next_object_id)
            content_object_ids.append(next_object_id + 1)
            next_object_id += 2

        for page, page_object_id, content_object_id in zip(pages or [[]], page_object_ids, content_object_ids):
            content_parts = []
            for font, size, text, y in page:
                escaped = cls._pdf_escape(text)
                content_parts.append(
                    f"BT /{font} {size} Tf 1 0 0 1 {margin_left:.1f} {y:.1f} Tm ({escaped}) Tj ET"
                )
            content = "\n".join(content_parts).encode("utf-8")
            objects.append(
                (
                    f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 {page_width:.1f} {page_height:.1f}] "
                    f"/Resources << /Font << /F1 3 0 R /F2 4 0 R /F3 5 0 R >> >> "
                    f"/Contents {content_object_id} 0 R >>"
                ).encode("utf-8")
            )
            objects.append(f"<< /Length {len(content)} >>\nstream\n".encode("utf-8") + content + b"\nendstream")

        kids = " ".join(f"{page_id} 0 R" for page_id in page_object_ids)
        objects[1] = f"<< /Type /Pages /Kids [{kids}] /Count {len(page_object_ids)} >>".encode("utf-8")

        with pdf_path.open("wb") as handle:
            handle.write(b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n")
            offsets = [0]
            for index, body in enumerate(objects, start=1):
                offsets.append(handle.tell())
                handle.write(f"{index} 0 obj\n".encode("utf-8"))
                handle.write(body)
                handle.write(b"\nendobj\n")
            xref_offset = handle.tell()
            handle.write(f"xref\n0 {len(objects) + 1}\n".encode("utf-8"))
            handle.write(b"0000000000 65535 f \n")
            for offset in offsets[1:]:
                handle.write(f"{offset:010d} 00000 n \n".encode("utf-8"))
            handle.write(
                (
                    "trailer\n"
                    f"<< /Size {len(objects) + 1} /Root 1 0 R >>\n"
                    f"startxref\n{xref_offset}\n%%EOF\n"
                ).encode("utf-8")
            )

    @classmethod
    def _render_pdf(cls, html_path: Path, pdf_path: Path, context: dict[str, Any]) -> None:
        chrome = cls._find_chrome()
        if chrome:
            html_uri = html_path.resolve().as_uri()
            command = [
                chrome,
                "--headless",
                "--disable-gpu",
                "--no-sandbox",
                "--allow-file-access-from-files",
                "--run-all-compositor-stages-before-draw",
                f"--print-to-pdf={pdf_path}",
                html_uri,
            ]
            try:
                result = subprocess.run(command, capture_output=True, text=True, timeout=120)
                if result.returncode == 0 and pdf_path.exists():
                    return
            except Exception:
                pass

        cls._write_pdf_document(pdf_path, cls._build_pdf_lines(context))
        if not pdf_path.exists():
            raise RuntimeError("PDF generation completed without creating an output file.")

    @classmethod
    def generate_report(
        cls,
        url: str,
        results: List[EvaluationResult],
        output_dir: str,
        report_paths: dict[str, str] | None = None,
    ) -> dict[str, str]:
        """
        Generate executive HTML and PDF reports from the audit results.
        """
        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)

        context = cls._build_context(url, results)
        report_paths = report_paths or cls.build_report_paths(url, results, output_dir)
        html_content = cls._render_html(context)

        report_dir = Path(report_paths["report_dir"])
        report_stem = report_paths["report_stem"]
        html_path = Path(report_paths["html_path"])
        pdf_path = Path(report_paths["pdf_path"])
        legacy_html_path = Path(report_paths["legacy_html_path"])
        legacy_pdf_path = Path(report_paths["legacy_pdf_path"])

        report_dir.mkdir(parents=True, exist_ok=True)
        html_path.write_text(html_content, encoding="utf-8")
        legacy_html_path.write_text(html_content, encoding="utf-8")
        cls._render_pdf(html_path, pdf_path, context=context)
        legacy_pdf_path.write_bytes(pdf_path.read_bytes())

        return {
            **report_paths,
            "payload": json.dumps(context, default=str),
        }

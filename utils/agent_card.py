"""Stable agent card / manifest for orchestration consumers."""

from __future__ import annotations


def build_agent_card() -> dict:
    return {
        "schemaVersion": "1",
        "name": "stealth-lightbeacon",
        "entrypoint": "python main.py evaluate",
        "inputs": {
            "url": "Target URL or SLB_TARGET_URL environment variable.",
            "audits": "Comma-separated evaluator subset such as security,performance.",
            "auth_token": "Optional SLB_AUTH_TOKEN bearer token.",
            "fail_on_critical": "Whether critical issues should fail the job.",
            "recon": "Whether to run anti-bot reconnaissance before crawl.",
            "auto_select_scraper": "Whether to apply recon recommendations automatically.",
        },
        "outputs": {
            "formats": ["json", "html", "both", "llm", "geo-xml", "pdf"],
            "artifact_paths": [
                "reports/<domain>/<stem>.json",
                "reports/<domain>/<stem>.html",
                "reports/<domain>/<stem>.pdf",
                "reports/<domain>/<stem>.md",
                "reports/<domain>/<stem>.xml",
                "reports/report.html",
                "reports/report.pdf",
            ],
        },
        "audits": [
            "seo",
            "performance",
            "accessibility",
            "aeo-geo",
            "ux",
            "security",
        ],
        "canary": {
            "supported": True,
            "max_urls_default": 10,
            "subset_supported": True,
            "critical_gate_supported": True,
        },
    }

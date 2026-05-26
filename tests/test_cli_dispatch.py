from unittest.mock import patch

from typer.testing import CliRunner

import main
from modules.base import EvaluationResult


runner = CliRunner()


def test_cli_evaluate_dispatches_core_runtime_args(monkeypatch, tmp_path):
    captured = {}

    async def fake_run_evaluation(url, active_modules, **kwargs):
        captured["url"] = url
        captured["active_domains"] = [module.domain for module in active_modules]
        captured["kwargs"] = kwargs
        return [
            EvaluationResult(
                domain="Technical SEO",
                score=8.5,
                issues=tuple(),
                metadata={},
            )
        ]

    monkeypatch.setenv("SLB_AUTH_TOKEN", "token-123")
    monkeypatch.setattr(main, "run_evaluation", fake_run_evaluation)
    monkeypatch.setattr(main, "print_terminal_report", lambda *args, **kwargs: None)

    with patch("modules.scraping.ScrapingFactory.get_engine", return_value=None):
        result = runner.invoke(
            main.app,
            [
                "https://example.com",
                "--out",
                str(tmp_path),
                "--audits",
                "security,performance",
                "--crawl-depth",
                "2",
                "--max-urls",
                "25",
                "--check-links",
                "--check-api",
                "--format",
                "json",
                "--fail-on-critical",
            ],
        )

    assert result.exit_code == 0
    assert captured["url"] == "https://example.com"
    assert "Drupal & Security Headers" in captured["active_domains"]
    assert "PageSpeed & Performance" in captured["active_domains"]
    assert captured["kwargs"]["crawl_depth"] == 2
    assert captured["kwargs"]["max_urls"] == 25
    assert captured["kwargs"]["check_links"] is True
    assert captured["kwargs"]["check_api"] is True
    assert captured["kwargs"]["auth_token"] == "token-123"

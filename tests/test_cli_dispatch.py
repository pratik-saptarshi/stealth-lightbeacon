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
                "evaluate",
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


def test_cli_evaluate_accepts_pdf_format_and_generates_report(monkeypatch, tmp_path):
    async def fake_run_evaluation(url, active_modules, **kwargs):
        return [
            EvaluationResult(
                domain="Technical SEO",
                score=8.5,
                issues=tuple(),
                metadata={},
            )
        ]

    monkeypatch.setattr(main, "run_evaluation", fake_run_evaluation)
    monkeypatch.setattr(main, "print_terminal_report", lambda *args, **kwargs: None)

    with patch("modules.scraping.ScrapingFactory.get_engine", return_value=None), patch(
        "report.generator.ReportGenerator.build_report_paths",
        return_value={"report_dir": str(tmp_path), "report_stem": "report"},
    ), patch(
        "report.generator.ReportGenerator.generate_report",
        side_effect=lambda url, results, output_dir, report_paths: {
            **report_paths,
            "html_path": str(tmp_path / "report.html"),
            "pdf_path": str(tmp_path / "report.pdf"),
        },
    ) as mock_generate:
        result = runner.invoke(
            main.app,
            [
                "evaluate",
                "https://example.com",
                "--out",
                str(tmp_path),
                "--format",
                "pdf",
            ],
        )

    assert result.exit_code == 0
    mock_generate.assert_called_once()

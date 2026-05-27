from __future__ import annotations

from modules.base import EvaluationResult
from utils.budget_validator import BudgetValidator


def test_budget_validator_handles_missing_perf_result_and_pass_case():
    validator = BudgetValidator({"performance_score": 8.0, "lcp_ms": 1500})
    assert validator.validate([]) == []

    result = EvaluationResult(
        domain="PageSpeed & Performance",
        score=8.5,
        issues=(),
        metadata={"lcp_ms": 1200, "cls": 0.05, "inp_ms": 150, "ttfb_ms": 300},
    )
    assert validator.validate([result]) == []

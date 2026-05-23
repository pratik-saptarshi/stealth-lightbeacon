"""
budget_validator.py — Core validator for enforcing performance budgets.
Compares Core Web Vitals and performance scores against user-defined limits.
"""

from typing import List, Dict, Any
from modules.base import EvaluationResult

class BudgetValidator:
    """
    Enforces a strict performance budget over Core Web Vitals and scoring metrics.
    """
    def __init__(self, budget: Dict[str, Any]):
        self.budget = {k.lower(): v for k, v in budget.items()}

    def validate(self, results: List[EvaluationResult]) -> List[str]:
        """
        Validates the evaluation results against the performance budget configuration.
        Returns a list of failure descriptions if any budget boundaries are breached.
        """
        failures = []
        perf_result = None
        for r in results:
            if r.domain == "PageSpeed & Performance":
                perf_result = r
                break
                
        if not perf_result:
            return failures

        metadata = perf_result.metadata
        score = perf_result.score

        # 1. Validate LCP
        if "lcp_ms" in self.budget and "lcp_ms" in metadata:
            budget_lcp = self.budget["lcp_ms"]
            actual_lcp = metadata["lcp_ms"]
            if actual_lcp is not None and actual_lcp > budget_lcp:
                failures.append(f"LCP exceeded budget: {actual_lcp}ms > {budget_lcp}ms")

        # 2. Validate CLS
        if "cls" in self.budget and "cls" in metadata:
            budget_cls = self.budget["cls"]
            actual_cls = metadata["cls"]
            if actual_cls is not None and actual_cls > budget_cls:
                failures.append(f"CLS exceeded budget: {actual_cls} > {budget_cls}")

        # 3. Validate INP
        if "inp_ms" in self.budget and "inp_ms" in metadata:
            budget_inp = self.budget["inp_ms"]
            actual_inp = metadata["inp_ms"]
            if actual_inp is not None and actual_inp > budget_inp:
                failures.append(f"INP exceeded budget: {actual_inp}ms > {budget_inp}ms")

        # 4. Validate TTFB
        if "ttfb_ms" in self.budget and "ttfb_ms" in metadata:
            budget_ttfb = self.budget["ttfb_ms"]
            actual_ttfb = metadata["ttfb_ms"]
            if actual_ttfb is not None and actual_ttfb > budget_ttfb:
                failures.append(f"TTFB exceeded budget: {actual_ttfb}ms > {budget_ttfb}ms")

        # 5. Validate Score
        if "performance_score" in self.budget:
            budget_score = self.budget["performance_score"]
            if score < budget_score:
                failures.append(f"Performance Score was below budget: {score} < {budget_score}")

        return failures

"""
test_performance_budget.py — TDD Unit tests for the Performance Budget Enforcer.
"""

import pytest
import os
import json
import typer
from modules.base import EvaluationResult
from main import app
from typer.testing import CliRunner

runner = CliRunner()

def test_performance_budget_validation_success():
    """
    Budget validator must pass with no errors if PageSpeed results satisfy all budget boundaries.
    """
    from utils.budget_validator import BudgetValidator
    
    results = [
        EvaluationResult(
            domain="PageSpeed & Performance",
            score=9.5,
            issues=(),
            metadata={
                "lighthouse_performance": 95,
                "lcp_ms": 1500,
                "cls": 0.05,
                "inp_ms": 100,
                "ttfb_ms": 400
            }
        )
    ]
    
    budget = {
        "lcp_ms": 2500,
        "cls": 0.1,
        "inp_ms": 200,
        "ttfb_ms": 800,
        "performance_score": 8.0
    }
    
    validator = BudgetValidator(budget)
    failures = validator.validate(results)
    
    assert len(failures) == 0

def test_performance_budget_validation_failures():
    """
    Budget validator must identify exact metrics exceeding the specified boundaries.
    """
    from utils.budget_validator import BudgetValidator
    
    results = [
        EvaluationResult(
            domain="PageSpeed & Performance",
            score=7.0,
            issues=(),
            metadata={
                "lighthouse_performance": 70,
                "lcp_ms": 3200,  # Exceeds 2500
                "cls": 0.18,     # Exceeds 0.10
                "inp_ms": 120,
                "ttfb_ms": 950   # Exceeds 800
            }
        )
    ]
    
    budget = {
        "lcp_ms": 2500,
        "cls": 0.1,
        "inp_ms": 200,
        "ttfb_ms": 800,
        "performance_score": 8.0 # Exceeds (score is 7.0)
    }
    
    validator = BudgetValidator(budget)
    failures = validator.validate(results)
    
    assert len(failures) == 4
    assert any("LCP" in f for f in failures)
    assert any("CLS" in f for f in failures)
    assert any("TTFB" in f for f in failures)
    assert any("Performance Score" in f for f in failures)

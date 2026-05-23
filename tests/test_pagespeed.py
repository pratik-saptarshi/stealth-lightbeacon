"""
test_pagespeed.py — Unit tests for the PagespeedEvaluator module.
"""

import os
import json
import shutil
import pytest
from modules.pagespeed import PagespeedEvaluator
from modules.base import EvaluationResult

# Define a temporary cache directory for test validation
TEST_CACHE_DIR = "reports/test_cache"

@pytest.fixture(autouse=True)
def run_around_tests():
    """
    Cleans up the temporary test cache folder before and after tests.
    """
    if os.path.exists(TEST_CACHE_DIR):
        shutil.rmtree(TEST_CACHE_DIR)
    os.makedirs(TEST_CACHE_DIR, exist_ok=True)
    yield
    if os.path.exists(TEST_CACHE_DIR):
        shutil.rmtree(TEST_CACHE_DIR)

@pytest.mark.asyncio
async def test_pagespeed_evaluator_cache_reads():
    """
    Verifies that fresh cached results are read directly, avoiding external API triggers.
    """
    evaluator = PagespeedEvaluator(cache_dir=TEST_CACHE_DIR)
    url = "https://example.com/speedy-page"
    
    # Write manual mock data to cache
    mock_psi_response = {
        "lighthouseResult": {
            "categories": {
                "performance": {"score": 0.95}
            }
        },
        "loadingExperience": {
            "metrics": {
                "LARGEST_CONTENTFUL_PAINT_MS": {"percentile": 1200},
                "CUMULATIVE_LAYOUT_SHIFT_SCORE": {"percentile": 2},
                "INTERACTION_TO_NEXT_PAINT": {"percentile": 80},
                "EXPERIMENTAL_TIME_TO_FIRST_BYTE": {"percentile": 200}
            }
        }
    }
    evaluator._write_to_cache(url, mock_psi_response)
    
    # Run evaluation (should trigger cache hit instantly)
    result = await evaluator.evaluate("", url)
    
    assert isinstance(result, EvaluationResult)
    assert result.domain == "PageSpeed & Performance"
    assert result.score == 10.0
    assert not result.issues
    assert result.metadata["lcp_ms"] == 1200
    assert result.metadata["cls"] == 0.02

@pytest.mark.asyncio
async def test_pagespeed_evaluator_cwv_scoring():
    """
    Verifies that Core Web Vitals exceeding target thresholds correctly raise warnings and critical issues.
    """
    evaluator = PagespeedEvaluator(cache_dir=TEST_CACHE_DIR)
    url = "https://example.com/slow-page"
    
    # Write a slow mock PSI response to cache
    mock_psi_response = {
        "lighthouseResult": {
            "categories": {
                "performance": {"score": 0.45}
            }
        },
        "loadingExperience": {
            "metrics": {
                "LARGEST_CONTENTFUL_PAINT_MS": {"percentile": 4500},  # CRITICAL (>4000)
                "CUMULATIVE_LAYOUT_SHIFT_SCORE": {"percentile": 15},  # WARNING (0.15)
                "INTERACTION_TO_NEXT_PAINT": {"percentile": 600},     # CRITICAL (>500)
                "EXPERIMENTAL_TIME_TO_FIRST_BYTE": {"percentile": 950} # WARNING (950)
            }
        }
    }
    evaluator._write_to_cache(url, mock_psi_response)
    
    # Run evaluation
    result = await evaluator.evaluate("", url)
    
    assert result.score < 6.0
    assert len(result.issues) == 4
    
    issue_ids = [issue.id for issue in result.issues]
    assert "R-PERF-LCP-CRIT" in issue_ids
    assert "R-PERF-CLS-WARN" in issue_ids
    assert "R-PERF-INP-CRIT" in issue_ids
    assert "R-PERF-TTFB-WARN" in issue_ids

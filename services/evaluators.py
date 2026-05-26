"""Evaluator selection helpers shared by the CLI and service adapters."""

from __future__ import annotations

from typing import List, Optional

from modules.base import BaseEvaluator


def select_active_evaluators(audits: Optional[str] = None) -> List[BaseEvaluator]:
    from modules.accessibility import AccessibilityEvaluator
    from modules.aeo_geo import AeoGeoEvaluator
    from modules.drupal import DrupalEvaluator
    from modules.pagespeed import PagespeedEvaluator
    from modules.seo import SeoEvaluator
    from modules.ux import UxEvaluator

    all_evaluators = [
        ("seo", SeoEvaluator),
        ("performance", PagespeedEvaluator),
        ("accessibility", AccessibilityEvaluator),
        ("aeo-geo", AeoGeoEvaluator),
        ("ux", UxEvaluator),
        ("security", DrupalEvaluator),
    ]
    if not audits:
        return [factory() for _, factory in all_evaluators]

    requested = {item.strip().lower() for item in audits.split(",") if item.strip()}
    if not requested or requested.intersection({"all", "*"}):
        return [factory() for _, factory in all_evaluators]

    aliases = {
        "seo": "seo",
        "performance": "performance",
        "accessibility": "accessibility",
        "aeo": "aeo-geo",
        "geo": "aeo-geo",
        "aeo-geo": "aeo-geo",
        "ux": "ux",
        "security": "security",
        "drupal": "security",
    }
    normalized = {aliases.get(item, item) for item in requested}
    selected = []
    for key, factory in all_evaluators:
        if key in normalized:
            selected.append(factory())
    return selected

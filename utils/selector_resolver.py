"""Selector repair helper for minor layout shifts."""

from __future__ import annotations

from dataclasses import dataclass
from difflib import SequenceMatcher
from typing import Any, Dict, Optional


@dataclass(frozen=True)
class ResolvedSelector:
    node: Any
    selector: str
    confidence: float
    repaired: bool


class SelectorResolver:
    def __init__(self, min_confidence: float = 0.5):
        self.min_confidence = min_confidence
        self.cache: Dict[str, ResolvedSelector] = {}

    def _signature(self, name: Any, attrs: Optional[Dict[str, Any]], kwargs: Dict[str, Any]) -> str:
        attrs = attrs or {}
        parts = [str(name)]
        for key, value in sorted(attrs.items()):
            parts.append(f"{key}={value}")
        for key, value in sorted(kwargs.items()):
            parts.append(f"{key}={value}")
        return "|".join(parts)

    def _split_selector(self, name: Any, attrs: Optional[Dict[str, Any]]) -> tuple[Any, Dict[str, Any]]:
        if not isinstance(name, str):
            return name, attrs or {}
        if "#" not in name and "." not in name:
            return name, attrs or {}

        base, *class_bits = name.split(".")
        selector_attrs = dict(attrs or {})
        if "#" in base:
            tag, element_id = base.split("#", 1)
            if tag:
                base = tag
            selector_attrs.setdefault("id", element_id)
        if class_bits:
            selector_attrs.setdefault("class", class_bits)
        return base or None, selector_attrs

    def _exact_find(self, parser: Any, name: Any, attrs: Optional[Dict[str, Any]], kwargs: Dict[str, Any]):
        backend = getattr(parser, "_parser", parser)
        finder = getattr(backend, "find", None)
        if finder is None:
            return None
        return finder(name, attrs, **kwargs)

    def _exact_find_all(self, parser: Any, name: Any, attrs: Optional[Dict[str, Any]], kwargs: Dict[str, Any]):
        backend = getattr(parser, "_parser", parser)
        finder = getattr(backend, "find_all", None)
        if finder is None:
            return []
        return finder(name, attrs, **kwargs)

    def _selector_for_node(self, node: Any) -> str:
        attrs = getattr(node, "attrs", {}) or {}
        if attrs.get("id"):
            return f"{node.name}#{attrs['id']}"
        classes = attrs.get("class") or []
        if isinstance(classes, str):
            classes = classes.split()
        if classes:
            return f"{node.name}.{'.'.join(classes)}"
        return node.name

    def _score_candidate(self, candidate: Any, attrs: Dict[str, Any], text_hint: Optional[str]) -> float:
        score = 0.4
        cand_attrs = getattr(candidate, "attrs", {}) or {}
        if attrs:
            matches = 0
            for key, value in attrs.items():
                if cand_attrs.get(key) == value:
                    matches += 1
            score += 0.4 * (matches / max(len(attrs), 1))
        if text_hint:
            score += 0.2 * SequenceMatcher(None, candidate.get_text().strip().lower(), text_hint.strip().lower()).ratio()
        else:
            score += 0.2 if candidate.get_text().strip() else 0.0
        return min(score, 1.0)

    def resolve(self, parser: Any, name: Any = None, attrs: Optional[Dict[str, Any]] = None, text_hint: Optional[str] = None, **kwargs) -> ResolvedSelector:
        name, attrs = self._split_selector(name, attrs)
        key = self._signature(name, attrs, kwargs)
        cached = self.cache.get(key)
        if cached is not None:
            return cached

        exact = self._exact_find(parser, name, attrs, kwargs)
        if exact is not None:
            resolved = ResolvedSelector(node=exact, selector=self._selector_for_node(exact), confidence=1.0, repaired=False)
            self.cache[key] = resolved
            return resolved

        candidates = self._exact_find_all(parser, name, None, {}) if name is not None else self._exact_find_all(parser, name, None, {})
        best_node = None
        best_score = 0.0
        for candidate in candidates:
            score = self._score_candidate(candidate, attrs or {}, text_hint)
            if score > best_score:
                best_score = score
                best_node = candidate

        if best_node is None or best_score < self.min_confidence:
            resolved = ResolvedSelector(node=None, selector=str(name or "*"), confidence=best_score, repaired=False)
            self.cache[key] = resolved
            return resolved

        resolved = ResolvedSelector(
            node=best_node,
            selector=self._selector_for_node(best_node),
            confidence=best_score,
            repaired=True,
        )
        self.cache[key] = resolved
        return resolved

"""
base.py — Base interface and data models for evaluation modules.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional, Tuple

@dataclass(frozen=True)
class Issue:
    id: str
    severity: str  # critical, warning, pass, info
    message: str
    location: str = ""
    remedy: str = ""

@dataclass(frozen=True)
class EvaluationResult:
    domain: str
    score: float  # 0.0 - 10.0
    issues: Tuple[Issue, ...] = field(default_factory=tuple)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        if not isinstance(self.issues, tuple):
            object.__setattr__(self, 'issues', tuple(self.issues))

class BaseEvaluator(ABC):
    """
    Abstract Base Class for all evaluator modules (e.g., SEO, Accessibility, PageSpeed).
    """
    @abstractmethod
    async def evaluate(self, html: str, url: str, client: Optional[Any] = None, allow_private: bool = False, **kwargs) -> EvaluationResult:
        """
        Executes the evaluation logic on the provided HTML content and URL.
        """
        pass

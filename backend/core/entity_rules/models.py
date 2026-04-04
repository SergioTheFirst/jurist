"""Shared models for the rule-based entity refinement pipeline."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal


DecisionVerdict = Literal["accept", "review", "reject"]


@dataclass(frozen=True)
class EntitySpan:
    """Candidate entity span before final overlap resolution."""

    id: str
    original: str
    placeholder: str
    entity_type: str
    start: int
    end: int
    source: str
    confidence: float
    identity_key: str | None = None
    metadata: dict[str, str] = field(default_factory=dict)

    @property
    def coverage(self) -> int:
        """Return candidate length in characters."""

        return self.end - self.start


@dataclass(frozen=True)
class RuleDecision:
    """Validation decision produced by a rule engine."""

    verdict: DecisionVerdict
    score: float
    reason: str
    model_confidence: float = 0.0
    context_bonus: float = 0.0
    penalty: float = 0.0

    @property
    def accepted(self) -> bool:
        """Return True when the candidate may be anonymized automatically."""

        return self.verdict == "accept"

    @property
    def reviewable(self) -> bool:
        """Return True when the candidate should be shown to the lawyer for review."""

        return self.verdict == "review"


@dataclass(frozen=True)
class ReviewCandidate:
    """Borderline candidate that should be shown in preview but not auto-hidden."""

    original: str
    entity_type: str
    start: int
    end: int
    source: str
    confidence: float
    score: float
    reason: str
    model_confidence: float
    context_bonus: float
    penalty: float

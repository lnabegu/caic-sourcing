"""
ScoringConfig — dimension weights and profile management for source discovery.
"""
from __future__ import annotations

from typing import Dict, List, Optional

SCORING_DIMENSIONS: List[str] = [
    "event_specificity",
    "actionability",
    "accountability_signal",
    "community_proximity",
    "independence",
]

DEFAULT_PROFILES: Dict[str, Dict[str, float]] = {
    "default": {
        "event_specificity": 0.25,
        "actionability": 0.20,
        "accountability_signal": 0.20,
        "community_proximity": 0.20,
        "independence": 0.15,
    },
    "accountability": {
        "event_specificity": 0.15,
        "actionability": 0.10,
        "accountability_signal": 0.45,
        "community_proximity": 0.15,
        "independence": 0.15,
    },
    "community": {
        "event_specificity": 0.20,
        "actionability": 0.25,
        "accountability_signal": 0.10,
        "community_proximity": 0.35,
        "independence": 0.10,
    },
    "climate": {
        "event_specificity": 0.35,
        "actionability": 0.15,
        "accountability_signal": 0.20,
        "community_proximity": 0.15,
        "independence": 0.15,
    },
    "actionable": {
        "event_specificity": 0.15,
        "actionability": 0.40,
        "accountability_signal": 0.15,
        "community_proximity": 0.20,
        "independence": 0.10,
    },
}


class ScoringConfig:
    """Manages scoring profiles and weight resolution."""

    def __init__(self, extra_profiles: Optional[Dict[str, Dict[str, float]]] = None):
        self._profiles: Dict[str, Dict[str, float]] = {**DEFAULT_PROFILES}
        if extra_profiles:
            for name, weights in extra_profiles.items():
                self._validate_weights(weights)
                self._profiles[name] = dict(weights)

    def resolve(
        self,
        profile: str = "default",
        overrides: Optional[Dict[str, float]] = None,
    ) -> Dict[str, float]:
        """
        Return resolved weights for a profile, applying overrides then re-normalising
        so weights always sum to 1.0.
        """
        if profile not in self._profiles:
            raise ValueError(
                f"Unknown profile '{profile}'. Available: {list(self._profiles)}"
            )
        weights = dict(self._profiles[profile])

        if overrides:
            for dim, val in overrides.items():
                if dim not in SCORING_DIMENSIONS:
                    raise ValueError(
                        f"Unknown dimension '{dim}'. Valid: {SCORING_DIMENSIONS}"
                    )
                weights[dim] = val

        # Re-normalise
        total = sum(weights.values())
        if total == 0:
            raise ValueError("Weights sum to zero after applying overrides.")
        return {dim: w / total for dim, w in weights.items()}

    def list_profiles(self) -> Dict[str, Dict[str, float]]:
        """Return all available profiles."""
        return {name: dict(w) for name, w in self._profiles.items()}

    @staticmethod
    def _validate_weights(weights: Dict[str, float]) -> None:
        for dim in weights:
            if dim not in SCORING_DIMENSIONS:
                raise ValueError(
                    f"Unknown dimension '{dim}'. Valid: {SCORING_DIMENSIONS}"
                )
        total = sum(weights.values())
        if abs(total - 1.0) > 1e-6:
            raise ValueError(
                f"Weights must sum to 1.0, got {total:.6f}."
            )


# Module-level singleton used by routes
default_scoring_config = ScoringConfig()
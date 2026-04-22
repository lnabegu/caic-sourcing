"""Unit tests for ScoringConfig."""
import pytest

from src.source_discovery.config import (
    DEFAULT_PROFILES,
    SCORING_DIMENSIONS,
    ScoringConfig,
)


def test_resolve_default_weights_sum_to_one():
    cfg = ScoringConfig()
    weights = cfg.resolve("default")
    assert abs(sum(weights.values()) - 1.0) < 1e-9


def test_all_default_profiles_sum_to_one():
    cfg = ScoringConfig()
    for name in DEFAULT_PROFILES:
        weights = cfg.resolve(name)
        assert abs(sum(weights.values()) - 1.0) < 1e-9, f"Profile '{name}' doesn't sum to 1"


def test_overrides_renormalize():
    cfg = ScoringConfig()
    # Force one dimension to a large value; result must still sum to 1.0
    weights = cfg.resolve("default", overrides={"event_specificity": 5.0})
    assert abs(sum(weights.values()) - 1.0) < 1e-9


def test_unknown_profile_raises():
    cfg = ScoringConfig()
    with pytest.raises(ValueError, match="Unknown profile"):
        cfg.resolve("nonexistent_profile")


def test_unknown_dimension_in_overrides_raises():
    cfg = ScoringConfig()
    with pytest.raises(ValueError, match="Unknown dimension"):
        cfg.resolve("default", overrides={"made_up_dim": 0.5})


def test_extra_profiles_injected_at_init():
    extra = {
        "my_profile": {dim: 1.0 / len(SCORING_DIMENSIONS) for dim in SCORING_DIMENSIONS}
    }
    cfg = ScoringConfig(extra_profiles=extra)
    profiles = cfg.list_profiles()
    assert "my_profile" in profiles
    weights = cfg.resolve("my_profile")
    assert abs(sum(weights.values()) - 1.0) < 1e-9


def test_extra_profile_with_bad_weights_raises():
    extra = {"bad": {"event_specificity": 0.5}}  # doesn't sum to 1
    with pytest.raises(ValueError, match="sum to 1.0"):
        ScoringConfig(extra_profiles=extra)


def test_list_profiles_returns_all_defaults():
    cfg = ScoringConfig()
    profiles = cfg.list_profiles()
    for name in DEFAULT_PROFILES:
        assert name in profiles


def test_custom_weights_via_full_override_not_needed_in_config():
    """ScoringConfig.resolve doesn't handle custom_weights — that's the router's job."""
    cfg = ScoringConfig()
    # Providing overrides for all dimensions effectively replaces weights
    full_overrides = {dim: 1.0 for dim in SCORING_DIMENSIONS}
    weights = cfg.resolve("default", overrides=full_overrides)
    # Should normalise to equal weights
    expected = 1.0 / len(SCORING_DIMENSIONS)
    for v in weights.values():
        assert abs(v - expected) < 1e-9

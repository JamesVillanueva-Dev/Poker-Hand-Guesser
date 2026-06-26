from __future__ import annotations

from engine.hand_classes import HAND_CLASSES, normalize, uniform_distribution
from engine.likelihood import HeuristicLikelihood
from engine.range_engine import RangeEstimator
from engine.state import ActionType, BoardState, PlayerProfile, PokerAction, Street


def test_starting_hand_classes_count() -> None:
    assert len(HAND_CLASSES) == 169
    assert "AA" in HAND_CLASSES
    assert "AKs" in HAND_CLASSES
    assert "72o" in HAND_CLASSES


def test_distribution_normalizes_to_one() -> None:
    distribution = normalize({"AA": 10.0, "KK": 5.0})
    assert abs(sum(distribution.values()) - 1.0) < 1e-9
    assert len(distribution) == 169


def test_bayesian_update_keeps_distribution_valid() -> None:
    estimator = RangeEstimator(likelihood_model=HeuristicLikelihood())
    action = PokerAction(
        player_id="villain",
        action_type=ActionType.RAISE,
        street=Street.PREFLOP,
        position="UTG",
        amount=3.0,
        pot_before=1.5,
        bet_fraction_pot=2.0,
    )
    updated = estimator.update_range(uniform_distribution(), action, BoardState(), PlayerProfile(player_id="villain"))
    assert abs(sum(updated.values()) - 1.0) < 1e-9
    assert updated["AA"] > updated["72o"]

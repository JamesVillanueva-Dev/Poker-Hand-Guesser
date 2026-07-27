"""No postflop code path may consult the preflop ranking (§1, principle 1).

A grep proves this today; this test proves it tomorrow. It replaces
`hand_strength_bucket` with a landmine and then runs the whole postflop stack.
"""

from __future__ import annotations

import pytest

import engine.hand_classes as hand_classes
import engine.likelihood as likelihood
import engine.strategy as strategy
from engine.range_engine import RangeEstimator
from engine.state import ActionType, BoardState, PlayerProfile, PokerAction, Street

BOARD = ["Ks", "7d", "2c"]


@pytest.fixture
def landmine(monkeypatch: pytest.MonkeyPatch) -> None:
    def explode(hand_class: str) -> float:
        raise AssertionError(f"postflop code consulted the preflop ranking for {hand_class}")

    monkeypatch.setattr(hand_classes, "hand_strength_bucket", explode)
    monkeypatch.setattr(likelihood, "hand_strength_bucket", explode)
    monkeypatch.setattr(strategy, "hand_strength_bucket", explode)


def test_postflop_range_update_never_uses_the_preflop_ranking(landmine: None) -> None:
    estimator = RangeEstimator()
    board_state = BoardState(street=Street.FLOP, board_cards=BOARD, hero_cards=["Ah", "Qd"], pot=10.0)
    action = PokerAction("v", ActionType.BET, Street.FLOP, "BTN", amount=9.0, pot_before=10.0, bet_fraction_pot=0.9)
    prior = {hand: 1.0 / 169 for hand in hand_classes.HAND_CLASSES}

    posterior = estimator.update_range(prior, action, board_state, PlayerProfile("v"))
    assert abs(sum(posterior.values()) - 1.0) < 1e-9


def test_postflop_recommendation_never_uses_the_preflop_ranking(landmine: None) -> None:
    board_state = BoardState(
        street=Street.RIVER,
        board_cards=[*BOARD, "Jh", "4s"],
        hero_cards=["Kh", "Qd"],
        pot=20.0,
        effective_stack=80.0,
    )
    recommendation = strategy.recommend_move(
        {hand: 1.0 / 169 for hand in hand_classes.HAND_CLASSES}, board_state, PlayerProfile("v")
    )
    assert recommendation.action in {"check", "bet", "call", "raise", "fold"}
    assert recommendation.range_composition


def test_preflop_is_the_one_place_the_ranking_is_still_allowed() -> None:
    """It is kept deliberately: before the flop there is no board to rank against."""
    strength, draw = likelihood.hand_features("AA", BoardState(street=Street.PREFLOP))
    assert strength == hand_classes.hand_strength_bucket("AA")
    assert draw == 0.0

"""Recommendations must reflect the board-aware engine, not a threshold cascade (§6)."""

from __future__ import annotations

from engine.hand_classes import normalize, uniform_distribution
from engine.range_engine import RangeEstimator
from engine.state import ActionType, BoardState, PlayerProfile, PokerAction, Street
from engine.strategy import recommend_move

PROFILE = PlayerProfile("villain")


def _board(board: list[str], hero: list[str], pot: float = 10.0, stack: float = 100.0) -> BoardState:
    return BoardState(
        street=Street.FLOP if len(board) == 3 else Street.RIVER if len(board) == 5 else Street.TURN,
        board_cards=board,
        hero_cards=hero,
        pot=pot,
        effective_stack=stack,
    )


def _opponent_bet(amount: float, pot: float) -> PokerAction:
    return PokerAction(
        player_id="villain",
        action_type=ActionType.BET,
        street=Street.FLOP,
        position="BTN",
        amount=amount,
        pot_before=pot,
        bet_fraction_pot=amount / pot,
        sequence=1,
    )


def test_a_flopped_set_bets_and_air_facing_a_big_bet_folds() -> None:
    board = ["Ks", "7d", "2c"]
    range_estimate = RangeEstimator().initial_distribution(board)

    strong = recommend_move(range_estimate, _board(board, ["7h", "7c"]), PROFILE)
    assert strong.action in {"bet", "raise"}
    assert strong.expected_value_bb > 0

    weak = recommend_move(
        range_estimate,
        _board(board, ["5h", "4d"], pot=40.0),
        PROFILE,
        _opponent_bet(30.0, 10.0),
    )
    assert weak.action == "fold"
    assert weak.expected_value_bb == 0.0


def test_reasons_cite_board_relative_facts_not_abstract_scores() -> None:
    board = ["9s", "8s", "2h"]
    recommendation = recommend_move(
        RangeEstimator().initial_distribution(board), _board(board, ["Ah", "Kd"]), PROFILE
    )
    joined = " ".join(recommendation.reasons)
    assert "on this board the opponent's range is" in joined.lower()
    assert recommendation.range_composition
    assert set(recommendation.range_composition) & {"top pair", "air", "set", "two pair", "flush draw", "straight draw"}
    assert "/100" not in joined, "the old abstract 0-100 scores are gone"


def test_every_line_is_priced_and_the_best_one_is_chosen() -> None:
    board = ["Ks", "7d", "2c"]
    recommendation = recommend_move(
        RangeEstimator().initial_distribution(board), _board(board, ["Kh", "Kc"]), PROFILE
    )
    assert len(recommendation.ev_breakdown) >= 4
    best = max(entry["expected_value_bb"] for entry in recommendation.ev_breakdown)
    assert recommendation.expected_value_bb == best
    assert any("expected value" in reason for reason in recommendation.reasons)


def test_hero_equity_drives_the_call_decision_not_a_threshold() -> None:
    """Same hero hand, same price, different opponent range: different answer."""
    board = ["Ks", "7d", "2c"]
    hero = ["Kh", "Qd"]  # top pair
    wide = uniform_distribution()
    narrow = normalize({"KK": 1.0, "77": 1.0, "22": 1.0})

    facing = _opponent_bet(8.0, 10.0)
    against_wide = recommend_move(wide, _board(board, hero, pot=18.0), PROFILE, facing)
    against_sets = recommend_move(narrow, _board(board, hero, pot=18.0), PROFILE, facing)
    assert against_wide.expected_value_bb > against_sets.expected_value_bb
    assert against_sets.action == "fold"


def test_confidence_is_labeled_when_it_has_not_been_measured() -> None:
    board = ["Ks", "7d", "2c"]
    unmeasured = recommend_move(
        RangeEstimator().initial_distribution(board), _board(board, ["Ah", "Kd"]), PROFILE
    )
    assert "unvalidated" in unmeasured.confidence_basis
    assert unmeasured.confidence == 0.5

    measured = recommend_move(
        RangeEstimator().initial_distribution(board),
        _board(board, ["Ah", "Kd"]),
        PROFILE,
        measured_skill=2.3,
        scored_showdowns=47,
    )
    assert "47 scored showdowns" in measured.confidence_basis
    assert measured.confidence > 0.5

    losing = recommend_move(
        RangeEstimator().initial_distribution(board),
        _board(board, ["Ah", "Kd"]),
        PROFILE,
        measured_skill=-1.8,
        scored_showdowns=12,
    )
    assert losing.confidence < 0.5, "a model that is losing must not report high confidence"


def test_preflop_still_produces_a_recommendation() -> None:
    recommendation = recommend_move(
        uniform_distribution(),
        BoardState(street=Street.PREFLOP, hero_cards=["Ah", "As"], pot=1.5, effective_stack=100.0),
        PROFILE,
    )
    assert recommendation.action in {"check", "bet", "call", "raise", "fold"}
    assert recommendation.reasons


def test_recommendation_survives_missing_hero_cards() -> None:
    board = ["Ks", "7d", "2c"]
    recommendation = recommend_move(RangeEstimator().initial_distribution(board), _board(board, []), PROFILE)
    assert recommendation.action in {"check", "bet", "call", "raise", "fold"}
    assert "unknown cards" in " ".join(recommendation.reasons)

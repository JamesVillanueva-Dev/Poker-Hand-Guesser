"""The policy is a normalized distribution, and it matches the stats it claims (§3).

The calibration invariant is the single test that keeps this honest: if the policy is
right, aggregating it over the opponent's whole range must reproduce that opponent's
observed frequencies.
"""

from __future__ import annotations

import pytest

from engine.likelihood import PolicyLikelihood, aggregate_action_frequency, legal_actions
from engine.range_engine import RangeEstimator
from engine.state import AGGRESSIVE_ACTIONS, ActionType, BoardState, PlayerProfile, PokerAction, Street

TOLERANCE = 0.05  # five percentage points

PROFILES: dict[str, PlayerProfile] = {
    "nit": PlayerProfile("nit", vpip=0.13, pfr=0.10, three_bet=0.03, fold_to_three_bet=0.72, cbet=0.45, aggression=1.1, bluff_frequency=0.09),
    "tag": PlayerProfile("tag", vpip=0.24, pfr=0.19, three_bet=0.07, fold_to_three_bet=0.52, cbet=0.60, aggression=2.0, bluff_frequency=0.22),
    "lag": PlayerProfile("lag", vpip=0.38, pfr=0.30, three_bet=0.13, fold_to_three_bet=0.38, cbet=0.72, aggression=2.9, bluff_frequency=0.34),
    "maniac": PlayerProfile("maniac", vpip=0.62, pfr=0.50, three_bet=0.22, fold_to_three_bet=0.22, cbet=0.85, aggression=4.2, bluff_frequency=0.50),
}

BOARDS: dict[str, list[str]] = {
    "dry": ["Ks", "7d", "2c"],
    "wet": ["9s", "8s", "2h"],
    "monotone": ["As", "Ks", "Qs"],
    "paired": ["2h", "2d", "7c"],
}

VOLUNTARY = frozenset(AGGRESSIVE_ACTIONS | {ActionType.CALL})


def _preflop_open(profile: PlayerProfile) -> tuple[RangeEstimator, dict, BoardState, list, object]:
    estimator = RangeEstimator()
    board_state = BoardState(street=Street.PREFLOP, pot=1.5)
    action = PokerAction("v", ActionType.RAISE, Street.PREFLOP, "BTN", amount=3.0, pot_before=1.5, bet_fraction_pot=2.0)
    prior = estimator.initial_distribution()
    context, legal, _ = estimator.policy_snapshot(prior, board_state, profile, action)
    return estimator, prior, board_state, legal, context


@pytest.mark.parametrize("name", list(PROFILES))
def test_action_probabilities_sum_to_one_for_every_hand_class(name: str) -> None:
    profile = PROFILES[name]
    model = PolicyLikelihood()
    estimator = RangeEstimator(model)
    board_state = BoardState(street=Street.FLOP, board_cards=BOARDS["wet"], pot=8.0)
    action = PokerAction("v", ActionType.BET, Street.FLOP, "BTN", amount=6.0, pot_before=8.0, bet_fraction_pot=0.75)
    _, legal, policies = estimator.policy_snapshot(estimator.initial_distribution(BOARDS["wet"]), board_state, profile, action)
    for hand, probabilities in policies.items():
        assert abs(sum(probabilities.values()) - 1.0) < 1e-9, hand
        assert all(probability > 0.0 for probability in probabilities.values()), hand


@pytest.mark.parametrize("name", list(PROFILES))
def test_vpip_and_pfr_match_the_profile(name: str) -> None:
    profile = PROFILES[name]
    model = PolicyLikelihood()
    _, prior, board_state, legal, context = _preflop_open(profile)

    vpip = aggregate_action_frequency(model, prior, legal, board_state, profile, context, VOLUNTARY)
    pfr = aggregate_action_frequency(model, prior, legal, board_state, profile, context, AGGRESSIVE_ACTIONS)
    assert abs(vpip - profile.vpip) < TOLERANCE, f"{name}: vpip {vpip:.3f} vs {profile.vpip:.3f}"
    assert abs(pfr - profile.pfr) < TOLERANCE, f"{name}: pfr {pfr:.3f} vs {profile.pfr:.3f}"


@pytest.mark.parametrize("name", list(PROFILES))
def test_three_bet_frequency_matches_the_profile(name: str) -> None:
    profile = PROFILES[name]
    model = PolicyLikelihood()
    estimator = RangeEstimator(model)
    opening_raise = PokerAction(
        "hero", ActionType.RAISE, Street.PREFLOP, "CO", amount=3.0, pot_before=1.5, bet_fraction_pot=2.0, sequence=0
    )
    board_state = BoardState(street=Street.PREFLOP, pot=4.5, previous_actions=[opening_raise])
    action = PokerAction(
        "v", ActionType.THREE_BET, Street.PREFLOP, "BTN", amount=10.0, pot_before=4.5, bet_fraction_pot=2.2, sequence=1
    )
    prior = estimator.initial_distribution()
    context, legal, _ = estimator.policy_snapshot(prior, board_state, profile, action)
    assert ActionType.THREE_BET in legal

    three_bet = aggregate_action_frequency(model, prior, legal, board_state, profile, context, AGGRESSIVE_ACTIONS)
    assert abs(three_bet - profile.three_bet) < TOLERANCE, f"{name}: 3bet {three_bet:.3f} vs {profile.three_bet:.3f}"


@pytest.mark.parametrize("name", list(PROFILES))
@pytest.mark.parametrize("texture", list(BOARDS))
def test_cbet_frequency_matches_the_profile_on_every_texture(name: str, texture: str) -> None:
    profile = PROFILES[name]
    board = BOARDS[texture]
    model = PolicyLikelihood()
    estimator = RangeEstimator(model)
    preflop_raise = PokerAction(
        "v", ActionType.RAISE, Street.PREFLOP, "BTN", amount=3.0, pot_before=1.5, bet_fraction_pot=2.0, sequence=0
    )
    board_state = BoardState(street=Street.FLOP, board_cards=board, pot=7.0, previous_actions=[preflop_raise])
    action = PokerAction(
        "v", ActionType.BET, Street.FLOP, "BTN", amount=4.5, pot_before=7.0, bet_fraction_pot=0.64, sequence=1
    )
    prior = estimator.initial_distribution(board)
    context, legal, _ = estimator.policy_snapshot(prior, board_state, profile, action)
    assert context.opponent_is_preflop_aggressor

    cbet = aggregate_action_frequency(model, prior, legal, board_state, profile, context, AGGRESSIVE_ACTIONS)
    assert abs(cbet - profile.cbet) < TOLERANCE, f"{name}/{texture}: cbet {cbet:.3f} vs {profile.cbet:.3f}"


def test_legal_actions_are_real() -> None:
    from engine.state import ActionContext

    checked_to = ActionContext(street=Street.FLOP, facing_bet=False)
    assert ActionType.FOLD not in legal_actions(checked_to), "you cannot fold when nobody bet"
    assert ActionType.CALL not in legal_actions(checked_to)

    facing = ActionContext(street=Street.FLOP, facing_bet=True, raise_level=1)
    assert ActionType.CHECK not in legal_actions(facing), "you cannot check facing a bet"
    assert ActionType.FOLD in legal_actions(facing)

    unopened = ActionContext(street=Street.PREFLOP, raise_level=0)
    assert ActionType.THREE_BET not in legal_actions(unopened), "no three-bet without a raise in front"
    opened = ActionContext(street=Street.PREFLOP, raise_level=1)
    assert ActionType.THREE_BET in legal_actions(opened)
    assert ActionType.RAISE not in legal_actions(opened)


def test_an_unexpected_observed_action_is_still_scored() -> None:
    from engine.state import ActionContext

    checked_to = ActionContext(street=Street.FLOP, facing_bet=False)
    assert ActionType.FOLD in legal_actions(checked_to, observed=ActionType.FOLD)


def test_semi_bluffs_bet_more_than_pure_air() -> None:
    """The distinction a board-blind model cannot make, and most of postflop poker."""
    profile = PROFILES["tag"]
    model = PolicyLikelihood()
    estimator = RangeEstimator(model)
    board = BOARDS["wet"]
    board_state = BoardState(street=Street.FLOP, board_cards=board, pot=7.0)
    action = PokerAction("v", ActionType.BET, Street.FLOP, "BTN", amount=5.0, pot_before=7.0, bet_fraction_pot=0.7)
    _, _, policies = estimator.policy_snapshot(estimator.initial_distribution(board), board_state, profile, action)

    draw = policies["JTs"][ActionType.BET]  # open-ender plus backdoor spades
    air = policies["K4o"][ActionType.BET]  # no pair, no draw
    assert draw > air * 1.5, f"draw {draw:.3f} vs air {air:.3f}"


def test_a_large_bet_is_more_polarizing_than_a_small_one() -> None:
    profile = PROFILES["tag"]
    model = PolicyLikelihood()
    estimator = RangeEstimator(model)
    board = BOARDS["dry"]
    board_state = BoardState(street=Street.FLOP, board_cards=board, pot=7.0)

    def value_share(fraction: float) -> float:
        action = PokerAction(
            "v", ActionType.BET, Street.FLOP, "BTN", amount=7.0 * fraction, pot_before=7.0, bet_fraction_pot=fraction
        )
        prior = estimator.initial_distribution(board)
        posterior = estimator.update_range(prior, action, board_state, profile)
        return posterior["KK"] + posterior["77"] + posterior["22"]

    assert value_share(1.5) > value_share(0.25)

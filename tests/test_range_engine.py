from __future__ import annotations

from engine.hand_classes import HAND_CLASSES, distribution_entropy, hand_strength_bucket, normalize, uniform_distribution
from engine.likelihood import PolicyLikelihood
from engine.range_engine import RangeEstimator
from engine.state import ActionType, BoardState, PlayerProfile, PokerAction, Street

DRY_FLOP = ["Ks", "7d", "2c"]


def _bet(fraction: float = 0.9, street: Street = Street.FLOP, sequence: int = 1) -> PokerAction:
    return PokerAction(
        player_id="villain",
        action_type=ActionType.BET if street != Street.PREFLOP else ActionType.RAISE,
        street=street,
        position="BTN",
        amount=10.0 * fraction,
        pot_before=10.0,
        bet_fraction_pot=fraction,
        sequence=sequence,
    )


def test_starting_hand_classes_count() -> None:
    assert len(HAND_CLASSES) == 169
    assert "AA" in HAND_CLASSES
    assert "AKs" in HAND_CLASSES
    assert "72o" in HAND_CLASSES


def test_distribution_normalizes_to_one() -> None:
    distribution = normalize({"AA": 10.0, "KK": 5.0})
    assert abs(sum(distribution.values()) - 1.0) < 1e-9
    assert len(distribution) == 169


def test_preflop_ranking_is_sane_for_pairs() -> None:
    assert hand_strength_bucket("AA") > hand_strength_bucket("AKs") > hand_strength_bucket("AKo")
    assert hand_strength_bucket("77") > hand_strength_bucket("72o")
    assert abs(hand_strength_bucket("77") - hand_strength_bucket("AQo")) < 0.15


def test_bayesian_update_keeps_distribution_valid() -> None:
    estimator = RangeEstimator(likelihood_model=PolicyLikelihood())
    updated = estimator.update_range(
        uniform_distribution(),
        _bet(2.0, Street.PREFLOP, sequence=0),
        BoardState(pot=1.5),
        PlayerProfile(player_id="villain"),
    )
    assert abs(sum(updated.values()) - 1.0) < 1e-9
    assert updated["AA"] > updated["72o"]


def test_a_flopped_set_gains_weight_and_air_loses_it() -> None:
    """The flagship case: on K72, a large bet must favour 77 over AQo."""
    estimator = RangeEstimator()
    profile = PlayerProfile(player_id="villain")
    board_state = BoardState(street=Street.FLOP, board_cards=DRY_FLOP, pot=10.0)

    prior = estimator.initial_distribution(DRY_FLOP)
    assert prior["77"] < prior["AQo"], "77 starts behind: it has three live combos to AQo's twelve"

    posterior = estimator.update_range(prior, _bet(0.9), board_state, profile)
    assert posterior["77"] > posterior["AQo"]
    assert posterior["77"] / posterior["AQo"] > 2.0
    assert posterior["77"] / prior["77"] > posterior["AQo"] / prior["AQo"]


def test_two_pair_beats_a_broadway_overcard_on_a_low_board() -> None:
    """72o is two pair on K72. A preflop ranking calls it the worst hand in poker."""
    estimator = RangeEstimator()
    posterior = estimator.update_range(
        estimator.initial_distribution(DRY_FLOP),
        _bet(0.9),
        BoardState(street=Street.FLOP, board_cards=DRY_FLOP, pot=10.0),
        PlayerProfile(player_id="villain"),
    )
    assert posterior["72o"] > posterior["AQo"]


def test_updates_reduce_entropy() -> None:
    estimator = RangeEstimator()
    prior = estimator.initial_distribution(DRY_FLOP)
    posterior = estimator.update_range(
        prior, _bet(1.2), BoardState(street=Street.FLOP, board_cards=DRY_FLOP, pot=10.0), PlayerProfile("villain")
    )
    assert distribution_entropy(posterior) < distribution_entropy(prior)


def test_card_removal_is_applied_on_the_street_transition_only() -> None:
    estimator = RangeEstimator()
    prior = estimator.initial_distribution()
    board_state = BoardState(street=Street.FLOP, board_cards=DRY_FLOP, pot=10.0)

    once = estimator.update_range(prior, _bet(0.9), board_state, PlayerProfile("v"), previous_dead=[])
    twice = estimator.update_range(once, _bet(0.9, sequence=2), board_state, PlayerProfile("v"), previous_dead=DRY_FLOP)
    # Re-applying removal for an unchanged board would shrink 77 a second time.
    assert twice["77"] / twice["KQo"] > once["77"] / once["KQo"]


def test_blocked_classes_stay_at_zero_through_many_updates() -> None:
    estimator = RangeEstimator()
    board = ["As", "Ah", "Ad"]
    board_state = BoardState(street=Street.FLOP, board_cards=board, hero_cards=["Ac", "Kc"], pot=10.0)
    distribution = estimator.initial_distribution([*board, "Ac", "Kc"])
    assert distribution["AA"] == 0.0
    for sequence in range(4):
        distribution = estimator.update_range(
            distribution, _bet(0.7, sequence=sequence + 1), board_state, PlayerProfile("v")
        )
        assert distribution["AA"] == 0.0


def test_policy_snapshot_normalizes_for_every_class() -> None:
    estimator = RangeEstimator()
    _, legal, policies = estimator.policy_snapshot(
        estimator.initial_distribution(DRY_FLOP),
        BoardState(street=Street.FLOP, board_cards=DRY_FLOP, pot=10.0),
        PlayerProfile("v"),
        _bet(0.9),
    )
    assert len(policies) == 169
    for hand, probabilities in policies.items():
        assert abs(sum(probabilities.values()) - 1.0) < 1e-9, hand
        assert set(probabilities) == set(legal)

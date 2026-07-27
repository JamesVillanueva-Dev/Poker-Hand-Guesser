"""The profile must recover the parameters that generated the actions (§5)."""

from __future__ import annotations

import random
from dataclasses import dataclass

from backend.profile_stats import (
    build_observation,
    derive_rates,
    observe_action,
    observe_showdown,
    sample_sizes,
    shrunk_rate,
    start_hand,
)
from engine.state import ActionActor, ActionType, PlayerProfile, PokerAction, Street


@dataclass(frozen=True)
class Villain:
    vpip: float
    pfr: float
    cbet: float
    fold_to_three_bet: float


NIT = Villain(vpip=0.12, pfr=0.09, cbet=0.40, fold_to_three_bet=0.80)
MANIAC = Villain(vpip=0.70, pfr=0.55, cbet=0.85, fold_to_three_bet=0.20)


def simulate(villain: Villain, hands: int = 100, seed: int = 7) -> PlayerProfile:
    """Script `hands` hands from known generating parameters and recover the profile."""
    rng = random.Random(seed)
    profile = PlayerProfile("sim")

    for hand in range(hands):
        profile = start_hand(profile)
        history: list[PokerAction] = []
        sequence = 0

        def record(action_type: ActionType, street: Street, actor: ActionActor = ActionActor.OPPONENT, amount: float = 0.0) -> None:
            nonlocal profile, sequence
            action = PokerAction(
                player_id="sim",
                action_type=action_type,
                street=street,
                position="BTN",
                actor=actor,
                amount=amount,
                pot_before=max(1.5, amount * 2),
                sequence=sequence,
            )
            if actor == ActionActor.OPPONENT:
                profile = observe_action(profile, build_observation(action, history))
            history.append(action)
            sequence += 1

        roll = rng.random()
        if roll < villain.pfr:
            record(ActionType.RAISE, Street.PREFLOP, amount=3.0)
        elif roll < villain.vpip:
            record(ActionType.CALL, Street.PREFLOP, amount=1.0)
            continue
        else:
            record(ActionType.FOLD, Street.PREFLOP)
            continue

        # Hero three-bets a third of the time; the villain folds at its true rate.
        if rng.random() < 0.34:
            record(ActionType.RAISE, Street.PREFLOP, actor=ActionActor.HERO, amount=10.0)
            if rng.random() < villain.fold_to_three_bet:
                record(ActionType.FOLD, Street.PREFLOP)
                continue
            record(ActionType.CALL, Street.PREFLOP, amount=7.0)
        else:
            record(ActionType.CALL, Street.PREFLOP, actor=ActionActor.HERO, amount=2.0)

        if rng.random() < villain.cbet:
            record(ActionType.BET, Street.FLOP, amount=5.0)
        else:
            record(ActionType.CHECK, Street.FLOP)

    return profile


def test_hands_observed_counts_hands_not_actions() -> None:
    profile = simulate(MANIAC, hands=100)
    assert profile.hands_observed == 100
    assert profile.aggressive_actions + profile.passive_actions > 100


def test_vpip_and_pfr_converge_on_the_generating_parameters() -> None:
    for villain in (NIT, MANIAC):
        profile = simulate(villain, hands=200)
        assert profile.preflop_hands == 200
        assert abs(profile.vpip - villain.vpip) < 0.06, (villain, profile.vpip)
        assert abs(profile.pfr - villain.pfr) < 0.06, (villain, profile.pfr)

        longer = simulate(villain, hands=800)
        assert abs(longer.vpip - villain.vpip) < 0.02, (villain, longer.vpip)
        assert abs(longer.pfr - villain.pfr) < 0.02, (villain, longer.pfr)


def test_cbet_converges_from_the_prior_toward_the_truth() -> None:
    """Shrinkage means the estimate walks from the population prior to the truth."""
    for villain in (NIT, MANIAC):
        short = simulate(villain, hands=200)
        long = simulate(villain, hands=800)
        prior_gap = abs(0.55 - villain.cbet)
        assert abs(short.cbet - villain.cbet) < prior_gap, villain
        assert abs(long.cbet - villain.cbet) < abs(short.cbet - villain.cbet), villain
        assert abs(long.cbet - villain.cbet) < 0.06, (villain, long.cbet)

    assert simulate(NIT, hands=400).cbet < 0.55 < simulate(MANIAC, hands=400).cbet


def test_cbet_only_counts_flop_bets_as_the_preflop_aggressor() -> None:
    """A flop bet by a player who never raised preflop is a donk bet, not a cbet."""
    profile = PlayerProfile("d")
    limp = PokerAction("d", ActionType.CALL, Street.PREFLOP, "BB", amount=1.0, sequence=0)
    hero_raise = PokerAction("h", ActionType.RAISE, Street.PREFLOP, "BTN", actor=ActionActor.HERO, amount=3.0, sequence=1)
    donk = PokerAction("d", ActionType.BET, Street.FLOP, "BB", amount=4.0, sequence=2)
    profile = observe_action(profile, build_observation(limp, []))
    profile = observe_action(profile, build_observation(donk, [limp, hero_raise]))
    assert profile.cbet_opportunities == 0
    assert profile.cbet == 0.55  # untouched population prior


def test_fold_to_three_bet_is_actually_tracked() -> None:
    """The field used to be declared, stored, and never updated anywhere in the repo."""
    tight = simulate(NIT, hands=800)
    loose = simulate(MANIAC, hands=800)
    assert tight.three_bets_faced > 0 and loose.three_bets_faced > 0
    assert tight.fold_to_three_bet != 0.47, "the field must move, or it should not exist"
    assert abs(tight.fold_to_three_bet - NIT.fold_to_three_bet) < 0.06
    assert abs(loose.fold_to_three_bet - MANIAC.fold_to_three_bet) < 0.06
    assert loose.fold_to_three_bet < tight.fold_to_three_bet


def test_postflop_actions_do_not_touch_vpip() -> None:
    """The old bug: VPIP drifted toward 'fraction of all actions that were voluntary'."""
    profile = derive_rates(PlayerProfile("p"))
    baseline = profile.vpip
    history: list[PokerAction] = []
    for index in range(30):
        action = PokerAction("p", ActionType.CALL, Street.TURN, "BB", amount=5.0, sequence=index)
        profile = observe_action(profile, build_observation(action, history))
        history.append(action)
    assert profile.vpip == baseline
    assert profile.preflop_hands == 0


def test_bluff_frequency_comes_from_showdowns_not_bet_sizing() -> None:
    profile = derive_rates(PlayerProfile("b"))
    assert profile.bluff_frequency == 0.22

    caught = profile
    for _ in range(20):
        caught = observe_showdown(caught, was_aggressive=True, showdown_percentile=0.10)
    assert caught.bluff_frequency > 0.55
    assert caught.showdown_bluffs == 20

    honest = profile
    for _ in range(20):
        honest = observe_showdown(honest, was_aggressive=True, showdown_percentile=0.95)
    assert honest.bluff_frequency < 0.12
    assert honest.showdown_bluffs == 0


def test_shrinkage_stops_a_two_hand_sample_claiming_certainty() -> None:
    assert shrunk_rate(2, 2, 0.55) < 0.65
    assert shrunk_rate(200, 200, 0.55) > 0.94
    assert shrunk_rate(0, 0, 0.55) == 0.55


def test_sample_sizes_are_exposed() -> None:
    sizes = sample_sizes(simulate(NIT, hands=40))
    assert sizes["hands"] == 40
    assert sizes["preflop_hands"] == 40
    assert set(sizes) >= {"cbet_opportunities", "three_bets_faced", "showdowns"}

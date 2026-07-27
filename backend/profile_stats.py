"""Opponent statistics that mean what their names say.

Every rate is a numerator over the opportunities that actually created it, shrunk
toward a population prior with a Beta-Binomial pseudo-count so a two-hand sample
cannot produce a 100% cbet. The rate fields on `PlayerProfile` are always recomputed
from the counters; nothing blends a float toward a hardcoded constant any more.
"""

from __future__ import annotations

from dataclasses import dataclass, replace

from engine.state import (
    AGGRESSIVE_ACTIONS,
    VOLUNTARY_ACTIONS,
    ActionActor,
    ActionType,
    PlayerProfile,
    PokerAction,
    Street,
)

POPULATION_PRIORS: dict[str, float] = {
    "vpip": 0.24,
    "pfr": 0.16,
    "three_bet": 0.07,
    "fold_to_three_bet": 0.47,
    "cbet": 0.55,
    "bluff_frequency": 0.22,
    "showdown_frequency": 0.28,
}
PRIOR_WEIGHT: float = 12.0
AGGRESSION_PRIOR: float = 1.7
AGGRESSION_PRIOR_WEIGHT: float = 8.0
RIVER_AGGRESSION_PRIOR: float = 1.2
RIVER_PRIOR_WEIGHT: float = 6.0
BLUFF_PERCENTILE: float = 0.40


def shrunk_rate(count: int, opportunities: int, prior_mean: float, prior_weight: float = PRIOR_WEIGHT) -> float:
    """Beta-Binomial posterior mean. Small samples stay near the population prior."""
    return (count + prior_mean * prior_weight) / (opportunities + prior_weight)


@dataclass(frozen=True)
class ActionObservation:
    """One opponent action plus the facts about the spot that decide what it counts as."""

    action: PokerAction
    counts_preflop_hand: bool = False
    counts_vpip: bool = False
    counts_pfr: bool = False
    three_bet_opportunity: bool = False
    is_three_bet: bool = False
    faces_three_bet: bool = False
    cbet_opportunity: bool = False


def build_observation(action: PokerAction, prior_actions: list[PokerAction]) -> ActionObservation:
    """Derive what an action counts toward from the hand's action history."""
    own_history = [previous for previous in prior_actions if previous.actor == action.actor]
    own_preflop = [previous for previous in own_history if previous.street == Street.PREFLOP]
    voluntary = action.action_type in VOLUNTARY_ACTIONS
    raised = action.action_type in AGGRESSIVE_ACTIONS

    street_history = [previous for previous in prior_actions if previous.street == action.street]
    raises_before = [previous for previous in street_history if previous.action_type in AGGRESSIVE_ACTIONS]
    facing_raise = bool(raises_before) and raises_before[-1].actor != action.actor
    raises_in_front = [previous for previous in raises_before if previous.actor != action.actor]
    own_street_actions = [previous for previous in street_history if previous.actor == action.actor]

    preflop_aggressors = [
        previous
        for previous in prior_actions
        if previous.street == Street.PREFLOP and previous.action_type in AGGRESSIVE_ACTIONS
    ]
    is_preflop_aggressor = bool(preflop_aggressors) and preflop_aggressors[-1].actor == action.actor

    is_preflop = action.street == Street.PREFLOP
    return ActionObservation(
        action=action,
        counts_preflop_hand=is_preflop and not own_preflop,
        counts_vpip=is_preflop
        and voluntary
        and not any(previous.action_type in VOLUNTARY_ACTIONS for previous in own_preflop),
        counts_pfr=is_preflop
        and raised
        and not any(previous.action_type in AGGRESSIVE_ACTIONS for previous in own_preflop),
        three_bet_opportunity=is_preflop and len(raises_before) == 1 and facing_raise and not own_street_actions,
        is_three_bet=is_preflop and raised and len(raises_before) == 1 and facing_raise,
        faces_three_bet=is_preflop and len(raises_before) >= 2 and facing_raise,
        cbet_opportunity=(
            action.street == Street.FLOP and is_preflop_aggressor and not raises_in_front and not own_street_actions
        ),
    )


def observe_action(profile: PlayerProfile, observation: ActionObservation) -> PlayerProfile:
    """Fold one opponent action into the counters, then re-derive the rates."""
    action = observation.action
    if action.actor != ActionActor.OPPONENT:
        return profile

    aggressive = action.action_type in AGGRESSIVE_ACTIONS
    passive = action.action_type in {ActionType.CALL, ActionType.CHECK}
    updated = replace(
        profile,
        preflop_hands=profile.preflop_hands + int(observation.counts_preflop_hand),
        vpip_count=profile.vpip_count + int(observation.counts_vpip),
        pfr_count=profile.pfr_count + int(observation.counts_pfr),
        three_bet_opportunities=profile.three_bet_opportunities + int(observation.three_bet_opportunity),
        three_bet_count=profile.three_bet_count + int(observation.is_three_bet),
        three_bets_faced=profile.three_bets_faced + int(observation.faces_three_bet),
        three_bet_folds=profile.three_bet_folds
        + int(observation.faces_three_bet and action.action_type == ActionType.FOLD),
        cbet_opportunities=profile.cbet_opportunities + int(observation.cbet_opportunity),
        cbet_count=profile.cbet_count + int(observation.cbet_opportunity and aggressive),
        aggressive_actions=profile.aggressive_actions + int(aggressive),
        passive_actions=profile.passive_actions + int(passive),
        river_actions=profile.river_actions + int(action.street == Street.RIVER and (aggressive or passive)),
        river_aggressive_actions=profile.river_aggressive_actions
        + int(action.street == Street.RIVER and aggressive),
        showdown_opportunities=profile.showdown_opportunities + int(action.action_type == ActionType.FOLD),
    )
    return derive_rates(updated)


def start_hand(profile: PlayerProfile) -> PlayerProfile:
    """`hands_observed` counts hands, not actions."""
    return derive_rates(replace(profile, hands_observed=profile.hands_observed + 1))


def observe_showdown(
    profile: PlayerProfile,
    was_aggressive: bool,
    showdown_percentile: float | None,
) -> PlayerProfile:
    """Ground truth. A bluff is an opponent who bet or raised and then tabled a weak hand."""
    bluffed = bool(was_aggressive and showdown_percentile is not None and showdown_percentile < BLUFF_PERCENTILE)
    updated = replace(
        profile,
        showdowns_seen=profile.showdowns_seen + 1,
        showdown_opportunities=profile.showdown_opportunities + 1,
        showdown_aggressive_hands=profile.showdown_aggressive_hands + int(was_aggressive),
        showdown_bluffs=profile.showdown_bluffs + int(bluffed),
    )
    return derive_rates(updated)


def derive_rates(profile: PlayerProfile) -> PlayerProfile:
    """Recompute every rate field from the counters. The single source of truth."""
    return replace(
        profile,
        vpip=shrunk_rate(profile.vpip_count, profile.preflop_hands, POPULATION_PRIORS["vpip"]),
        pfr=shrunk_rate(profile.pfr_count, profile.preflop_hands, POPULATION_PRIORS["pfr"]),
        three_bet=shrunk_rate(
            profile.three_bet_count, profile.three_bet_opportunities, POPULATION_PRIORS["three_bet"]
        ),
        fold_to_three_bet=shrunk_rate(
            profile.three_bet_folds, profile.three_bets_faced, POPULATION_PRIORS["fold_to_three_bet"]
        ),
        cbet=shrunk_rate(profile.cbet_count, profile.cbet_opportunities, POPULATION_PRIORS["cbet"]),
        bluff_frequency=shrunk_rate(
            profile.showdown_bluffs, profile.showdown_aggressive_hands, POPULATION_PRIORS["bluff_frequency"]
        ),
        showdown_frequency=shrunk_rate(
            profile.showdowns_seen, profile.showdown_opportunities, POPULATION_PRIORS["showdown_frequency"]
        ),
        aggression=(profile.aggressive_actions + AGGRESSION_PRIOR * AGGRESSION_PRIOR_WEIGHT)
        / (profile.passive_actions + AGGRESSION_PRIOR_WEIGHT),
        river_aggression=(profile.river_aggressive_actions + RIVER_AGGRESSION_PRIOR * RIVER_PRIOR_WEIGHT)
        / (max(0, profile.river_actions - profile.river_aggressive_actions) + RIVER_PRIOR_WEIGHT),
    )


def sample_sizes(profile: PlayerProfile) -> dict[str, int]:
    """Denominators, so the frontend can tell a 4-hand read from a 400-hand read."""
    return {
        "hands": profile.hands_observed,
        "preflop_hands": profile.preflop_hands,
        "three_bet_opportunities": profile.three_bet_opportunities,
        "three_bets_faced": profile.three_bets_faced,
        "cbet_opportunities": profile.cbet_opportunities,
        "postflop_actions": profile.aggressive_actions + profile.passive_actions,
        "showdowns": profile.showdowns_seen,
        "showdown_aggressive_hands": profile.showdown_aggressive_hands,
    }

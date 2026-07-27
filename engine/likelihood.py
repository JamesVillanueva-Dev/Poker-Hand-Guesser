"""The opponent's action policy.

`P(action | hand class, board, profile, context)` is built as a set of utility logits
that are turned into a probability distribution over the *legal* action set by a
softmax, so it always sums to 1. Postflop, the only strength signal it consumes is the
board-relative percentile from `engine.evaluator`; the preflop ranking is used preflop
and nowhere else.

Where a real observed statistic exists for a spot (VPIP, PFR, 3bet, cbet), the policy
is calibrated to it: two scalar tilts are solved by bisection so that aggregating the
policy over the modeled range reproduces the opponent's measured frequency. The poker
logic decides *which* hands take an action; the observed stat decides *how often*.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from math import exp
from typing import Protocol

from engine.evaluator import HandStrength, board_strength
from engine.hand_classes import hand_strength_bucket
from engine.state import (
    AGGRESSIVE_ACTIONS,
    ActionContext,
    ActionType,
    BoardState,
    PlayerProfile,
    PokerAction,
    Street,
    build_action_context,
)

VOLUNTARY = frozenset(AGGRESSIVE_ACTIONS | {ActionType.CALL})


class LikelihoodModel(Protocol):
    def action_probabilities(
        self,
        hand_class: str,
        legal: list[ActionType],
        board_state: BoardState,
        profile: PlayerProfile,
        context: ActionContext,
    ) -> dict[ActionType, float]:
        ...

    def calibrate(
        self,
        prior: dict[str, float],
        legal: list[ActionType],
        board_state: BoardState,
        profile: PlayerProfile,
        context: ActionContext,
    ) -> ActionContext:
        ...


def legal_actions(context: ActionContext, observed: ActionType | None = None) -> list[ActionType]:
    """The actions that are actually available in this spot."""
    if context.street == Street.PREFLOP:
        if context.raise_level == 0:
            actions = [ActionType.FOLD, ActionType.CHECK, ActionType.CALL, ActionType.RAISE, ActionType.JAM]
        elif context.raise_level == 1:
            actions = [ActionType.FOLD, ActionType.CALL, ActionType.THREE_BET, ActionType.JAM]
        elif context.raise_level == 2:
            actions = [ActionType.FOLD, ActionType.CALL, ActionType.FOUR_BET, ActionType.JAM]
        else:
            actions = [ActionType.FOLD, ActionType.CALL, ActionType.JAM]
    elif context.facing_bet:
        actions = [ActionType.FOLD, ActionType.CALL, ActionType.RAISE, ActionType.JAM]
    else:
        actions = [ActionType.CHECK, ActionType.BET, ActionType.JAM]

    if observed is not None and observed not in actions:
        # Never silently drop an action the user actually observed: scoring an
        # unexpected action is better than crashing or normalizing it away.
        actions = [*actions, observed]
    return actions


def _softmax(logits: dict[ActionType, float], temperature: float, floor: float) -> dict[ActionType, float]:
    largest = max(logits.values())
    weights = {action: exp((logit - largest) / temperature) for action, logit in logits.items()}
    total = sum(weights.values())
    count = len(weights)
    return {action: (1.0 - floor) * weight / total + floor / count for action, weight in weights.items()}


@dataclass
class PolicyLikelihood:
    """Board-aware, normalized action policy."""

    temperature: float = 1.0
    exploration_floor: float = 0.02

    # ---------------------------------------------------------------- public API

    def action_probabilities(
        self,
        hand_class: str,
        legal: list[ActionType],
        board_state: BoardState,
        profile: PlayerProfile,
        context: ActionContext,
    ) -> dict[ActionType, float]:
        logits = self._logits(hand_class, legal, board_state, profile, context)
        return _softmax(logits, self.temperature, self.exploration_floor)

    def calibrate(
        self,
        prior: dict[str, float],
        legal: list[ActionType],
        board_state: BoardState,
        profile: PlayerProfile,
        context: ActionContext,
    ) -> ActionContext:
        """Solve the two tilts so range-aggregated frequencies match observed stats."""
        continue_target, aggressive_target = calibration_targets(profile, context)
        if continue_target is None and aggressive_target is None:
            return context

        neutral = replace(context, continue_tilt=0.0, aggression_tilt=0.0)
        base = {
            hand: self._logits(hand, legal, board_state, profile, neutral)
            for hand, weight in prior.items()
            if weight > 0.0
        }
        weights = {hand: prior[hand] for hand in base}
        total_weight = sum(weights.values())
        if total_weight <= 0.0:
            return context

        continue_tilt = 0.0
        aggression_tilt = 0.0
        for _ in range(3):
            if continue_target is not None:
                continue_tilt = _solve_tilt(
                    base, weights, total_weight, VOLUNTARY, continue_target, continue_tilt, aggression_tilt, self
                )
            if aggressive_target is not None:
                aggression_tilt = _solve_tilt(
                    base,
                    weights,
                    total_weight,
                    AGGRESSIVE_ACTIONS,
                    aggressive_target,
                    continue_tilt,
                    aggression_tilt,
                    self,
                    solve_aggression=True,
                )
        return replace(context, continue_tilt=continue_tilt, aggression_tilt=aggression_tilt)

    def probability(
        self,
        hand_class: str,
        action: PokerAction,
        board_state: BoardState,
        player_profile: PlayerProfile,
        context: ActionContext | None = None,
    ) -> float:
        """Single-action convenience wrapper used by tests and the import path."""
        resolved = context or build_action_context(board_state, action)
        legal = legal_actions(resolved, action.action_type)
        return self.action_probabilities(hand_class, legal, board_state, player_profile, resolved)[action.action_type]

    # ---------------------------------------------------------------- internals

    def _logits(
        self,
        hand_class: str,
        legal: list[ActionType],
        board_state: BoardState,
        profile: PlayerProfile,
        context: ActionContext,
    ) -> dict[ActionType, float]:
        strength, draw = hand_features(hand_class, board_state)
        if context.street == Street.PREFLOP or len(board_state.board_cards) < 3:
            raw = self._preflop_logits(strength, context)
        else:
            raw = self._postflop_logits(strength, draw, profile, context)

        shifted: dict[ActionType, float] = {}
        for action in legal:
            logit = raw.get(action, -4.0)
            if action in VOLUNTARY:
                logit += context.continue_tilt
            if action in AGGRESSIVE_ACTIONS:
                logit += context.aggression_tilt
            shifted[action] = logit
        return shifted

    def _preflop_logits(self, strength: float, context: ActionContext) -> dict[ActionType, float]:
        value = strength - 0.62
        weak = max(0.0, 0.62 - strength) / 0.62
        showdown = 1.0 - min(1.0, abs(strength - 0.6) / 0.3)
        pressure = 0.4 + 0.5 * context.raise_level + 0.6 * min(2.0, context.bet_fraction_pot)
        hero_pressure = 0.7 if context.hero_three_bet else 0.0

        return {
            ActionType.FOLD: -0.2 + 4.6 * weak * pressure - 4.8 * max(0.0, value) + hero_pressure,
            ActionType.CHECK: 0.9 + 0.8 * showdown - 2.0 * max(0.0, value),
            ActionType.CALL: 0.2 + 2.2 * showdown + 1.6 * value - 1.4 * weak * pressure - 0.5 * hero_pressure,
            ActionType.RAISE: -0.6 + 5.2 * value,
            ActionType.THREE_BET: -1.6 + 7.0 * value,
            ActionType.FOUR_BET: -2.6 + 8.5 * value,
            ActionType.JAM: -3.4 + 9.0 * max(0.0, strength - 0.78),
        }

    def _postflop_logits(
        self,
        strength: float,
        draw: float,
        profile: PlayerProfile,
        context: ActionContext,
    ) -> dict[ActionType, float]:
        sizing = min(2.0, max(0.0, context.bet_fraction_pot))
        polar = 0.7 + 1.3 * sizing
        # The value pivot sits well above the median: on a dry board plain ace-high
        # already beats most random holdings, and that is not a hand to build a pot with.
        value = strength - 0.68
        weak = max(0.0, 0.5 - strength) / 0.5
        showdown = 1.0 - min(1.0, abs(strength - 0.6) / 0.32)
        semi_bluff = draw * (1.0 - min(1.0, strength / 0.6))
        aggression_factor = profile.aggression / (profile.aggression + 1.0)
        river_factor = profile.river_aggression / (profile.river_aggression + 1.0)
        bluffiness = profile.bluff_frequency - 0.22
        hero_pressure = 0.9 if context.hero_three_bet else 0.35 * min(2, context.hero_aggressive_actions)
        jam_aggression = river_factor - 0.55 if context.street == Street.RIVER else aggression_factor - 0.6

        return {
            ActionType.CHECK: 1.0 + 1.1 * showdown + 1.0 * weak - 2.4 * max(0.0, value) * polar - 1.6 * semi_bluff,
            ActionType.CALL: 0.5
            + 1.9 * showdown
            + 2.0 * value
            + 2.2 * draw
            - 2.6 * weak * sizing
            - 0.6 * hero_pressure * weak,
            ActionType.FOLD: -0.4
            + 4.4 * weak * (0.4 + sizing)
            - 3.0 * draw
            - 5.0 * max(0.0, value)
            + 0.8 * hero_pressure * weak,
            # Value climbs steeply with sizing (large bets are polarized) while the
            # penalty on weak holdings stays gentle, so semi-bluffs can outweigh it.
            ActionType.BET: -0.5
            + 4.2 * max(0.0, value) * polar
            + 1.3 * min(0.0, value) * polar
            + 4.5 * semi_bluff
            + 7.0 * bluffiness * weak
            + 2.4 * (aggression_factor - 0.6),
            ActionType.RAISE: -1.6
            + 5.0 * max(0.0, value) * polar
            + 1.8 * min(0.0, value) * polar
            + 4.0 * semi_bluff
            + 6.0 * bluffiness * weak
            + 2.4 * (aggression_factor - 0.6),
            ActionType.JAM: -3.2 + 9.0 * max(0.0, strength - 0.72) + 2.0 * bluffiness * weak + 2.0 * jam_aggression,
        }


def hand_features(hand_class: str, board_state: BoardState) -> tuple[float, float]:
    """(strength, draw equity). Postflop this never touches the preflop ranking."""
    if board_state.street == Street.PREFLOP or len(board_state.board_cards) < 3:
        return hand_strength_bucket(hand_class), 0.0
    strength: HandStrength = board_strength(board_state.board_cards, board_state.hero_cards)[hand_class]
    if strength.live_combos == 0:
        return 0.0, 0.0
    return strength.made_percentile, strength.draw_equity


def calibration_targets(profile: PlayerProfile, context: ActionContext) -> tuple[float | None, float | None]:
    """(voluntary-action target, aggressive-action target) for spots with a real stat.

    Spots without a measured statistic are left uncalibrated on purpose: the raw
    logits speak, and nothing pretends to a frequency the app has never observed.
    """
    if context.street == Street.PREFLOP:
        if context.raise_level == 0:
            return profile.vpip, profile.pfr
        if context.raise_level == 1:
            return None, profile.three_bet
        return 1.0 - profile.fold_to_three_bet, None
    if context.street == Street.FLOP and not context.facing_bet and context.opponent_is_preflop_aggressor:
        return None, profile.cbet
    return None, None


def aggregate_action_frequency(
    model: PolicyLikelihood,
    prior: dict[str, float],
    legal: list[ActionType],
    board_state: BoardState,
    profile: PlayerProfile,
    context: ActionContext,
    target_set: frozenset[ActionType],
) -> float:
    """Σ_h P(h) · π(a ∈ target_set | h). The quantity the calibration tests assert on."""
    total = 0.0
    weight_total = 0.0
    for hand, weight in prior.items():
        if weight <= 0.0:
            continue
        probabilities = model.action_probabilities(hand, legal, board_state, profile, context)
        total += weight * sum(probabilities.get(action, 0.0) for action in target_set)
        weight_total += weight
    return total / weight_total if weight_total > 0.0 else 0.0


def _aggregate(
    base: dict[str, dict[ActionType, float]],
    weights: dict[str, float],
    total_weight: float,
    target_set: frozenset[ActionType],
    continue_tilt: float,
    aggression_tilt: float,
    model: PolicyLikelihood,
) -> float:
    aggregate = 0.0
    for hand, logits in base.items():
        shifted = {
            action: logit
            + (continue_tilt if action in VOLUNTARY else 0.0)
            + (aggression_tilt if action in AGGRESSIVE_ACTIONS else 0.0)
            for action, logit in logits.items()
        }
        probabilities = _softmax(shifted, model.temperature, model.exploration_floor)
        aggregate += weights[hand] * sum(probabilities.get(action, 0.0) for action in target_set)
    return aggregate / total_weight


def _solve_tilt(
    base: dict[str, dict[ActionType, float]],
    weights: dict[str, float],
    total_weight: float,
    target_set: frozenset[ActionType],
    target: float,
    continue_tilt: float,
    aggression_tilt: float,
    model: PolicyLikelihood,
    solve_aggression: bool = False,
    iterations: int = 22,
) -> float:
    """Bisect the tilt that makes the range-aggregated frequency hit `target`."""
    target = min(0.99, max(0.01, target))
    low, high = -14.0, 14.0

    def aggregate_at(tilt: float) -> float:
        if solve_aggression:
            return _aggregate(base, weights, total_weight, target_set, continue_tilt, tilt, model)
        return _aggregate(base, weights, total_weight, target_set, tilt, aggression_tilt, model)

    if aggregate_at(low) > target:
        return low
    if aggregate_at(high) < target:
        return high
    for _ in range(iterations):
        middle = (low + high) / 2.0
        if aggregate_at(middle) < target:
            low = middle
        else:
            high = middle
    return (low + high) / 2.0


@dataclass
class HeuristicLikelihood(PolicyLikelihood):
    """Backwards-compatible name for the default policy."""


@dataclass
class NeuralLikelihood:
    """Plug-in point for a likelihood trained on the dataset emitted at showdown."""

    model_path: str | None = None

    def action_probabilities(
        self,
        hand_class: str,
        legal: list[ActionType],
        board_state: BoardState,
        profile: PlayerProfile,
        context: ActionContext,
    ) -> dict[ActionType, float]:
        raise NotImplementedError(
            "NeuralLikelihood needs a trained model. Collect showdowns first: every scored "
            "showdown appends to the JSONL dataset that training/train.py consumes."
        )

    def calibrate(
        self,
        prior: dict[str, float],
        legal: list[ActionType],
        board_state: BoardState,
        profile: PlayerProfile,
        context: ActionContext,
    ) -> ActionContext:
        return context


__all__ = [
    "HeuristicLikelihood",
    "LikelihoodModel",
    "NeuralLikelihood",
    "PolicyLikelihood",
    "aggregate_action_frequency",
    "calibration_targets",
    "hand_features",
    "legal_actions",
]

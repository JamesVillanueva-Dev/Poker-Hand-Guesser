"""Measure the model's skill in bits against a scripted opponent.

This is the discipline the project was missing: a number that says whether a change
made the tool better or worse. It plays N hands against an opponent whose decisions
come from a known generating process, then scores the model's range against the hand
that opponent actually held.

The `--compare` flag replays the identical hands through the pre-rebuild engine
(board-blind likelihood, no card removal, no normalization) so the two are directly
comparable on the same deals.

    python -m scripts.benchmark --hands 20
    python -m scripts.benchmark --hands 200 --compare

The opponent here is scripted, not human. The number this prints measures whether the
engine recovers a known generating policy, which is a necessary condition for being
useful on real hands, not a sufficient one.
"""

from __future__ import annotations

import argparse
import random
from dataclasses import dataclass, field
from math import inf

from engine.evaluator import FULL_DECK, board_strength, hand_class_of, live_combos
from engine.hand_classes import HAND_CLASSES, hand_strength_bucket, normalize, uniform_distribution
from engine.likelihood import PolicyLikelihood
from engine.range_engine import RangeEstimator
from engine.scoring import BASELINE_LOG_LOSS, score_prediction
from engine.state import ActionActor, ActionType, BoardState, PlayerProfile, PokerAction, Street

STREETS: tuple[tuple[Street, int], ...] = (
    (Street.PREFLOP, 0),
    (Street.FLOP, 3),
    (Street.TURN, 4),
    (Street.RIVER, 5),
)


# ---------------------------------------------------------------------------------------
# The pre-rebuild engine, kept here (and only here) so "before" is a real measurement.
# ---------------------------------------------------------------------------------------


@dataclass
class LegacyLikelihood:
    """Verbatim behaviour of the board-blind `HeuristicLikelihood` this rebuild replaced."""

    min_probability: float = 0.015

    def probability(self, hand_class: str, action: PokerAction, board_state: BoardState, profile: PlayerProfile) -> float:
        strength = _legacy_bucket(hand_class)
        sizing = max(action.bet_fraction_pot, action.amount / action.pot_before if action.pot_before > 0 else 0.0)
        aggression = max(0.15, profile.aggression)
        bluff = max(0.02, min(0.65, profile.bluff_frequency))

        if action.street == Street.PREFLOP:
            openness = max(0.04, min(0.8, profile.vpip))
            raise_bias = max(0.03, min(0.65, profile.pfr))
            match action.action_type:
                case ActionType.FOLD:
                    likelihood = 1.15 - 0.92 * strength
                case ActionType.CHECK | ActionType.CALL:
                    likelihood = openness * (0.65 + 0.5 * (1.0 - abs(strength - 0.45)))
                case ActionType.RAISE:
                    likelihood = raise_bias * (0.28 + 1.75 * strength**1.65)
                case ActionType.THREE_BET:
                    likelihood = profile.three_bet * (0.2 + 2.35 * strength**2.25)
                case ActionType.FOUR_BET | ActionType.JAM:
                    likelihood = 0.03 + 1.85 * strength**3.1
                case _:
                    likelihood = 0.5
        else:
            big_bet_pressure = min(1.0, max(0.0, sizing))
            value_component = 0.18 + 1.65 * strength ** (1.3 + big_bet_pressure)
            bluff_component = bluff * (0.75 - 0.38 * strength)
            match action.action_type:
                case ActionType.FOLD:
                    likelihood = 1.12 - 0.78 * strength
                case ActionType.CHECK:
                    likelihood = 0.75 + 0.38 * (1.0 - strength) / max(0.65, aggression)
                case ActionType.CALL:
                    likelihood = 0.45 + 0.9 * (1.0 - abs(strength - 0.58))
                case ActionType.BET | ActionType.RAISE:
                    cbet = profile.cbet if action.street == Street.FLOP else 0.5 + 0.12 * aggression
                    likelihood = cbet * (value_component + bluff_component)
                case ActionType.JAM:
                    river = profile.river_aggression if action.street == Street.RIVER else aggression
                    likelihood = (0.08 + 2.25 * strength**2.7 + bluff_component) * max(0.45, river)
                case _:
                    likelihood = 0.5
        return max(self.min_probability, likelihood)


def _legacy_bucket(hand_class: str) -> float:
    """The old preflop ranking, used by the old engine on every street."""
    ranks = "AKQJT98765432"
    first, second = ranks.index(hand_class[0]), ranks.index(hand_class[1])
    high_score = (12 - min(first, second)) / 12
    low_score = (12 - max(first, second)) / 12
    pair_bonus = 0.28 if len(hand_class) == 2 else 0.0
    suited_bonus = 0.08 if hand_class.endswith("s") else 0.0
    connected = max(0.0, 0.09 - abs(first - second) * 0.018) if len(hand_class) == 3 else 0.0
    broadway = 0.08 if first <= 4 and second <= 4 else 0.0
    ace = 0.05 if "A" in hand_class else 0.0
    raw = 0.48 * high_score + 0.22 * low_score + pair_bonus + suited_bonus + connected + broadway + ace
    return max(0.01, min(1.0, raw))


def legacy_update(distribution: dict[str, float], action: PokerAction, board_state: BoardState, profile: PlayerProfile) -> dict[str, float]:
    model = LegacyLikelihood()
    prior = normalize(distribution)
    return normalize({hand: prior[hand] * model.probability(hand, action, board_state, profile) for hand in HAND_CLASSES})


# ---------------------------------------------------------------------------------------
# The scripted opponent
# ---------------------------------------------------------------------------------------


@dataclass
class ScriptedVillain:
    """Acts on real board-relative strength, by thresholds rather than a softmax."""

    open_threshold: float = 0.42
    call_threshold: float = 0.30
    value_threshold: float = 0.78
    bluff_rate: float = 0.28

    def preflop(self, hand_class: str, rng: random.Random) -> ActionType:
        strength = hand_strength_bucket(hand_class)
        if strength >= self.open_threshold:
            return ActionType.RAISE
        if strength >= self.call_threshold:
            return ActionType.CALL
        return ActionType.FOLD

    def postflop(self, percentile: float, draw: float, rng: random.Random) -> ActionType:
        if percentile >= self.value_threshold:
            return ActionType.BET
        if draw >= 0.25 and rng.random() < self.bluff_rate + 0.2:
            return ActionType.BET
        if percentile < 0.35 and rng.random() < self.bluff_rate:
            return ActionType.BET
        return ActionType.CHECK


@dataclass
class HandScript:
    hero: list[str]
    villain: list[str]
    board: list[str]
    actions: list[tuple[Street, ActionType, float, float]] = field(default_factory=list)


def script_hand(rng: random.Random, villain: ScriptedVillain) -> HandScript | None:
    deck = list(FULL_DECK)
    rng.shuffle(deck)
    hero, villain_cards, board = deck[:2], deck[2:4], deck[4:9]

    hand_class = hand_class_of(*villain_cards)
    preflop = villain.preflop(hand_class, rng)
    if preflop == ActionType.FOLD:
        return None

    script = HandScript(hero=hero, villain=villain_cards, board=board)
    pot = 1.5
    script.actions.append((Street.PREFLOP, preflop, 3.0 if preflop == ActionType.RAISE else 1.0, pot))
    pot += 6.0 if preflop == ActionType.RAISE else 2.0

    for street, cards in ((Street.FLOP, 3), (Street.TURN, 4), (Street.RIVER, 5)):
        visible = board[:cards]
        strength = board_strength(visible, hero)[hand_class]
        action = villain.postflop(strength.made_percentile, strength.draw_equity, rng)
        amount = round(pot * rng.choice([0.4, 0.66, 1.0]), 1) if action == ActionType.BET else 0.0
        script.actions.append((street, action, amount, pot))
        pot += amount * 2  # hero always calls, so the hand reaches showdown
    return script


# ---------------------------------------------------------------------------------------
# Running the benchmark
# ---------------------------------------------------------------------------------------


def run(hands: int, seed: int, legacy: bool = False) -> dict[str, object]:
    rng = random.Random(seed)
    estimator = RangeEstimator(PolicyLikelihood())
    profile = PlayerProfile("benchmark")
    per_street: dict[str, list[float]] = {street.value: [] for street, _ in STREETS}
    all_skills: list[float] = []
    scored_hands = 0

    while scored_hands < hands:
        script = script_hand(rng, ScriptedVillain())
        if script is None:
            continue
        scored_hands += 1
        true_class = hand_class_of(*script.villain)

        dead: list[str] = list(script.hero)
        distribution = (
            uniform_distribution() if legacy else normalize({hand: live_combos(hand, dead) for hand in HAND_CLASSES})
        )
        history: list[PokerAction] = []

        for sequence, (street, action_type, amount, pot) in enumerate(script.actions):
            cards = {Street.PREFLOP: 0, Street.FLOP: 3, Street.TURN: 4, Street.RIVER: 5}[street]
            visible = script.board[:cards]
            previous_dead = list(dead)
            dead = [*script.hero, *visible]
            board_state = BoardState(
                street=street,
                board_cards=visible,
                hero_cards=script.hero,
                pot=pot,
                effective_stack=100.0,
                position="BTN",
                previous_actions=list(history),
            )
            action = PokerAction(
                player_id="benchmark",
                action_type=action_type,
                street=street,
                position="BTN",
                actor=ActionActor.OPPONENT,
                amount=amount,
                pot_before=pot,
                bet_fraction_pot=amount / pot if pot else 0.0,
                sequence=sequence,
            )
            if legacy:
                distribution = legacy_update(distribution, action, board_state, profile)
            else:
                distribution = estimator.update_range(distribution, action, board_state, profile, previous_dead)
            history.append(action)

            score = score_prediction(distribution, true_class)
            per_street[street.value].append(score.skill)
            if street == Street.RIVER:
                all_skills.append(score.skill)

    return {
        "hands": scored_hands,
        "mean_skill": sum(all_skills) / len(all_skills) if all_skills else 0.0,
        "per_street": {street: (sum(values) / len(values) if values else 0.0) for street, values in per_street.items()},
        "worst": min(all_skills, default=inf),
        "best": max(all_skills, default=-inf),
    }


def flagship_case() -> dict[str, float]:
    """Probability mass on 77 versus AQo after a large bet on Ks 7d 2c."""
    board = ["Ks", "7d", "2c"]
    board_state = BoardState(street=Street.FLOP, board_cards=board, pot=10.0)
    action = PokerAction("v", ActionType.BET, Street.FLOP, "BTN", amount=9.0, pot_before=10.0, bet_fraction_pot=0.9)
    profile = PlayerProfile("v")

    estimator = RangeEstimator(PolicyLikelihood())
    current = estimator.update_range(estimator.initial_distribution(board), action, board_state, profile)
    before = legacy_update(uniform_distribution(), action, board_state, profile)
    return {
        "legacy_77": before["77"],
        "legacy_AQo": before["AQo"],
        "current_77": current["77"],
        "current_AQo": current["AQo"],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--hands", type=int, default=20)
    parser.add_argument("--seed", type=int, default=2026)
    parser.add_argument("--compare", action="store_true", help="also replay the hands through the old engine")
    args = parser.parse_args()

    print(f"Baseline (uniform guess over 169 classes): {BASELINE_LOG_LOSS:.2f} bits\n")

    results = {"current": run(args.hands, args.seed)}
    if args.compare:
        results["legacy"] = run(args.hands, args.seed, legacy=True)

    for label, result in results.items():
        print(f"{label}: {result['hands']} hands, mean skill at showdown {result['mean_skill']:+.2f} bits")
        for street, skill in result["per_street"].items():
            print(f"    {street:8s} {skill:+.2f} bits")
        print(f"    worst hand {result['worst']:+.2f}, best hand {result['best']:+.2f}\n")

    case = flagship_case()
    print("Ks 7d 2c after a 90%-pot bet:")
    print(f"    before: 77 {case['legacy_77'] * 100:.3f}%   AQo {case['legacy_AQo'] * 100:.3f}%")
    print(f"    after:  77 {case['current_77'] * 100:.3f}%   AQo {case['current_AQo'] * 100:.3f}%")


if __name__ == "__main__":
    main()

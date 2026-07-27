"""Hero's move, chosen by expected value against the modeled range.

There are no strength thresholds here. Every candidate line is priced against the same
opponent policy that produced the range: fold equity comes from `π(fold | h)` aggregated
over the range, and showdown equity comes from the same exact combo enumeration that
ranks the opponent's hands. The recommendation is whichever line prices highest.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from engine.evaluator import (
    RANK_VALUES,
    board_strength,
    category_mix,
    hand_class_of,
    hero_equity,
    holding_strength,
    normalize_cards,
)
from engine.hand_classes import RANKS, hand_strength_bucket, normalize
from engine.likelihood import PolicyLikelihood
from engine.scoring import BASELINE_LOG_LOSS
from engine.state import ActionContext, ActionType, BoardState, PlayerProfile, PokerAction, Street

BET_SIZES: tuple[float, ...] = (0.33, 0.66, 1.0)
AGGRESSIVE = {ActionType.BET, ActionType.RAISE, ActionType.THREE_BET, ActionType.FOUR_BET, ActionType.JAM}


@dataclass(frozen=True)
class MoveRecommendation:
    action: str
    sizing_bb: float
    sizing_pot_fraction: float
    confidence: float
    headline: str
    reasons: list[str]
    expected_value_bb: float = 0.0
    confidence_basis: str = "model certainty (unvalidated)"
    ev_breakdown: list[dict[str, float | str]] = field(default_factory=list)
    range_composition: dict[str, float] = field(default_factory=dict)

    def as_dict(self) -> dict[str, object]:
        return {
            "action": self.action,
            "sizing_bb": self.sizing_bb,
            "sizing_pot_fraction": self.sizing_pot_fraction,
            "confidence": self.confidence,
            "headline": self.headline,
            "reasons": self.reasons,
            "expected_value_bb": self.expected_value_bb,
            "confidence_basis": self.confidence_basis,
            "ev_breakdown": self.ev_breakdown,
            "range_composition": self.range_composition,
        }


@dataclass(frozen=True)
class Candidate:
    action: str
    expected_value: float
    sizing_bb: float
    sizing_pot_fraction: float
    detail: str


def recommend_move(
    distribution: dict[str, float],
    board_state: BoardState,
    profile: PlayerProfile,
    latest_action: PokerAction | None = None,
    measured_skill: float | None = None,
    scored_showdowns: int = 0,
    model: PolicyLikelihood | None = None,
) -> MoveRecommendation:
    normalized = normalize(distribution)
    policy = model or PolicyLikelihood()
    hero_cards = normalize_cards(board_state.hero_cards)[:2]
    board = normalize_cards(board_state.board_cards)
    postflop = len(board) >= 3 and board_state.street != Street.PREFLOP

    facing = _facing_amount(latest_action)
    pot = max(1.0, board_state.pot)
    stack = board_state.effective_stack if board_state.effective_stack > 0 else pot * 4.0

    equity, hero_label, composition, range_strength = _read_the_spot(normalized, hero_cards, board, postflop)

    candidates: list[Candidate] = []
    if facing > 0:
        candidates.append(Candidate("fold", 0.0, 0.0, 0.0, "Folding is worth 0 by definition."))
        call_ev = equity * pot - (1.0 - equity) * facing
        candidates.append(
            Candidate(
                "call",
                call_ev,
                facing,
                facing / pot,
                f"Calling {facing:.1f} bb into {pot:.1f} bb needs {facing / (pot + facing) * 100:.0f}% equity; the model gives hero {equity * 100:.0f}%.",
            )
        )
    else:
        candidates.append(
            Candidate("check", equity * pot, 0.0, 0.0, f"Checking realises {equity * 100:.0f}% of a {pot:.1f} bb pot.")
        )

    aggressive_label = "raise" if facing > 0 else "bet"
    for fraction in BET_SIZES:
        size = min(stack, pot * fraction)
        if size <= 0.0:
            continue
        # Raising means matching the bet in front *and* putting the raise on top. That
        # whole amount is at risk when the opponent continues.
        commitment = facing + size
        fold_equity, continuing = _fold_equity(policy, normalized, board_state, profile, size, pot, latest_action)
        continuing_equity = _equity_against(continuing, hero_cards, board, postflop, normalized, equity)
        value = fold_equity * pot + (1.0 - fold_equity) * (
            continuing_equity * (pot + commitment) - (1.0 - continuing_equity) * commitment
        )
        candidates.append(
            Candidate(
                aggressive_label,
                value,
                round(commitment, 1),
                round(fraction, 2),
                f"A {fraction * 100:.0f}% pot {aggressive_label} risks {commitment:.1f} bb and folds out "
                f"{fold_equity * 100:.0f}% of the range; against what continues hero has "
                f"{continuing_equity * 100:.0f}% equity.",
            )
        )

    best = max(candidates, key=lambda candidate: candidate.expected_value)
    confidence, basis = _confidence(measured_skill, scored_showdowns)

    reasons = [
        f"Hero holds {hero_label}"
        + (f" — {equity * 100:.0f}% equity against the modeled range." if postflop else f" preflop, roughly {equity * 100:.0f}% equity against the modeled range."),
        _composition_sentence(composition, postflop, range_strength),
    ]
    if latest_action is not None and latest_action.actor.value == "opponent":
        reasons.append(
            f"Latest opponent action: {latest_action.action_type.value.replace('_', ' ')} for "
            f"{latest_action.amount:.1f} bb into {latest_action.pot_before:.1f} bb."
        )
    reasons.append(best.detail)
    reasons.append(
        "Line chosen by expected value: " + ", ".join(f"{c.action} {c.expected_value:+.2f} bb" for c in candidates) + "."
    )

    return MoveRecommendation(
        action=best.action,
        sizing_bb=best.sizing_bb,
        sizing_pot_fraction=best.sizing_pot_fraction,
        confidence=confidence,
        headline=_headline(best, facing),
        reasons=reasons,
        expected_value_bb=round(best.expected_value, 2),
        confidence_basis=basis,
        ev_breakdown=[
            {"action": c.action, "sizing_pot_fraction": c.sizing_pot_fraction, "expected_value_bb": round(c.expected_value, 2)}
            for c in candidates
        ],
        range_composition={category: round(weight, 4) for category, weight in composition.items()},
    )


# ------------------------------------------------------------------------------------------
# Reading the spot
# ------------------------------------------------------------------------------------------


def _read_the_spot(
    normalized: dict[str, float],
    hero_cards: tuple[str, ...],
    board: tuple[str, ...],
    postflop: bool,
) -> tuple[float, str, dict[str, float], float]:
    if postflop:
        strengths = board_strength(list(board), list(hero_cards))
        range_strength = sum(
            weight * strengths[hand].made_percentile for hand, weight in normalized.items() if hand in strengths
        )
        composition = category_mix(normalized, list(board), list(hero_cards))
        if len(hero_cards) == 2:
            percentile, label = holding_strength(list(hero_cards), list(board))
            equity = hero_equity(normalized, list(hero_cards), list(board))
            return equity, f"{label} ({percentile * 100:.0f}th percentile on this board)", composition, range_strength
        return 0.5, "unknown cards", composition, range_strength

    range_strength = sum(weight * hand_strength_bucket(hand) for hand, weight in normalized.items())
    if len(hero_cards) == 2:
        hand_class = starting_hand_class(list(hero_cards))
        hero_bucket = hand_strength_bucket(hand_class)
        # Preflop there is no board to enumerate against; the preflop ranking gap is a
        # documented proxy for equity, and it is the only place it is still used.
        equity = min(0.92, max(0.08, 0.5 + 0.75 * (hero_bucket - range_strength)))
        return equity, hand_class, {}, range_strength
    return 0.5, "unknown cards", {}, range_strength


def _equity_against(
    continuing: dict[str, float],
    hero_cards: tuple[str, ...],
    board: tuple[str, ...],
    postflop: bool,
    fallback_distribution: dict[str, float],
    fallback_equity: float,
) -> float:
    if not postflop or len(hero_cards) != 2:
        # Continuing ranges are stronger than the full range; nudge the proxy down.
        return max(0.05, fallback_equity - 0.06)
    return hero_equity(continuing, list(hero_cards), list(board))


def _fold_equity(
    policy: PolicyLikelihood,
    normalized: dict[str, float],
    board_state: BoardState,
    profile: PlayerProfile,
    size: float,
    pot: float,
    latest_action: PokerAction | None,
) -> tuple[float, dict[str, float]]:
    """How much of the range folds to a bet of `size`, and what is left when it does not."""
    hero_aggression = 1 + (1 if latest_action is not None and latest_action.actor.value == "hero" else 0)
    context = ActionContext(
        street=board_state.street,
        raise_level=1,
        facing_bet=True,
        bet_fraction_pot=size / pot if pot > 0 else 0.0,
        pot_odds=size / (pot + size) if pot + size > 0 else 0.0,
        hero_aggressive_actions=hero_aggression,
    )
    legal = [ActionType.FOLD, ActionType.CALL, ActionType.RAISE, ActionType.JAM]
    if board_state.street == Street.PREFLOP:
        legal = [ActionType.FOLD, ActionType.CALL, ActionType.THREE_BET, ActionType.JAM]

    folds = 0.0
    continuing: dict[str, float] = {}
    for hand, weight in normalized.items():
        if weight <= 0.0:
            continuing[hand] = 0.0
            continue
        probabilities = policy.action_probabilities(hand, legal, board_state, profile, context)
        fold_probability = probabilities[ActionType.FOLD]
        folds += weight * fold_probability
        continuing[hand] = weight * (1.0 - fold_probability)
    return folds, normalize(continuing)


def _facing_amount(latest_action: PokerAction | None) -> float:
    if latest_action is None or latest_action.actor.value != "opponent":
        return 0.0
    return latest_action.amount if latest_action.action_type in AGGRESSIVE else 0.0


def _composition_sentence(composition: dict[str, float], postflop: bool, range_strength: float) -> str:
    if not postflop or not composition:
        return f"The modeled range averages {range_strength * 100:.0f}/100 on the preflop ranking."
    parts = [f"{weight * 100:.0f}% {category}" for category, weight in list(composition.items())[:4]]
    return "On this board the opponent's range is " + ", ".join(parts) + "."


def _headline(best: Candidate, facing: float) -> str:
    if best.action == "fold":
        return "Fold. Nothing prices better than zero here."
    if best.action == "call":
        return "Call. The price beats every alternative line."
    if best.action == "check":
        return "Check. Betting does not price better than a free showdown."
    return f"{'Raise' if facing > 0 else 'Bet'} {best.sizing_pot_fraction * 100:.0f}% pot. Highest expected value of the lines priced."


def _confidence(measured_skill: float | None, scored_showdowns: int) -> tuple[float, str]:
    """Confidence is measured, or it is labeled as unmeasured. It is never invented."""
    if measured_skill is None or scored_showdowns <= 0:
        return 0.5, "model certainty (unvalidated) — no showdowns have been scored yet"
    grounded = 0.5 + measured_skill / (2.0 * BASELINE_LOG_LOSS)
    return (
        round(min(0.95, max(0.05, grounded)), 2),
        f"grounded in {scored_showdowns} scored showdown{'s' if scored_showdowns != 1 else ''} "
        f"(mean skill {measured_skill:+.2f} bits vs. a uniform guess)",
    )


def starting_hand_class(cards: list[str]) -> str:
    """Preflop class for two concrete cards."""
    if len(cards) < 2:
        return "72o"
    return hand_class_of(cards[0], cards[1]) or "72o"


__all__ = ["MoveRecommendation", "RANKS", "RANK_VALUES", "recommend_move", "starting_hand_class"]

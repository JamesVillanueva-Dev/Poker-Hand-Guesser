from __future__ import annotations

from dataclasses import dataclass

from engine.hand_classes import RANKS, hand_strength_bucket, normalize
from engine.state import ActionType, BoardState, PlayerProfile, PokerAction, Street

RANK_VALUES: dict[str, int] = {
    "2": 2,
    "3": 3,
    "4": 4,
    "5": 5,
    "6": 6,
    "7": 7,
    "8": 8,
    "9": 9,
    "T": 10,
    "J": 11,
    "Q": 12,
    "K": 13,
    "A": 14,
}


@dataclass(frozen=True)
class MoveRecommendation:
    action: str
    sizing_bb: float
    sizing_pot_fraction: float
    confidence: float
    headline: str
    reasons: list[str]

    def as_dict(self) -> dict[str, object]:
        return {
            "action": self.action,
            "sizing_bb": self.sizing_bb,
            "sizing_pot_fraction": self.sizing_pot_fraction,
            "confidence": self.confidence,
            "headline": self.headline,
            "reasons": self.reasons,
        }


def recommend_move(
    distribution: dict[str, float],
    board_state: BoardState,
    profile: PlayerProfile,
    latest_action: PokerAction | None = None,
) -> MoveRecommendation:
    normalized = normalize(distribution)
    range_strength = sum(probability * hand_strength_bucket(hand) for hand, probability in normalized.items())
    premium_mass = sum(probability for hand, probability in normalized.items() if hand_strength_bucket(hand) >= 0.78)
    weak_mass = sum(probability for hand, probability in normalized.items() if hand_strength_bucket(hand) <= 0.38)
    hero_score, hero_label = _hero_strength(board_state.hero_cards, board_state.board_cards, board_state.street)
    pot = max(1.0, board_state.pot)
    facing = latest_action.amount if latest_action and latest_action.actor.value == "opponent" and latest_action.action_type in {
        ActionType.BET,
        ActionType.RAISE,
        ActionType.THREE_BET,
        ActionType.FOUR_BET,
        ActionType.JAM,
    } else 0.0
    pot_odds = facing / max(pot + facing, 1.0) if facing > 0 else 0.0
    pressure = min(1.0, premium_mass * 1.35 + range_strength * 0.45)
    fold_equity = min(0.72, max(0.06, weak_mass * 1.45 + (1.0 - profile.vpip) * 0.16 - profile.showdown_frequency * 0.1))
    edge = hero_score - range_strength
    reasons = [
        f"Hero holding reads as {hero_label} ({hero_score * 100:.0f}/100) against an opponent range averaging {range_strength * 100:.0f}/100.",
        f"Opponent range has {premium_mass * 100:.1f}% premium-weight hands and {weak_mass * 100:.1f}% weak-weight hands.",
    ]

    if latest_action and latest_action.actor.value == "opponent":
        reasons.append(
            f"Latest opponent action was {latest_action.action_type.value.replace('_', ' ')} for {latest_action.amount:.1f} bb into {latest_action.pot_before:.1f} bb."
        )

    if facing > 0:
        reasons.append(f"Calling requires about {pot_odds * 100:.1f}% equity by direct pot odds.")

    if facing > 0 and (edge < -0.12 or hero_score < pot_odds + pressure * 0.38):
        return MoveRecommendation(
            action="fold",
            sizing_bb=0.0,
            sizing_pot_fraction=0.0,
            confidence=_confidence(abs(edge) + pressure),
            headline="Fold the low-equity bluff catchers.",
            reasons=[*reasons, "The price and concentrated value weight make continuing too thin without a stronger hand or read."],
        )

    if hero_score >= 0.76 and pressure < 0.72:
        sizing = _value_sizing(board_state.street, profile, pot, board_state.effective_stack)
        return MoveRecommendation(
            action="raise" if facing > 0 else "bet",
            sizing_bb=sizing[0],
            sizing_pot_fraction=sizing[1],
            confidence=_confidence(edge + 0.2),
            headline="Build the pot for value.",
            reasons=[*reasons, "Hero strength is ahead of the modeled range often enough to prefer value and protection."],
        )

    if hero_score >= 0.55 and facing > 0:
        return MoveRecommendation(
            action="call",
            sizing_bb=facing,
            sizing_pot_fraction=facing / pot,
            confidence=_confidence(hero_score - pot_odds),
            headline="Continue at the offered price.",
            reasons=[*reasons, "The hand has enough showdown value to continue without inflating the pot against the stronger part of the range."],
        )

    if facing <= 0 and (hero_score >= 0.6 or fold_equity >= 0.42):
        sizing_fraction = 0.55 if board_state.street in {Street.FLOP, Street.TURN} else 0.45
        sizing_bb = min(board_state.effective_stack, pot * sizing_fraction) if board_state.effective_stack > 0 else pot * sizing_fraction
        return MoveRecommendation(
            action="bet",
            sizing_bb=round(sizing_bb, 1),
            sizing_pot_fraction=sizing_fraction,
            confidence=_confidence(hero_score + fold_equity - pressure),
            headline="Apply pressure with a controlled sizing.",
            reasons=[*reasons, "The opponent profile leaves enough folds or worse continues for a medium sizing to perform well."],
        )

    return MoveRecommendation(
        action="check" if facing <= 0 else "call",
        sizing_bb=0.0 if facing <= 0 else facing,
        sizing_pot_fraction=0.0 if facing <= 0 else facing / pot,
        confidence=_confidence(0.5 - abs(edge)),
        headline="Keep the pot manageable.",
        reasons=[*reasons, "The model does not show enough range advantage or fold equity to justify a large bet."],
    )


def _value_sizing(street: Street, profile: PlayerProfile, pot: float, effective_stack: float) -> tuple[float, float]:
    if street == Street.PREFLOP:
        fraction = 2.2
    elif profile.bluff_frequency > 0.32:
        fraction = 0.72
    elif street == Street.RIVER:
        fraction = 0.62
    else:
        fraction = 0.68
    sizing = pot * fraction
    if effective_stack > 0:
        sizing = min(effective_stack, sizing)
    return round(sizing, 1), round(fraction, 2)


def _confidence(signal: float) -> float:
    return round(max(0.28, min(0.92, 0.46 + signal * 0.55)), 2)


def _hero_strength(hero_cards: list[str], board_cards: list[str], street: Street) -> tuple[float, str]:
    if len(hero_cards) < 2:
        return 0.5, "unknown cards"

    if street == Street.PREFLOP or not board_cards:
        hand_class = _starting_hand_class(hero_cards[:2])
        return hand_strength_bucket(hand_class), hand_class

    ranks = [_rank(card) for card in [*hero_cards[:2], *board_cards] if _rank(card)]
    suits = [_suit(card) for card in [*hero_cards[:2], *board_cards] if _suit(card)]
    counts = sorted((ranks.count(rank) for rank in set(ranks)), reverse=True)
    flush_count = max((suits.count(suit) for suit in set(suits)), default=0)
    straight = _has_straight(ranks)
    hero_rank_values = [_rank_value(card) for card in hero_cards[:2]]
    top_board = max((_rank_value(card) for card in board_cards), default=0)
    overpair = len(set(hero_rank_values)) == 1 and hero_rank_values[0] > top_board

    if straight and flush_count >= 5:
        return 0.98, "straight flush or better"
    if counts and counts[0] == 4:
        return 0.96, "quads"
    if len(counts) >= 2 and counts[0] == 3 and counts[1] >= 2:
        return 0.9, "full house"
    if flush_count >= 5:
        return 0.84, "flush"
    if straight:
        return 0.8, "straight"
    if counts and counts[0] == 3:
        return 0.68, "trips"
    if len(counts) >= 2 and counts[0] == 2 and counts[1] == 2:
        return 0.58, "two pair"
    if overpair:
        return 0.64, "overpair"
    if counts and counts[0] == 2:
        pair_rank = max(_rank_to_value(rank) for rank in set(ranks) if ranks.count(rank) == 2)
        if pair_rank >= top_board:
            return 0.54, "top pair"
        return 0.42, "pair"
    if flush_count == 4 or _open_ended(ranks):
        return 0.38, "draw"
    high = max(hero_rank_values, default=0)
    return (0.34 if high >= 13 else 0.24), "high-card hand"


def _starting_hand_class(cards: list[str]) -> str:
    first, second = cards
    first_rank = _rank(first)
    second_rank = _rank(second)
    if not first_rank or not second_rank:
        return "72o"
    if first_rank == second_rank:
        return f"{first_rank}{second_rank}"
    ordered = sorted([first_rank, second_rank], key=lambda rank: RANKS.index(rank))
    suffix = "s" if _suit(first) == _suit(second) else "o"
    return f"{ordered[0]}{ordered[1]}{suffix}"


def _rank(card: str) -> str:
    return card[:1].upper() if len(card) >= 2 and card[:1].upper() in RANK_VALUES else ""


def _suit(card: str) -> str:
    suit = card[-1:].lower()
    return suit if suit in {"s", "h", "d", "c"} else ""


def _rank_value(card: str) -> int:
    return RANK_VALUES.get(_rank(card), 0)


def _has_straight(ranks: list[str]) -> bool:
    values = {_rank_to_value(rank) for rank in ranks}
    if 14 in values:
        values.add(1)
    return any(all(value + offset in values for offset in range(5)) for value in range(1, 11))


def _open_ended(ranks: list[str]) -> bool:
    values = {_rank_to_value(rank) for rank in ranks}
    if 14 in values:
        values.add(1)
    return any(sum((value + offset) in values for offset in range(4)) >= 4 for value in range(1, 12))


def _rank_to_value(rank: str) -> int:
    return RANK_VALUES.get(rank, 0)

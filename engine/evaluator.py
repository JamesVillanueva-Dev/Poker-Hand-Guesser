"""Board-relative hand strength.

Every postflop question this project asks reduces to one primitive: given a board,
how good is a holding *relative to everything else that could be held*? This module
answers that exactly by enumerating the live two-card combos, evaluating each one,
and ranking them. Nothing here consults the preflop hand-strength ranking.
"""

from __future__ import annotations

from bisect import bisect_left, bisect_right
from collections import Counter
from dataclasses import dataclass
from functools import lru_cache
from itertools import combinations

from engine.hand_classes import HAND_CLASSES, RANKS

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
VALUE_RANKS: dict[int, str] = {value: rank for rank, value in RANK_VALUES.items()}
SUITS: tuple[str, ...] = ("s", "h", "d", "c")
FULL_DECK: tuple[str, ...] = tuple(f"{rank}{suit}" for rank in RANKS for suit in SUITS)

CATEGORY_ORDER: tuple[str, ...] = (
    "straight flush",
    "quads",
    "full house",
    "flush",
    "straight",
    "set",
    "trips",
    "two pair",
    "overpair",
    "top pair",
    "middle pair",
    "weak pair",
    "flush draw",
    "straight draw",
    "air",
)


@dataclass(frozen=True)
class HandStrength:
    """Board-relative strength of one of the 169 classes."""

    made_percentile: float
    category: str
    draw_equity: float
    live_combos: int


def normalize_card(card: str) -> str:
    if len(card) < 2:
        return ""
    rank = card[0].upper()
    suit = card[-1].lower()
    if rank not in RANK_VALUES or suit not in SUITS:
        return ""
    return f"{rank}{suit}"


def normalize_cards(cards: list[str] | tuple[str, ...]) -> tuple[str, ...]:
    normalized = [normalize_card(card) for card in cards]
    seen: list[str] = []
    for card in normalized:
        if card and card not in seen:
            seen.append(card)
    return tuple(seen)


def card_rank(card: str) -> int:
    return RANK_VALUES[card[0].upper()]


def card_suit(card: str) -> str:
    return card[-1].lower()


def hand_class_of(card_one: str, card_two: str) -> str:
    """Map two concrete cards onto one of the 169 canonical classes."""
    first = normalize_card(card_one)
    second = normalize_card(card_two)
    if not first or not second:
        return ""
    high, low = sorted((first, second), key=lambda card: -card_rank(card))
    if card_rank(high) == card_rank(low):
        return f"{high[0]}{low[0]}"
    suffix = "s" if card_suit(high) == card_suit(low) else "o"
    return f"{high[0]}{low[0]}{suffix}"


def class_cards(hand_class: str) -> list[tuple[str, str]]:
    """All concrete two-card combos belonging to a class, ignoring dead cards."""
    high, low = hand_class[0], hand_class[1]
    if len(hand_class) == 2:
        return [(f"{high}{a}", f"{low}{b}") for a, b in combinations(SUITS, 2)]
    if hand_class.endswith("s"):
        return [(f"{high}{suit}", f"{low}{suit}") for suit in SUITS]
    return [(f"{high}{a}", f"{low}{b}") for a in SUITS for b in SUITS if a != b]


def live_combos(hand_class: str, dead: list[str] | tuple[str, ...]) -> int:
    """Combo count for a class after removing every dead (board + hero) card."""
    blocked = set(normalize_cards(dead))
    return sum(1 for one, two in class_cards(hand_class) if one not in blocked and two not in blocked)


# --------------------------------------------------------------------------------------
# 5-7 card evaluation
# --------------------------------------------------------------------------------------


def _straight_high(values: set[int]) -> int:
    if 14 in values:
        values = values | {1}
    for high in range(14, 4, -1):
        if all(high - offset in values for offset in range(5)):
            return high
    return 0


def evaluate(cards: tuple[str, ...]) -> tuple[int, ...]:
    """Rank-histogram evaluator. Returns a comparable tuple; bigger is better."""
    ranks = [card_rank(card) for card in cards]
    suits = [card_suit(card) for card in cards]
    rank_counts = Counter(ranks)
    suit_counts = Counter(suits)

    flush_suit = next((suit for suit, count in suit_counts.items() if count >= 5), None)
    if flush_suit is not None:
        flush_ranks = sorted((rank for rank, suit in zip(ranks, suits) if suit == flush_suit), reverse=True)
        straight_flush = _straight_high(set(flush_ranks))
        if straight_flush:
            return (8, straight_flush)

    ordered = sorted(rank_counts.items(), key=lambda item: (-item[1], -item[0]))
    top_rank, top_count = ordered[0]

    if top_count == 4:
        kicker = max(rank for rank in ranks if rank != top_rank)
        return (7, top_rank, kicker)
    if top_count == 3 and len(ordered) > 1 and ordered[1][1] >= 2:
        return (6, top_rank, ordered[1][0])
    if flush_suit is not None:
        return (5, *flush_ranks[:5])

    straight = _straight_high(set(ranks))
    if straight:
        return (4, straight)
    if top_count == 3:
        kickers = sorted((rank for rank in ranks if rank != top_rank), reverse=True)[:2]
        return (3, top_rank, *kickers)
    if top_count == 2 and len(ordered) > 1 and ordered[1][1] == 2:
        pairs = (top_rank, ordered[1][0])
        kicker = max(rank for rank in ranks if rank not in pairs)
        return (2, pairs[0], pairs[1], kicker)
    if top_count == 2:
        kickers = sorted((rank for rank in ranks if rank != top_rank), reverse=True)[:3]
        return (1, top_rank, *kickers)
    return (0, *sorted(ranks, reverse=True)[:5])


def _made_category(hole: tuple[str, str], board: tuple[str, ...], score: tuple[int, ...]) -> str:
    bucket = score[0]
    if bucket == 8:
        return "straight flush"
    if bucket == 7:
        return "quads"
    if bucket == 6:
        return "full house"
    if bucket == 5:
        return "flush"
    if bucket == 4:
        return "straight"

    hole_ranks = [card_rank(card) for card in hole]
    board_ranks = [card_rank(card) for card in board]
    top_board = max(board_ranks) if board_ranks else 0

    if bucket == 3:
        return "set" if hole_ranks[0] == hole_ranks[1] else "trips"
    if bucket == 2:
        return "two pair"
    if bucket == 1:
        pair_rank = score[1]
        if hole_ranks[0] == hole_ranks[1] and pair_rank == hole_ranks[0]:
            return "overpair" if pair_rank > top_board else "weak pair"
        if pair_rank == top_board:
            return "top pair"
        if pair_rank >= sorted(set(board_ranks))[len(set(board_ranks)) // 2]:
            return "middle pair"
        return "weak pair"
    return "air"


def _out_cards(hole: tuple[str, str], board: tuple[str, ...], available: frozenset[str]) -> set[str]:
    """Cards that complete a flush or a straight for this holding."""
    cards = (*hole, *board)
    suits = [card_suit(card) for card in cards]
    values = {card_rank(card) for card in cards}
    outs: set[str] = set()

    suit_counts = Counter(suits)
    for suit, count in suit_counts.items():
        if count == 4:
            outs.update(card for card in available if card_suit(card) == suit)

    if not _straight_high(values):
        for value in range(2, 15):
            if value in values:
                continue
            if _straight_high(values | {value}):
                rank = VALUE_RANKS[value]
                outs.update(card for card in available if card[0] == rank)
    return outs


# --------------------------------------------------------------------------------------
# Board analysis
# --------------------------------------------------------------------------------------


@dataclass(frozen=True)
class BoardAnalysis:
    board: tuple[str, ...]
    dead: tuple[str, ...]
    strengths: dict[str, HandStrength]
    combo_scores: dict[str, list[tuple[tuple[str, str], tuple[int, ...]]]]
    sorted_scores: list[tuple[int, ...]]

    def percentile_of_score(self, score: tuple[int, ...]) -> float:
        total = len(self.sorted_scores)
        if total == 0:
            return 0.5
        low = bisect_left(self.sorted_scores, score)
        high = bisect_right(self.sorted_scores, score)
        return (low + high) / (2.0 * total)


@lru_cache(maxsize=128)
def analyze_board(board: tuple[str, ...], dead: tuple[str, ...] = ()) -> BoardAnalysis:
    """Enumerate every live combo on this board and rank it. Memoized per (board, dead)."""
    board = normalize_cards(board)
    dead = tuple(card for card in normalize_cards(dead) if card not in board)
    used = set(board) | set(dead)
    deck = tuple(card for card in FULL_DECK if card not in used)
    available = frozenset(deck)
    street_multiplier = 0.04 if len(board) == 3 else 0.02 if len(board) == 4 else 0.0

    combo_scores: dict[str, list[tuple[tuple[str, str], tuple[int, ...]]]] = {hand: [] for hand in HAND_CLASSES}
    combo_draws: dict[str, list[float]] = {hand: [] for hand in HAND_CLASSES}
    combo_categories: dict[str, list[str]] = {hand: [] for hand in HAND_CLASSES}
    all_scores: list[tuple[int, ...]] = []

    for one, two in combinations(deck, 2):
        hand = hand_class_of(one, two)
        score = evaluate((one, two, *board))
        combo_scores[hand].append(((one, two), score))
        all_scores.append(score)
        category = _made_category((one, two), board, score)
        if street_multiplier > 0.0:
            remaining = available - {one, two}
            outs = len(_out_cards((one, two), board, remaining))
            draw = min(1.0, outs * street_multiplier)
            if category in {"air", "weak pair", "middle pair"} and outs >= 8:
                category = "flush draw" if outs >= 9 else "straight draw"
        else:
            draw = 0.0
        combo_draws[hand].append(draw)
        combo_categories[hand].append(category)

    all_scores.sort()
    total = len(all_scores)

    strengths: dict[str, HandStrength] = {}
    for hand in HAND_CLASSES:
        scores = combo_scores[hand]
        if not scores:
            strengths[hand] = HandStrength(made_percentile=0.0, category="blocked", draw_equity=0.0, live_combos=0)
            continue
        percentiles = []
        for _, score in scores:
            low = bisect_left(all_scores, score)
            high = bisect_right(all_scores, score)
            percentiles.append((low + high) / (2.0 * total))
        counts = Counter(combo_categories[hand])
        category = max(counts.items(), key=lambda item: (item[1], -CATEGORY_ORDER.index(item[0])))[0]
        strengths[hand] = HandStrength(
            made_percentile=sum(percentiles) / len(percentiles),
            category=category,
            draw_equity=sum(combo_draws[hand]) / len(combo_draws[hand]),
            live_combos=len(scores),
        )

    return BoardAnalysis(board=board, dead=dead, strengths=strengths, combo_scores=combo_scores, sorted_scores=all_scores)


def board_strength(board: list[str], dead: list[str] | None = None) -> dict[str, HandStrength]:
    """Per-hand-class board-relative strength for all 169 classes."""
    return analyze_board(normalize_cards(board), normalize_cards(dead or [])).strengths


# --------------------------------------------------------------------------------------
# Hero-side wrappers: one code path for hero and for opponent classes
# --------------------------------------------------------------------------------------


def holding_strength(hero_cards: list[str], board: list[str]) -> tuple[float, str]:
    """A specific holding's percentile and made-hand label on this board.

    Used for hero's cards and, at showdown, for the villain's tabled cards. One code path.
    """
    hero = normalize_cards(hero_cards)[:2]
    board_cards = normalize_cards(board)
    if len(hero) < 2 or len(board_cards) < 3:
        return 0.5, "unknown"
    analysis = analyze_board(board_cards, hero)
    score = evaluate((*hero, *board_cards))
    category = _made_category((hero[0], hero[1]), board_cards, score)
    return analysis.percentile_of_score(score), category


def hero_equity(distribution: dict[str, float], hero_cards: list[str], board: list[str]) -> float:
    """Showdown equity of hero's exact holding against the modeled range on this board."""
    hero = normalize_cards(hero_cards)[:2]
    board_cards = normalize_cards(board)
    if len(hero) < 2 or len(board_cards) < 3:
        return 0.5
    analysis = analyze_board(board_cards, hero)
    hero_score = evaluate((*hero, *board_cards))

    equity = 0.0
    weight_total = 0.0
    for hand, weight in distribution.items():
        combos = analysis.combo_scores.get(hand, [])
        if weight <= 0.0 or not combos:
            continue
        wins = sum(1.0 if hero_score > score else 0.5 if hero_score == score else 0.0 for _, score in combos)
        equity += weight * wins / len(combos)
        weight_total += weight
    if weight_total <= 0.0:
        return 0.5
    return equity / weight_total


def category_mix(distribution: dict[str, float], board: list[str], dead: list[str] | None = None) -> dict[str, float]:
    """Probability mass of the modeled range by board-relative category."""
    strengths = board_strength(board, dead)
    mix: dict[str, float] = {}
    total = 0.0
    for hand, weight in distribution.items():
        strength = strengths.get(hand)
        if strength is None or weight <= 0.0 or strength.live_combos == 0:
            continue
        mix[strength.category] = mix.get(strength.category, 0.0) + weight
        total += weight
    if total <= 0.0:
        return {}
    return {category: weight / total for category, weight in sorted(mix.items(), key=lambda item: -item[1])}


def apply_card_removal(
    distribution: dict[str, float],
    previous_dead: list[str],
    current_dead: list[str],
) -> dict[str, float]:
    """Re-weight a class distribution for newly revealed cards.

    Applied on the delta between two dead-card sets, so it is exact and idempotent:
    calling it with `previous_dead == current_dead` is a no-op. Classes whose combos
    are all blocked go to zero and can never come back, because the factor is zero.
    """
    previous = normalize_cards(previous_dead)
    current = normalize_cards(current_dead)
    if set(previous) == set(current):
        return dict(distribution)

    updated: dict[str, float] = {}
    for hand, weight in distribution.items():
        before = live_combos(hand, previous)
        after = live_combos(hand, current)
        if before <= 0 or after <= 0:
            updated[hand] = 0.0
        else:
            updated[hand] = weight * after / before
    return updated


# `hero_hand` is the historical name for the hero-side wrapper.
hero_hand = holding_strength

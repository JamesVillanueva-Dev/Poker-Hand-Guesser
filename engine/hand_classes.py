from __future__ import annotations

from math import log2

RANKS: tuple[str, ...] = ("A", "K", "Q", "J", "T", "9", "8", "7", "6", "5", "4", "3", "2")
SUITS: tuple[str, ...] = ("s", "h", "d", "c")


def generate_hand_classes() -> list[str]:
    classes: list[str] = []
    for row, high in enumerate(RANKS):
        for col, low in enumerate(RANKS):
            if row == col:
                classes.append(f"{high}{low}")
            elif row < col:
                classes.append(f"{high}{low}s")
            else:
                classes.append(f"{low}{high}o")
    return classes


HAND_CLASSES: tuple[str, ...] = tuple(generate_hand_classes())


def combo_count(hand_class: str) -> int:
    if len(hand_class) == 2:
        return 6
    if hand_class.endswith("s"):
        return 4
    return 12


def uniform_distribution(weight_by_combos: bool = True) -> dict[str, float]:
    if weight_by_combos:
        total = sum(combo_count(hand) for hand in HAND_CLASSES)
        return {hand: combo_count(hand) / total for hand in HAND_CLASSES}
    value = 1.0 / len(HAND_CLASSES)
    return {hand: value for hand in HAND_CLASSES}


def normalize(distribution: dict[str, float]) -> dict[str, float]:
    clipped = {hand: max(0.0, float(distribution.get(hand, 0.0))) for hand in HAND_CLASSES}
    total = sum(clipped.values())
    if total <= 0.0:
        return uniform_distribution()
    return {hand: value / total for hand, value in clipped.items()}


def distribution_entropy(distribution: dict[str, float]) -> float:
    normalized = normalize(distribution)
    return -sum(probability * log2(probability) for probability in normalized.values() if probability > 0.0)


CHEN_VALUES: dict[str, float] = {
    "A": 10.0,
    "K": 8.0,
    "Q": 7.0,
    "J": 6.0,
    "T": 5.0,
    "9": 4.5,
    "8": 4.0,
    "7": 3.5,
    "6": 3.0,
    "5": 2.5,
    "4": 2.0,
    "3": 1.5,
    "2": 1.0,
}
GAP_PENALTIES: dict[int, float] = {0: 0.0, 1: -1.0, 2: -2.0, 3: -4.0}
CHEN_MIN: float = -1.5  # 72o
CHEN_MAX: float = 20.0  # AA


def hand_strength_bucket(hand_class: str) -> float:
    """Preflop-only strength prior, on the Chen formula, normalized to (0, 1].

    Used before the flop and nowhere else: once there is a board, strength comes from
    `engine.evaluator.board_strength`. Chen is used because it prices pocket pairs
    against broadway offsuit hands roughly the way their all-in equity does.
    """
    high, low = hand_class[0], hand_class[1]
    high_index, low_index = RANKS.index(high), RANKS.index(low)

    if len(hand_class) == 2:
        score = max(5.0, CHEN_VALUES[high] * 2.0)
    else:
        score = CHEN_VALUES[RANKS[min(high_index, low_index)]]
        if hand_class.endswith("s"):
            score += 2.0
        gap = abs(high_index - low_index) - 1
        score += GAP_PENALTIES.get(gap, -5.0)
        if gap <= 1 and min(high_index, low_index) > RANKS.index("Q"):
            score += 1.0  # both cards below a queen: straight potential

    return max(0.01, min(1.0, (score - CHEN_MIN) / (CHEN_MAX - CHEN_MIN)))


def matrix_cells(distribution: dict[str, float], dead: list[str] | None = None) -> list[dict[str, object]]:
    """Grid cells for the heatmap. `combo_count` is live combos once cards are known."""
    from engine.evaluator import live_combos  # local import: evaluator imports this module

    normalized = normalize(distribution)
    cells: list[dict[str, object]] = []
    for row, rank_row in enumerate(RANKS):
        for col, rank_col in enumerate(RANKS):
            if row == col:
                hand = f"{rank_row}{rank_col}"
            elif row < col:
                hand = f"{rank_row}{rank_col}s"
            else:
                hand = f"{rank_col}{rank_row}o"
            cells.append(
                {
                    "hand": hand,
                    "row": row,
                    "col": col,
                    "probability": normalized[hand],
                    "combo_count": live_combos(hand, dead) if dead else combo_count(hand),
                }
            )
    return cells

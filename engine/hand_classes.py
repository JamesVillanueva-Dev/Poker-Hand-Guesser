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


def hand_strength_bucket(hand_class: str) -> float:
    first = RANKS.index(hand_class[0])
    second = RANKS.index(hand_class[1])
    high_score = (12 - min(first, second)) / 12
    low_score = (12 - max(first, second)) / 12
    pair_bonus = 0.28 if len(hand_class) == 2 else 0.0
    suited_bonus = 0.08 if hand_class.endswith("s") else 0.0
    connected_bonus = max(0.0, 0.09 - abs(first - second) * 0.018) if len(hand_class) == 3 else 0.0
    broadway_bonus = 0.08 if first <= 4 and second <= 4 else 0.0
    ace_bonus = 0.05 if "A" in hand_class else 0.0
    raw = 0.48 * high_score + 0.22 * low_score + pair_bonus + suited_bonus + connected_bonus + broadway_bonus + ace_bonus
    return max(0.01, min(1.0, raw))


def matrix_cells(distribution: dict[str, float]) -> list[dict[str, object]]:
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
                    "combo_count": combo_count(hand),
                }
            )
    return cells

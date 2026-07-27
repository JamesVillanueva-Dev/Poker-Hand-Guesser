"""Emit the training dataset that `training/dataset.py` has always expected.

Every scored showdown appends JSONL rows of `{"features": [...], "label": 0|1}`, where
the label says whether that hand class was the one the opponent actually held. This is
the only producer of that file; before this module existed the training pipeline had no
input at all.

Rows are negative-sampled (one positive plus `NEGATIVES_PER_ROW` others drawn without
replacement, seeded by hand id so a re-scored hand reproduces the same rows) to keep the
file from growing by 169 rows per street per hand.
"""

from __future__ import annotations

import json
import random
from pathlib import Path
from typing import Any

from engine.evaluator import board_strength, live_combos
from engine.hand_classes import HAND_CLASSES, hand_strength_bucket
from engine.state import PlayerProfile, Street

DATASET_PATH = Path(__file__).resolve().parent / "data" / "showdowns.jsonl"
NEGATIVES_PER_ROW = 16

FEATURE_NAMES: tuple[str, ...] = (
    "made_percentile",
    "draw_equity",
    "live_combos_norm",
    "prior_probability",
    "prior_log_odds",
    "preflop_bucket",
    "street_index",
    "board_cards_seen",
    "bet_fraction_pot",
    "raise_level",
    "facing_bet",
    "vpip",
    "pfr",
    "three_bet",
    "cbet",
    "aggression_norm",
    "river_aggression_norm",
    "bluff_frequency",
)

STREET_INDEX: dict[str, int] = {
    Street.PREFLOP.value: 0,
    Street.FLOP.value: 1,
    Street.TURN.value: 2,
    Street.RIVER.value: 3,
}


def build_features(
    hand_class: str,
    distribution: dict[str, float],
    board_cards: list[str],
    hero_cards: list[str],
    street: str,
    profile: PlayerProfile,
    bet_fraction_pot: float = 0.0,
    raise_level: int = 0,
    facing_bet: bool = False,
) -> list[float]:
    dead = [*board_cards, *hero_cards]
    if len(board_cards) >= 3:
        strength = board_strength(board_cards, hero_cards)[hand_class]
        made, draw, combos = strength.made_percentile, strength.draw_equity, strength.live_combos
    else:
        made, draw, combos = 0.0, 0.0, live_combos(hand_class, dead)

    prior = max(1e-9, float(distribution.get(hand_class, 0.0)))
    return [
        made,
        draw,
        combos / 12.0,
        prior,
        prior / (1.0 - min(0.999999, prior)),
        hand_strength_bucket(hand_class),
        STREET_INDEX.get(street, 0) / 3.0,
        len(board_cards) / 5.0,
        min(3.0, bet_fraction_pot),
        raise_level / 3.0,
        1.0 if facing_bet else 0.0,
        profile.vpip,
        profile.pfr,
        profile.three_bet,
        profile.cbet,
        profile.aggression / (profile.aggression + 1.0),
        profile.river_aggression / (profile.river_aggression + 1.0),
        profile.bluff_frequency,
    ]


def build_examples(
    hand_id: str,
    true_class: str,
    distribution: dict[str, float],
    board_cards: list[str],
    hero_cards: list[str],
    street: str,
    profile: PlayerProfile,
    bet_fraction_pot: float = 0.0,
    raise_level: int = 0,
    facing_bet: bool = False,
    negatives: int = NEGATIVES_PER_ROW,
) -> list[dict[str, Any]]:
    rng = random.Random(f"{hand_id}:{street}")
    candidates = [hand for hand in HAND_CLASSES if hand != true_class]
    sampled = rng.sample(candidates, min(negatives, len(candidates)))

    rows: list[dict[str, Any]] = []
    for hand_class in [true_class, *sampled]:
        rows.append(
            {
                "features": build_features(
                    hand_class,
                    distribution,
                    board_cards,
                    hero_cards,
                    street,
                    profile,
                    bet_fraction_pot,
                    raise_level,
                    facing_bet,
                ),
                "label": 1.0 if hand_class == true_class else 0.0,
                "meta": {"hand_id": hand_id, "street": street, "hand_class": hand_class},
            }
        )
    return rows


def append_examples(rows: list[dict[str, Any]], path: Path | None = None) -> int:
    if not rows:
        return 0
    path = path or DATASET_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row) + "\n")
    return len(rows)

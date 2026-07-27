"""The training pipeline finally has an input, and it is the shape it always expected."""

from __future__ import annotations

import json
from pathlib import Path

from engine.hand_classes import uniform_distribution
from engine.state import PlayerProfile, Street
from training.collect import FEATURE_NAMES, append_examples, build_examples, build_features


def test_features_are_finite_and_fixed_width() -> None:
    features = build_features(
        "77",
        uniform_distribution(),
        ["Ks", "7d", "2c"],
        ["Ah", "Qd"],
        Street.FLOP.value,
        PlayerProfile("v"),
        bet_fraction_pot=0.9,
    )
    assert len(features) == len(FEATURE_NAMES)
    assert all(isinstance(value, float) for value in features)
    assert all(value == value for value in features), "no NaNs"


def test_board_relative_strength_reaches_the_features() -> None:
    board, hero = ["Ks", "7d", "2c"], ["Ah", "Qd"]
    index = FEATURE_NAMES.index("made_percentile")
    trips = build_features("77", uniform_distribution(), board, hero, Street.FLOP.value, PlayerProfile("v"))
    air = build_features("T9o", uniform_distribution(), board, hero, Street.FLOP.value, PlayerProfile("v"))
    assert trips[index] > air[index]


def test_examples_carry_exactly_one_positive_label() -> None:
    rows = build_examples(
        hand_id="h1",
        true_class="KQo",
        distribution=uniform_distribution(),
        board_cards=["Ks", "7d", "2c"],
        hero_cards=[],
        street=Street.FLOP.value,
        profile=PlayerProfile("v"),
        negatives=8,
    )
    assert len(rows) == 9
    assert sum(row["label"] for row in rows) == 1.0
    positive = next(row for row in rows if row["label"] == 1.0)
    assert positive["meta"]["hand_class"] == "KQo"


def test_examples_are_deterministic_for_the_same_hand() -> None:
    kwargs = dict(
        hand_id="h1",
        true_class="KQo",
        distribution=uniform_distribution(),
        board_cards=["Ks", "7d", "2c"],
        hero_cards=[],
        street=Street.FLOP.value,
        profile=PlayerProfile("v"),
    )
    assert build_examples(**kwargs) == build_examples(**kwargs)


def test_dataset_round_trips_through_the_existing_loader(dataset_path: Path) -> None:
    rows = build_examples(
        hand_id="h1",
        true_class="AA",
        distribution=uniform_distribution(),
        board_cards=[],
        hero_cards=[],
        street=Street.PREFLOP.value,
        profile=PlayerProfile("v"),
        negatives=4,
    )
    assert append_examples(rows, dataset_path) == 5
    assert append_examples(rows, dataset_path) == 5

    lines = [json.loads(line) for line in dataset_path.read_text(encoding="utf-8").splitlines() if line.strip()]
    assert len(lines) == 10
    for line in lines:
        assert set(line) >= {"features", "label"}
        assert isinstance(line["features"], list)
        assert line["label"] in {0.0, 1.0}

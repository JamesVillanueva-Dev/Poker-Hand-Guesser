"""Acceptance criteria for board-relative hand strength (§2)."""

from __future__ import annotations

from engine.evaluator import (
    HAND_CLASSES,
    analyze_board,
    apply_card_removal,
    board_strength,
    evaluate,
    hand_class_of,
    holding_strength,
    live_combos,
)


def test_flopped_set_outranks_air_regression() -> None:
    """The exact inversion this rebuild exists to fix.

    A board-blind ranking calls 77 mediocre (~0.53) and AQo strong (~0.72) on K72.
    On the actual board 77 is a set and AQo has not made a pair.
    """
    strengths = board_strength(["Ks", "7d", "2c"])
    assert strengths["77"].made_percentile > strengths["AQo"].made_percentile
    assert strengths["77"].category == "set"
    assert strengths["AQo"].category == "air"


def test_monotone_ranking_on_a_dry_board() -> None:
    strengths = board_strength(["Ks", "7d", "2c"])
    ordered = ["KK", "77", "22", "KQo", "K9o", "A5s", "65s"]
    percentiles = [strengths[hand].made_percentile for hand in ordered]
    assert percentiles == sorted(percentiles, reverse=True), dict(zip(ordered, percentiles))


def test_royal_flush_board_orders_suited_above_offsuit() -> None:
    board = ["As", "Ks", "Qs"]
    royal = evaluate(("Js", "Ts", *board))
    straight = evaluate(("Jh", "Th", *board))
    assert royal > straight

    strengths = board_strength(board)
    for suited, offsuit in (("JTs", "JTo"), ("T9s", "T9o"), ("98s", "98o")):
        assert strengths[suited].made_percentile > strengths[offsuit].made_percentile
    assert strengths["JTs"].made_percentile == max(
        strength.made_percentile for strength in strengths.values()
    )


def test_card_removal_from_the_board() -> None:
    strengths = board_strength(["As", "Ah", "Kd"])
    assert strengths["AA"].live_combos == 1
    assert strengths["KK"].live_combos == 3
    assert strengths["QQ"].live_combos == 6


def test_card_removal_includes_hero_cards() -> None:
    strengths = board_strength(["As", "7d", "2c"], ["Ac", "Kc"])
    assert strengths["AA"].live_combos == 1
    # Two aces and three kings remain: 6 AK combos total, 2 of them suited.
    assert strengths["AKs"].live_combos == 2
    assert strengths["AKo"].live_combos == 4
    assert strengths["AKs"].live_combos + strengths["AKo"].live_combos == 6


def test_every_percentile_is_a_probability() -> None:
    for board in (["Ks", "7d", "2c"], ["9s", "8s", "2h", "Jd"], ["As", "Ks", "Qs", "2h", "7c"]):
        for hand, strength in board_strength(board).items():
            assert 0.0 <= strength.made_percentile <= 1.0, (board, hand)
            assert 0.0 <= strength.draw_equity <= 1.0, (board, hand)
            assert strength.live_combos >= 0


def test_blocked_classes_report_zero_combos() -> None:
    strengths = board_strength(["As", "Ah", "Ad"], ["Ac", "Kc"])
    assert strengths["AA"].live_combos == 0
    assert strengths["AA"].made_percentile == 0.0


def test_draws_carry_equity_and_air_does_not() -> None:
    strengths = board_strength(["9s", "8s", "2h"])
    assert strengths["JTs"].draw_equity > 0.2
    assert strengths["JTs"].category in {"straight draw", "flush draw"}
    dry = board_strength(["Ks", "7d", "2c"])
    assert dry["A5s"].draw_equity == 0.0


def test_river_has_no_draw_equity() -> None:
    for strength in board_strength(["Ks", "7d", "2c", "Jh", "4s"]).values():
        assert strength.draw_equity == 0.0


def test_hand_class_of_round_trips() -> None:
    assert hand_class_of("Ah", "Ad") == "AA"
    assert hand_class_of("Ah", "Kh") == "AKs"
    assert hand_class_of("Kd", "Ah") == "AKo"
    assert hand_class_of("2c", "7d") == "72o"


def test_holding_strength_matches_the_board_ranking() -> None:
    board = ["Ks", "7d", "2c"]
    set_percentile, set_label = holding_strength(["7h", "7c"], board)
    air_percentile, air_label = holding_strength(["Ah", "Qd"], board)
    assert set_percentile > air_percentile
    assert set_label == "set"
    assert air_label == "air"


def test_apply_card_removal_is_exact_and_idempotent() -> None:
    base = {hand: 1.0 for hand in HAND_CLASSES}
    unchanged = apply_card_removal(base, ["Ks"], ["Ks"])
    assert unchanged == base

    after = apply_card_removal(base, [], ["As", "Ah", "Ad"])
    assert after["AA"] == 1.0 * live_combos("AA", ["As", "Ah", "Ad"]) / 6
    assert after["KK"] == 1.0

    dead_class = apply_card_removal({"AA": 1.0}, [], ["As", "Ah", "Ad", "Ac"])
    assert dead_class["AA"] == 0.0
    # Once zero, no later removal can bring it back.
    assert apply_card_removal(dead_class, ["As", "Ah", "Ad", "Ac"], ["As", "Ah", "Ad", "Ac", "2h"])["AA"] == 0.0


def test_analysis_is_memoized_per_board() -> None:
    first = analyze_board(("Ks", "7d", "2c"), ())
    second = analyze_board(("Ks", "7d", "2c"), ())
    assert first is second
    assert len(first.sorted_scores) == 1176  # C(49, 2)

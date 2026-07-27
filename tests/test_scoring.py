"""Grading the prediction against the truth (§4)."""

from __future__ import annotations

from math import isfinite

from engine.hand_classes import HAND_CLASSES, uniform_distribution
from engine.scoring import BASELINE_LOG_LOSS, plain_language, score_prediction, summarize_scores


def test_baseline_is_the_uniform_guess() -> None:
    assert abs(BASELINE_LOG_LOSS - 7.4009) < 1e-3


def test_perfect_prediction_scores_the_full_baseline() -> None:
    score = score_prediction({"AA": 1.0}, "AA")
    assert score.log_loss < 1e-9
    assert abs(score.skill - BASELINE_LOG_LOSS) < 1e-9
    assert score.top_10_hit is True


def test_uniform_prediction_scores_exactly_zero_skill() -> None:
    uniform = {hand: 1.0 / len(HAND_CLASSES) for hand in HAND_CLASSES}
    score = score_prediction(uniform, "72o")
    assert abs(score.skill) < 1e-9
    assert abs(score.log_loss - BASELINE_LOG_LOSS) < 1e-9


def test_zero_mass_on_the_true_class_is_finite() -> None:
    """Card removal or a bad fold read can zero out the hand they actually held.

    That must cost a lot and must not take down the endpoint.
    """
    distribution = {hand: (0.0 if hand == "AA" else 1.0) for hand in HAND_CLASSES}
    score = score_prediction(distribution, "AA")
    assert isfinite(score.log_loss)
    assert isfinite(score.skill)
    assert score.skill < -10.0
    assert score.predicted_probability == 0.0
    assert score.top_10_hit is False


def test_confident_and_right_beats_confident_and_wrong() -> None:
    confident = {hand: 0.0 for hand in HAND_CLASSES}
    confident["AA"] = 0.9
    confident["KK"] = 0.1
    assert score_prediction(confident, "AA").skill > score_prediction(confident, "KK").skill
    assert score_prediction(confident, "KK").skill > score_prediction(confident, "72o").skill


def test_percentile_is_a_probability_and_tracks_rank() -> None:
    distribution = {hand: 0.0 for hand in HAND_CLASSES}
    distribution["AA"] = 0.5
    distribution["KK"] = 0.3
    distribution["QQ"] = 0.2
    assert 0.0 <= score_prediction(distribution, "AA").percentile <= 1.0
    assert score_prediction(distribution, "AA").percentile > score_prediction(distribution, "QQ").percentile


def test_top_10_hit_tracks_the_leading_tenth_of_mass() -> None:
    distribution = {hand: 0.0 for hand in HAND_CLASSES}
    distribution["AA"] = 0.5
    distribution["KK"] = 0.5
    assert score_prediction(distribution, "AA").top_10_hit is True
    assert score_prediction(uniform_distribution(), "72o").top_10_hit is False


def test_summary_reports_a_negative_result_plainly() -> None:
    losing = [{"skill": -1.5, "log_loss": 8.9, "top_10_hit": False} for _ in range(4)]
    summary = summarize_scores(losing)
    assert summary["count"] == 4
    assert summary["mean_skill"] < 0
    sentence = plain_language(summary)
    assert "worse" in sentence and "not beating a coin flip" in sentence

    winning = [{"skill": 2.3, "log_loss": 5.1, "top_10_hit": True} for _ in range(47)]
    assert "2.30 bits better" in plain_language(summarize_scores(winning))
    assert "No showdowns scored yet" in plain_language(summarize_scores([]))

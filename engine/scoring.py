"""Grading the model against the truth revealed at showdown.

Everything the app claims about its own accuracy comes from here. The unit is bits:
`skill = -log2(1/169) - (-log2 P(true class))`. Positive means the model beat a uniform
guess over the 169 classes; zero means it did not.
"""

from __future__ import annotations

from dataclasses import dataclass, asdict
from math import log2

from engine.hand_classes import HAND_CLASSES, normalize

BASELINE_LOG_LOSS: float = log2(len(HAND_CLASSES))  # 7.401 bits
PROBABILITY_FLOOR: float = 1e-6  # a zeroed-out class must cost a lot, but must not be inf


@dataclass(frozen=True)
class PredictionScore:
    log_loss: float
    baseline_log_loss: float
    skill: float
    percentile: float
    top_10_hit: bool
    predicted_probability: float

    def as_dict(self) -> dict[str, float | bool]:
        return asdict(self)


def score_prediction(distribution: dict[str, float], true_class: str) -> PredictionScore:
    """Score one predicted range against the hand the opponent actually held."""
    normalized = normalize(distribution)
    probability = normalized.get(true_class, 0.0)
    floored = max(probability, PROBABILITY_FLOOR)
    log_loss = -log2(floored)

    # Probability-integral-transform percentile: the chance that a hand drawn from the
    # prediction ranks below the truth. A perfectly calibrated model spreads this
    # uniformly over [0, 1]; a model that is confidently wrong pushes it to 0.
    below = sum(weight for hand, weight in normalized.items() if weight < probability)
    tied = sum(weight for hand, weight in normalized.items() if weight == probability)
    percentile = below + 0.5 * tied

    ranked = sorted(normalized.items(), key=lambda item: -item[1])
    cumulative = 0.0
    top_set: set[str] = set()
    for hand, weight in ranked:
        top_set.add(hand)
        cumulative += weight
        if cumulative >= 0.10:
            break

    return PredictionScore(
        log_loss=log_loss,
        baseline_log_loss=BASELINE_LOG_LOSS,
        skill=BASELINE_LOG_LOSS - log_loss,
        percentile=percentile,
        top_10_hit=true_class in top_set,
        predicted_probability=probability,
    )


def summarize_scores(scores: list[dict[str, float]]) -> dict[str, float | int]:
    """Running skill over a set of persisted prediction rows."""
    if not scores:
        return {"count": 0, "mean_skill": 0.0, "mean_log_loss": 0.0, "top_10_rate": 0.0}
    count = len(scores)
    return {
        "count": count,
        "mean_skill": sum(float(row["skill"]) for row in scores) / count,
        "mean_log_loss": sum(float(row["log_loss"]) for row in scores) / count,
        "top_10_rate": sum(1.0 for row in scores if row.get("top_10_hit")) / count,
    }


def plain_language(summary: dict[str, float | int]) -> str:
    """The sentence the dashboard shows. It must say so when the model is not winning."""
    count = int(summary.get("count", 0))
    if count == 0:
        return "No showdowns scored yet. This model has not been measured against a single known hand."
    skill = float(summary.get("mean_skill", 0.0))
    if skill <= 0.0:
        return (
            f"Over {count} scored showdown{'s' if count != 1 else ''}, this model is "
            f"{abs(skill):.2f} bits *worse* than random guessing. It is not beating a coin flip yet."
        )
    return (
        f"Over {count} scored showdown{'s' if count != 1 else ''}, this model is "
        f"{skill:.2f} bits better than random guessing."
    )

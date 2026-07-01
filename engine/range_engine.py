from __future__ import annotations

from dataclasses import dataclass, field

from engine.hand_classes import HAND_CLASSES, distribution_entropy, matrix_cells, normalize, uniform_distribution
from engine.likelihood import HeuristicLikelihood, LikelihoodModel
from engine.state import BoardState, PlayerProfile, PokerAction


@dataclass
class RangeSnapshot:
    sequence: int
    action_label: str
    distribution: dict[str, float]
    entropy: float


@dataclass
class RangeEstimator:
    likelihood_model: LikelihoodModel = field(default_factory=HeuristicLikelihood)

    def initial_distribution(self) -> dict[str, float]:
        return uniform_distribution(weight_by_combos=True)

    def update_range(
        self,
        current_distribution: dict[str, float],
        action: PokerAction,
        board_state: BoardState,
        player_profile: PlayerProfile,
    ) -> dict[str, float]:
        prior = normalize(current_distribution)
        unnormalized: dict[str, float] = {}
        for hand in HAND_CLASSES:
            likelihood = self.likelihood_model.probability(hand, action, board_state, player_profile)
            unnormalized[hand] = prior[hand] * likelihood
        return normalize(unnormalized)

    def summarize(self, distribution: dict[str, float], limit: int = 20) -> dict[str, object]:
        normalized = normalize(distribution)
        top_hands = sorted(normalized.items(), key=lambda item: item[1], reverse=True)[:limit]
        return {
            "distribution": normalized,
            "top_hands": [{"hand": hand, "probability": probability} for hand, probability in top_hands],
            "matrix": matrix_cells(normalized),
            "entropy": distribution_entropy(normalized),
        }


def action_label(action: PokerAction) -> str:
    actor = "Hero" if action.actor.value == "hero" else "Opponent"
    return f"{action.street.value.title()} {actor} {action.position} {action.action_type.value.replace('_', ' ').title()}"

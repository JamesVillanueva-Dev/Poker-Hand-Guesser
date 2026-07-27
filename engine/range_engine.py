from __future__ import annotations

from dataclasses import dataclass, field

from engine.evaluator import apply_card_removal
from engine.hand_classes import HAND_CLASSES, distribution_entropy, matrix_cells, normalize, uniform_distribution
from engine.likelihood import HeuristicLikelihood, LikelihoodModel, legal_actions
from engine.state import ActionContext, ActionType, BoardState, PlayerProfile, PokerAction, build_action_context


@dataclass
class RangeSnapshot:
    sequence: int
    action_label: str
    distribution: dict[str, float]
    entropy: float


@dataclass
class RangeEstimator:
    likelihood_model: LikelihoodModel = field(default_factory=HeuristicLikelihood)

    def initial_distribution(self, dead: list[str] | None = None) -> dict[str, float]:
        base = uniform_distribution(weight_by_combos=True)
        if not dead:
            return base
        return normalize(apply_card_removal(base, [], dead))

    def update_range(
        self,
        current_distribution: dict[str, float],
        action: PokerAction,
        board_state: BoardState,
        player_profile: PlayerProfile,
        previous_dead: list[str] | None = None,
    ) -> dict[str, float]:
        """One Bayesian update: P(h | a) ∝ P(h) · π(a | h, board, profile, context)."""
        dead = [*board_state.board_cards, *board_state.hero_cards]
        prior = normalize(
            apply_card_removal(current_distribution, dead if previous_dead is None else previous_dead, dead)
        )

        context = build_action_context(board_state, action)
        legal = legal_actions(context, action.action_type)
        context = self.likelihood_model.calibrate(prior, legal, board_state, player_profile, context)

        posterior: dict[str, float] = {}
        for hand in HAND_CLASSES:
            weight = prior[hand]
            if weight <= 0.0:
                posterior[hand] = 0.0
                continue
            probabilities = self.likelihood_model.action_probabilities(
                hand, legal, board_state, player_profile, context
            )
            posterior[hand] = weight * probabilities[action.action_type]
        return normalize(posterior)

    def policy_snapshot(
        self,
        distribution: dict[str, float],
        board_state: BoardState,
        player_profile: PlayerProfile,
        action: PokerAction,
    ) -> tuple[ActionContext, list[ActionType], dict[str, dict[ActionType, float]]]:
        """Calibrated context, legal actions, and each class's action distribution."""
        prior = normalize(distribution)
        context = build_action_context(board_state, action)
        legal = legal_actions(context, action.action_type)
        context = self.likelihood_model.calibrate(prior, legal, board_state, player_profile, context)
        policies = {
            hand: self.likelihood_model.action_probabilities(hand, legal, board_state, player_profile, context)
            for hand in HAND_CLASSES
        }
        return context, legal, policies

    def summarize(
        self,
        distribution: dict[str, float],
        dead: list[str] | None = None,
        limit: int = 20,
    ) -> dict[str, object]:
        normalized = normalize(distribution)
        top_hands = sorted(normalized.items(), key=lambda item: item[1], reverse=True)[:limit]
        return {
            "distribution": normalized,
            "top_hands": [{"hand": hand, "probability": probability} for hand, probability in top_hands],
            "matrix": matrix_cells(normalized, dead),
            "entropy": distribution_entropy(normalized),
        }


def action_label(action: PokerAction) -> str:
    actor = "Hero" if action.actor.value == "hero" else "Opponent"
    return f"{action.street.value.title()} {actor} {action.position} {action.action_type.value.replace('_', ' ').title()}"

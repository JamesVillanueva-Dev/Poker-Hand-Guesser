from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from engine.hand_classes import hand_strength_bucket
from engine.state import ActionType, BoardState, PlayerProfile, PokerAction, Street


class LikelihoodModel(Protocol):
    def probability(self, hand_class: str, action: PokerAction, board_state: BoardState, player_profile: PlayerProfile) -> float:
        ...


@dataclass
class HeuristicLikelihood:
    min_probability: float = 0.015

    def probability(self, hand_class: str, action: PokerAction, board_state: BoardState, player_profile: PlayerProfile) -> float:
        strength = hand_strength_bucket(hand_class)
        sizing = max(action.bet_fraction_pot, action.amount / action.pot_before if action.pot_before > 0 else 0.0)
        aggression = max(0.15, player_profile.aggression)
        bluff = max(0.02, min(0.65, player_profile.bluff_frequency))

        if action.street == Street.PREFLOP:
            likelihood = self._preflop_likelihood(strength, action, player_profile)
        else:
            likelihood = self._postflop_likelihood(strength, sizing, action, player_profile, aggression, bluff)

        return max(self.min_probability, likelihood)

    def _preflop_likelihood(self, strength: float, action: PokerAction, profile: PlayerProfile) -> float:
        openness = max(0.04, min(0.8, profile.vpip))
        raise_bias = max(0.03, min(0.65, profile.pfr))

        match action.action_type:
            case ActionType.FOLD:
                return 1.15 - 0.92 * strength
            case ActionType.CHECK | ActionType.CALL:
                return openness * (0.65 + 0.5 * (1.0 - abs(strength - 0.45)))
            case ActionType.RAISE:
                return raise_bias * (0.28 + 1.75 * strength**1.65)
            case ActionType.THREE_BET:
                return profile.three_bet * (0.2 + 2.35 * strength**2.25)
            case ActionType.FOUR_BET | ActionType.JAM:
                return 0.03 + 1.85 * strength**3.1
            case _:
                return 0.5

    def _postflop_likelihood(
        self,
        strength: float,
        sizing: float,
        action: PokerAction,
        profile: PlayerProfile,
        aggression: float,
        bluff: float,
    ) -> float:
        big_bet_pressure = min(1.0, max(0.0, sizing))
        value_component = 0.18 + 1.65 * strength ** (1.3 + big_bet_pressure)
        bluff_component = bluff * (0.75 - 0.38 * strength)

        match action.action_type:
            case ActionType.FOLD:
                return 1.12 - 0.78 * strength
            case ActionType.CHECK:
                return 0.75 + 0.38 * (1.0 - strength) / max(0.65, aggression)
            case ActionType.CALL:
                return 0.45 + 0.9 * (1.0 - abs(strength - 0.58))
            case ActionType.BET | ActionType.RAISE:
                cbet = profile.cbet if action.street == Street.FLOP else 0.5 + 0.12 * aggression
                return cbet * (value_component + bluff_component)
            case ActionType.JAM:
                river_factor = profile.river_aggression if action.street == Street.RIVER else aggression
                return (0.08 + 2.25 * strength**2.7 + bluff_component) * max(0.45, river_factor)
            case _:
                return 0.5


@dataclass
class NeuralLikelihood:
    model_path: str | None = None

    def probability(self, hand_class: str, action: PokerAction, board_state: BoardState, player_profile: PlayerProfile) -> float:
        raise NotImplementedError("NeuralLikelihood is a plug-in point for a trained PyTorch likelihood model.")

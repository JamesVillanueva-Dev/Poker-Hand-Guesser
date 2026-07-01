from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum


class Street(StrEnum):
    PREFLOP = "preflop"
    FLOP = "flop"
    TURN = "turn"
    RIVER = "river"


class ActionType(StrEnum):
    FOLD = "fold"
    CHECK = "check"
    CALL = "call"
    BET = "bet"
    RAISE = "raise"
    THREE_BET = "three_bet"
    FOUR_BET = "four_bet"
    JAM = "jam"


class ActionActor(StrEnum):
    HERO = "hero"
    OPPONENT = "opponent"


@dataclass(frozen=True)
class PokerAction:
    player_id: str
    action_type: ActionType
    street: Street
    position: str
    actor: ActionActor = ActionActor.OPPONENT
    amount: float = 0.0
    pot_before: float = 0.0
    bet_fraction_pot: float = 0.0
    sequence: int = 0


@dataclass
class BoardState:
    street: Street = Street.PREFLOP
    board_cards: list[str] = field(default_factory=list)
    hero_cards: list[str] = field(default_factory=list)
    pot: float = 0.0
    effective_stack: float = 0.0
    position: str = "BTN"
    previous_actions: list[PokerAction] = field(default_factory=list)


@dataclass
class PlayerProfile:
    player_id: str
    vpip: float = 0.24
    pfr: float = 0.16
    three_bet: float = 0.07
    fold_to_three_bet: float = 0.47
    cbet: float = 0.55
    aggression: float = 1.7
    river_aggression: float = 1.2
    bluff_frequency: float = 0.22
    showdown_frequency: float = 0.28
    hands_observed: int = 0

    def as_dict(self) -> dict[str, float | int | str]:
        return {
            "player_id": self.player_id,
            "vpip": self.vpip,
            "pfr": self.pfr,
            "three_bet": self.three_bet,
            "fold_to_three_bet": self.fold_to_three_bet,
            "cbet": self.cbet,
            "aggression": self.aggression,
            "river_aggression": self.river_aggression,
            "bluff_frequency": self.bluff_frequency,
            "showdown_frequency": self.showdown_frequency,
            "hands_observed": self.hands_observed,
        }

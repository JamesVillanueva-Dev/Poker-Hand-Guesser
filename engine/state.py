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


AGGRESSIVE_ACTIONS: frozenset[ActionType] = frozenset(
    {ActionType.BET, ActionType.RAISE, ActionType.THREE_BET, ActionType.FOUR_BET, ActionType.JAM}
)
PASSIVE_ACTIONS: frozenset[ActionType] = frozenset({ActionType.CHECK, ActionType.CALL})
VOLUNTARY_ACTIONS: frozenset[ActionType] = AGGRESSIVE_ACTIONS | {ActionType.CALL}


@dataclass
class ActionContext:
    """Everything about the spot that is not the opponent's cards.

    Built from the observed action history so the policy can score only actions that
    are actually legal, and so hero's own aggression shifts the read on the opponent.
    """

    street: Street = Street.PREFLOP
    raise_level: int = 0
    facing_bet: bool = False
    bet_fraction_pot: float = 0.0
    pot_odds: float = 0.0
    opponent_is_preflop_aggressor: bool = False
    hero_aggressive_actions: int = 0
    hero_three_bet: bool = False
    hero_last_action: ActionType | None = None
    continue_tilt: float = 0.0
    aggression_tilt: float = 0.0


def build_action_context(board_state: BoardState, action: PokerAction) -> ActionContext:
    """Derive the legal-action context for `action` from what came before it."""
    history = [previous for previous in board_state.previous_actions if previous.sequence < action.sequence]
    street_history = [previous for previous in history if previous.street == action.street]

    raise_level = 0
    facing_bet = False
    facing_amount = 0.0
    for previous in street_history:
        if previous.action_type in {ActionType.BET, ActionType.RAISE}:
            raise_level += 1
            facing_bet = True
            facing_amount = previous.amount
        elif previous.action_type == ActionType.THREE_BET:
            raise_level = max(raise_level, 2)
            facing_bet = True
            facing_amount = previous.amount
        elif previous.action_type == ActionType.FOUR_BET:
            raise_level = max(raise_level, 3)
            facing_bet = True
            facing_amount = previous.amount
        elif previous.action_type == ActionType.JAM:
            raise_level = max(raise_level, 3)
            facing_bet = True
            facing_amount = previous.amount
        elif previous.action_type in {ActionType.CALL, ActionType.CHECK, ActionType.FOLD}:
            if previous.actor == action.actor:
                continue
            facing_bet = facing_bet and previous.action_type != ActionType.CALL
            if previous.action_type == ActionType.CALL:
                facing_amount = 0.0

    preflop_raisers = [
        previous
        for previous in history
        if previous.street == Street.PREFLOP and previous.action_type in AGGRESSIVE_ACTIONS
    ]
    opponent_is_preflop_aggressor = bool(preflop_raisers) and preflop_raisers[-1].actor == action.actor

    hero_actions = [previous for previous in history if previous.actor != action.actor]
    hero_aggressive = [previous for previous in hero_actions if previous.action_type in AGGRESSIVE_ACTIONS]
    pot = max(action.pot_before, 0.0)
    sizing = action.bet_fraction_pot or (action.amount / pot if pot > 0 else 0.0)

    return ActionContext(
        street=action.street,
        raise_level=raise_level,
        facing_bet=facing_bet,
        bet_fraction_pot=sizing,
        pot_odds=facing_amount / (pot + facing_amount) if facing_amount > 0 else 0.0,
        opponent_is_preflop_aggressor=opponent_is_preflop_aggressor,
        hero_aggressive_actions=len(hero_aggressive),
        hero_three_bet=any(
            previous.action_type in {ActionType.THREE_BET, ActionType.FOUR_BET} for previous in hero_actions
        ),
        hero_last_action=hero_actions[-1].action_type if hero_actions else None,
    )


PROFILE_COUNTERS: tuple[str, ...] = (
    "preflop_hands",
    "vpip_count",
    "pfr_count",
    "three_bet_opportunities",
    "three_bet_count",
    "three_bets_faced",
    "three_bet_folds",
    "cbet_opportunities",
    "cbet_count",
    "aggressive_actions",
    "passive_actions",
    "river_aggressive_actions",
    "river_actions",
    "showdowns_seen",
    "showdown_opportunities",
    "showdown_aggressive_hands",
    "showdown_bluffs",
)


@dataclass
class PlayerProfile:
    """Observed tendencies.

    The rate fields (`vpip`, `pfr`, ...) are *derived* from the counters below by
    `backend.profile_stats.derive_rates`, using Beta-Binomial shrinkage toward
    population priors. They are stored so the whole profile round-trips through the
    API and the database unchanged, but nothing should write them directly.
    """

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
    preflop_hands: int = 0
    vpip_count: int = 0
    pfr_count: int = 0
    three_bet_opportunities: int = 0
    three_bet_count: int = 0
    three_bets_faced: int = 0
    three_bet_folds: int = 0
    cbet_opportunities: int = 0
    cbet_count: int = 0
    aggressive_actions: int = 0
    passive_actions: int = 0
    river_aggressive_actions: int = 0
    river_actions: int = 0
    showdowns_seen: int = 0
    showdown_opportunities: int = 0
    showdown_aggressive_hands: int = 0
    showdown_bluffs: int = 0

    def as_dict(self) -> dict[str, float | int | str]:
        payload: dict[str, float | int | str] = {
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
        for counter in PROFILE_COUNTERS:
            payload[counter] = getattr(self, counter)
        return payload

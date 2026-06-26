from __future__ import annotations

from dataclasses import replace

from engine.state import ActionType, PlayerProfile, PokerAction, Street


def blend(old: float, observed: float, samples: int, learning_rate: float = 0.08) -> float:
    sample_weight = min(0.35, learning_rate + samples * 0.002)
    return old * (1.0 - sample_weight) + observed * sample_weight


def update_profile_from_action(profile: PlayerProfile, action: PokerAction) -> PlayerProfile:
    samples = profile.hands_observed
    voluntary = 1.0 if action.action_type in {ActionType.CALL, ActionType.BET, ActionType.RAISE, ActionType.THREE_BET, ActionType.FOUR_BET, ActionType.JAM} else 0.0
    raised = 1.0 if action.action_type in {ActionType.RAISE, ActionType.THREE_BET, ActionType.FOUR_BET, ActionType.JAM} else 0.0
    three_bet = 1.0 if action.action_type == ActionType.THREE_BET else 0.0
    aggressive = 1.0 if action.action_type in {ActionType.BET, ActionType.RAISE, ActionType.THREE_BET, ActionType.FOUR_BET, ActionType.JAM} else 0.0
    passive = 1.0 if action.action_type in {ActionType.CALL, ActionType.CHECK} else 0.0
    river_aggressive = aggressive if action.street == Street.RIVER else profile.river_aggression / 3.0

    new_aggression = max(0.1, blend(profile.aggression / 3.0, aggressive / max(0.5, passive + 0.25), samples) * 3.0)
    new_river_aggression = max(0.1, blend(profile.river_aggression / 3.0, river_aggressive, samples) * 3.0)

    return replace(
        profile,
        vpip=blend(profile.vpip, voluntary, samples),
        pfr=blend(profile.pfr, raised if action.street == Street.PREFLOP else profile.pfr, samples),
        three_bet=blend(profile.three_bet, three_bet, samples),
        cbet=blend(profile.cbet, aggressive if action.street == Street.FLOP else profile.cbet, samples),
        aggression=new_aggression,
        river_aggression=new_river_aggression,
        bluff_frequency=blend(profile.bluff_frequency, 0.34 if aggressive and action.bet_fraction_pot >= 0.75 else 0.12, samples),
        hands_observed=samples + 1,
    )

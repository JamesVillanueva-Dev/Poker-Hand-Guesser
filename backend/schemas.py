from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from engine.state import ActionActor, ActionType, Street


class BoardStatePayload(BaseModel):
    street: Street = Street.PREFLOP
    board_cards: list[str] = Field(default_factory=list)
    hero_cards: list[str] = Field(default_factory=list)
    pot: float = 0.0
    effective_stack: float = 0.0
    position: str = "BTN"


class StartHandRequest(BaseModel):
    hand_id: str
    player_id: str
    board_state: BoardStatePayload = Field(default_factory=BoardStatePayload)
    session_profile: dict[str, Any] | None = None


class ActionRequest(BaseModel):
    hand_id: str
    player_id: str
    actor: ActionActor = ActionActor.OPPONENT
    action_type: ActionType
    street: Street
    position: str
    amount: float = 0.0
    pot_before: float = 0.0
    bet_fraction_pot: float = 0.0
    board_cards: list[str] = Field(default_factory=list)
    hero_cards: list[str] = Field(default_factory=list)
    effective_stack: float = 0.0


class ShowdownRequest(BaseModel):
    hand_id: str
    player_id: str
    hole_cards: list[str]
    won: bool = False


class ImportHandRequest(BaseModel):
    site: str
    raw_text: str


class RangeResponse(BaseModel):
    hand_id: str
    player_id: str
    distribution: dict[str, float]
    top_hands: list[dict[str, float | str]]
    matrix: list[dict[str, Any]]
    entropy: float
    timeline: list[dict[str, Any]]
    board_state: dict[str, Any]
    profile: dict[str, Any]
    recommendation: dict[str, Any]
    adaptation_notes: list[str]
    hand_complete: bool = False
    profile_samples: dict[str, int] = Field(default_factory=dict)
    calibration: dict[str, Any] = Field(default_factory=dict)
    legal_actions_by_street: dict[str, list[str]] = Field(default_factory=dict)


class PlayerResponse(BaseModel):
    player_id: str
    vpip: float
    pfr: float
    three_bet: float
    fold_to_three_bet: float
    cbet: float
    aggression: float
    river_aggression: float
    bluff_frequency: float
    showdown_frequency: float
    hands_observed: int
    sample_sizes: dict[str, int] = Field(default_factory=dict)


class PredictionScoreResponse(BaseModel):
    street: str
    log_loss: float
    baseline_log_loss: float
    skill: float
    percentile: float
    top_10_hit: bool
    predicted_probability: float


class CalibrationResponse(BaseModel):
    baseline_log_loss: float
    overall: dict[str, Any]
    by_street: dict[str, Any]
    recent: dict[str, Any]
    recent_window: int
    summary: str
    beats_guessing: bool

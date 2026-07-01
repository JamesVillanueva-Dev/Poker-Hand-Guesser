from __future__ import annotations

from typing import Any

from fastapi import Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from backend.dependencies import get_range_estimator, get_repository
from backend.hand_import import parse_hand_history
from backend.profile_stats import update_profile_from_action
from backend.schemas import ActionRequest, ImportHandRequest, RangeResponse, ShowdownRequest, StartHandRequest
from database.repository import SQLiteRepository
from engine.range_engine import RangeEstimator, action_label
from engine.state import ActionActor, ActionType, BoardState, PlayerProfile, PokerAction, Street
from engine.strategy import recommend_move

app = FastAPI(title="Poker Range Estimator", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_origin_regex=r"https?://(localhost|127\.0\.0\.1):\d+",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/hand/start", response_model=RangeResponse)
def start_hand(
    request: StartHandRequest,
    repository: SQLiteRepository = Depends(get_repository),
    estimator: RangeEstimator = Depends(get_range_estimator),
) -> dict[str, Any]:
    profile = PlayerProfile(**request.session_profile) if request.session_profile else PlayerProfile(player_id=request.player_id)
    profile.player_id = request.player_id
    distribution = estimator.initial_distribution()
    board_state = request.board_state.model_dump(mode="json")
    snapshots = [
        {
            "sequence": 0,
            "action_label": "Initial Range",
            "distribution": distribution,
            "entropy": estimator.summarize(distribution)["entropy"],
        }
    ]
    repository.save_session(request.hand_id, profile.player_id, distribution, snapshots, board_state, profile)
    return _range_response(request.hand_id, profile.player_id, distribution, snapshots, board_state, profile, estimator)


@app.post("/action", response_model=RangeResponse)
def observe_action(
    request: ActionRequest,
    repository: SQLiteRepository = Depends(get_repository),
    estimator: RangeEstimator = Depends(get_range_estimator),
) -> dict[str, Any]:
    session = repository.get_session(request.hand_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Hand session not found. Call /hand/start first.")

    profile = session["session_profile"]
    sequence = len(session["snapshots"])
    action = PokerAction(
        player_id=request.player_id,
        action_type=request.action_type,
        street=request.street,
        position=request.position,
        actor=request.actor,
        amount=request.amount,
        pot_before=request.pot_before,
        bet_fraction_pot=request.bet_fraction_pot,
        sequence=sequence,
    )
    board_cards = request.board_cards or session["board_state"].get("board_cards", [])
    hero_cards = request.hero_cards or session["board_state"].get("hero_cards", [])
    board_state = BoardState(
        street=request.street,
        board_cards=board_cards,
        hero_cards=hero_cards,
        pot=max(request.pot_before, session["board_state"].get("pot", 0.0)) + request.amount,
        effective_stack=request.effective_stack,
        position=request.position,
    )
    if request.actor == ActionActor.OPPONENT:
        distribution = estimator.update_range(session["current_distribution"], action, board_state, profile)
        updated_profile = update_profile_from_action(profile, action)
    else:
        distribution = session["current_distribution"]
        updated_profile = profile
    summary = estimator.summarize(distribution)
    explanation = _explain_observed_action(action, profile, updated_profile, request.actor == ActionActor.OPPONENT)
    snapshots = [
        *session["snapshots"],
        {
            "sequence": sequence,
            "action_label": action_label(action),
            "action": {
                "player_id": action.player_id,
                "actor": action.actor.value,
                "action_type": action.action_type.value,
                "street": action.street.value,
                "position": action.position,
                "amount": action.amount,
                "pot_before": action.pot_before,
                "bet_fraction_pot": action.bet_fraction_pot,
            },
            "distribution": distribution,
            "entropy": summary["entropy"],
            "explanation": explanation,
        },
    ]
    board_payload = {
        "street": request.street.value,
        "board_cards": board_cards,
        "hero_cards": hero_cards,
        "pot": board_state.pot,
        "effective_stack": request.effective_stack,
        "position": request.position,
    }
    repository.save_session(request.hand_id, request.player_id, distribution, snapshots, board_payload, updated_profile)
    return _range_response(request.hand_id, request.player_id, distribution, snapshots, board_payload, updated_profile, estimator)


@app.post("/showdown")
def showdown(
    request: ShowdownRequest,
    repository: SQLiteRepository = Depends(get_repository),
) -> dict[str, Any]:
    session = repository.get_session(request.hand_id)
    profile = session["session_profile"] if session else PlayerProfile(player_id=request.player_id)
    profile.showdown_frequency = min(1.0, profile.showdown_frequency * 0.94 + 0.06)
    profile.hands_observed += 1
    if session:
        repository.save_session(
            request.hand_id,
            request.player_id,
            session["current_distribution"],
            session["snapshots"],
            session["board_state"],
            profile,
        )
    return {"status": "recorded", "hole_cards": request.hole_cards, "won": request.won}


@app.get("/range/{hand_id}", response_model=RangeResponse)
def get_range(
    hand_id: str,
    repository: SQLiteRepository = Depends(get_repository),
    estimator: RangeEstimator = Depends(get_range_estimator),
) -> dict[str, Any]:
    session = repository.get_session(hand_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Hand session not found.")
    return _range_response(
        hand_id,
        session["player_id"],
        session["current_distribution"],
        session["snapshots"],
        session["board_state"],
        session["session_profile"],
        estimator,
    )


@app.get("/range", response_model=RangeResponse)
def get_range_by_query(
    hand_id: str,
    repository: SQLiteRepository = Depends(get_repository),
    estimator: RangeEstimator = Depends(get_range_estimator),
) -> dict[str, Any]:
    return get_range(hand_id, repository, estimator)


@app.get("/player/{player_id}")
def get_player(player_id: str, repository: SQLiteRepository = Depends(get_repository)) -> dict[str, Any]:
    return repository.get_player(player_id).as_dict()


@app.get("/history")
def get_history(repository: SQLiteRepository = Depends(get_repository)) -> list[dict[str, Any]]:
    return repository.list_history()


@app.post("/import")
def import_hand(request: ImportHandRequest, repository: SQLiteRepository = Depends(get_repository)) -> dict[str, Any]:
    parsed = parse_hand_history(request.raw_text, request.site)
    for index, parsed_action in enumerate(parsed["actions"]):
        player_id = parsed_action["player_id"]
        profile = repository.get_player(player_id)
        action = PokerAction(
            player_id=player_id,
            action_type=ActionType(parsed_action["action_type"]),
            street=Street(parsed_action["street"]),
            position="unknown",
            amount=parsed_action["amount"],
            sequence=index,
        )
        repository.save_player(update_profile_from_action(profile, action))
    import_id = repository.import_hand(parsed["site"], request.raw_text, parsed)
    return {"id": import_id, "parsed": parsed}


@app.get("/range/{hand_id}/snapshot/{sequence}", response_model=RangeResponse)
def rewind_range(
    hand_id: str,
    sequence: int,
    repository: SQLiteRepository = Depends(get_repository),
    estimator: RangeEstimator = Depends(get_range_estimator),
) -> dict[str, Any]:
    session = repository.get_session(hand_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Hand session not found.")
    snapshots = session["snapshots"]
    if sequence < 0 or sequence >= len(snapshots):
        raise HTTPException(status_code=404, detail="Snapshot not found.")
    snapshot = snapshots[sequence]
    return _range_response(hand_id, session["player_id"], snapshot["distribution"], snapshots[: sequence + 1], session["board_state"], session["session_profile"], estimator)


def _range_response(
    hand_id: str,
    player_id: str,
    distribution: dict[str, float],
    snapshots: list[dict[str, Any]],
    board_state: dict[str, Any],
    profile: PlayerProfile,
    estimator: RangeEstimator,
) -> dict[str, Any]:
    summary = estimator.summarize(distribution)
    latest_action = _latest_opponent_action(snapshots)
    recommendation = recommend_move(
        distribution,
        BoardState(
            street=Street(board_state.get("street", Street.PREFLOP.value)),
            board_cards=board_state.get("board_cards", []),
            hero_cards=board_state.get("hero_cards", []),
            pot=float(board_state.get("pot", 0.0)),
            effective_stack=float(board_state.get("effective_stack", 0.0)),
            position=board_state.get("position", "BTN"),
        ),
        profile,
        latest_action,
    )
    return {
        "hand_id": hand_id,
        "player_id": player_id,
        "distribution": summary["distribution"],
        "top_hands": summary["top_hands"],
        "matrix": summary["matrix"],
        "entropy": summary["entropy"],
        "timeline": snapshots,
        "board_state": board_state,
        "profile": profile.as_dict(),
        "recommendation": recommendation.as_dict(),
        "adaptation_notes": _adaptation_notes(profile, snapshots),
    }


def _latest_opponent_action(snapshots: list[dict[str, Any]]) -> PokerAction | None:
    for snapshot in reversed(snapshots):
        payload = snapshot.get("action")
        if not payload or payload.get("actor", "opponent") != ActionActor.OPPONENT.value:
            continue
        return PokerAction(
            player_id=payload.get("player_id", "villain"),
            actor=ActionActor.OPPONENT,
            action_type=ActionType(payload["action_type"]),
            street=Street(payload["street"]),
            position=payload.get("position", "IP"),
            amount=float(payload.get("amount", 0.0)),
            pot_before=float(payload.get("pot_before", 0.0)),
            bet_fraction_pot=float(payload.get("bet_fraction_pot", 0.0)),
            sequence=int(snapshot.get("sequence", 0)),
        )
    return None


def _explain_observed_action(action: PokerAction, before: PlayerProfile, after: PlayerProfile, updates_range: bool) -> str:
    actor = "opponent" if action.actor == ActionActor.OPPONENT else "hero"
    if not updates_range:
        return "Hero action recorded as context. Opponent range is unchanged until the opponent responds."

    sizing = action.bet_fraction_pot or (action.amount / action.pot_before if action.pot_before else 0.0)
    if action.action_type in {ActionType.BET, ActionType.RAISE, ActionType.THREE_BET, ActionType.FOUR_BET, ActionType.JAM}:
        tendency = "aggressive"
        if sizing >= 0.75:
            tendency = "large aggressive"
        return (
            f"Observed {actor} {tendency} action. Session aggression moved from {before.aggression:.2f} to {after.aggression:.2f}, "
            f"and bluff tendency is now {after.bluff_frequency * 100:.1f}%."
        )
    if action.action_type == ActionType.CALL:
        return f"Observed opponent call. The model keeps more medium-strength holdings and updates VPIP to {after.vpip * 100:.1f}%."
    if action.action_type == ActionType.CHECK:
        return f"Observed opponent check. Passive control lines get more weight; aggression is now {after.aggression:.2f}."
    return f"Observed opponent fold. Strong hand classes lose weight for this line; VPIP is now {after.vpip * 100:.1f}%."


def _adaptation_notes(profile: PlayerProfile, snapshots: list[dict[str, Any]]) -> list[str]:
    opponent_actions = [
        snapshot.get("action", {})
        for snapshot in snapshots
        if snapshot.get("action", {}).get("actor", "opponent") == ActionActor.OPPONENT.value
    ]
    aggressive = [
        action
        for action in opponent_actions
        if action.get("action_type") in {ActionType.BET.value, ActionType.RAISE.value, ActionType.THREE_BET.value, ActionType.FOUR_BET.value, ActionType.JAM.value}
    ]
    calls = [action for action in opponent_actions if action.get("action_type") == ActionType.CALL.value]
    notes = [
        f"Session-only model: {profile.hands_observed} opponent actions observed; no opponent data is saved across fresh sessions.",
        f"Current profile: VPIP {profile.vpip * 100:.1f}%, PFR {profile.pfr * 100:.1f}%, aggression {profile.aggression:.2f}, bluff estimate {profile.bluff_frequency * 100:.1f}%.",
    ]
    if opponent_actions:
        notes.append(f"Pattern read: {len(aggressive)} aggressive actions and {len(calls)} calls/check-call style continues in this hand history.")
    else:
        notes.append("Pattern read: waiting for opponent actions before adapting the range.")
    return notes

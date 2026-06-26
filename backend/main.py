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
from engine.state import ActionType, BoardState, PokerAction, Street

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
    profile = repository.get_player(request.player_id)
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
    repository.save_session(request.hand_id, profile.player_id, distribution, snapshots, board_state)
    return _range_response(request.hand_id, profile.player_id, distribution, snapshots, board_state, estimator)


@app.post("/action", response_model=RangeResponse)
def observe_action(
    request: ActionRequest,
    repository: SQLiteRepository = Depends(get_repository),
    estimator: RangeEstimator = Depends(get_range_estimator),
) -> dict[str, Any]:
    session = repository.get_session(request.hand_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Hand session not found. Call /hand/start first.")

    profile = repository.get_player(request.player_id)
    sequence = len(session["snapshots"])
    action = PokerAction(
        player_id=request.player_id,
        action_type=request.action_type,
        street=request.street,
        position=request.position,
        amount=request.amount,
        pot_before=request.pot_before,
        bet_fraction_pot=request.bet_fraction_pot,
        sequence=sequence,
    )
    board_state = BoardState(
        street=request.street,
        board_cards=request.board_cards,
        pot=max(request.pot_before, session["board_state"].get("pot", 0.0)) + request.amount,
        effective_stack=request.effective_stack,
        position=request.position,
    )
    distribution = estimator.update_range(session["current_distribution"], action, board_state, profile)
    summary = estimator.summarize(distribution)
    snapshots = [
        *session["snapshots"],
        {
            "sequence": sequence,
            "action_label": action_label(action),
            "action": {
                "player_id": action.player_id,
                "action_type": action.action_type.value,
                "street": action.street.value,
                "position": action.position,
                "amount": action.amount,
                "pot_before": action.pot_before,
                "bet_fraction_pot": action.bet_fraction_pot,
            },
            "distribution": distribution,
            "entropy": summary["entropy"],
        },
    ]
    board_payload = {
        "street": request.street.value,
        "board_cards": request.board_cards,
        "pot": board_state.pot,
        "effective_stack": request.effective_stack,
        "position": request.position,
    }
    repository.save_player(update_profile_from_action(profile, action))
    repository.save_session(request.hand_id, request.player_id, distribution, snapshots, board_payload)
    return _range_response(request.hand_id, request.player_id, distribution, snapshots, board_payload, estimator)


@app.post("/showdown")
def showdown(
    request: ShowdownRequest,
    repository: SQLiteRepository = Depends(get_repository),
) -> dict[str, Any]:
    profile = repository.get_player(request.player_id)
    profile.showdown_frequency = min(1.0, profile.showdown_frequency * 0.94 + 0.06)
    profile.hands_observed += 1
    repository.save_player(profile)
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
    return _range_response(hand_id, session["player_id"], snapshot["distribution"], snapshots[: sequence + 1], session["board_state"], estimator)


def _range_response(
    hand_id: str,
    player_id: str,
    distribution: dict[str, float],
    snapshots: list[dict[str, Any]],
    board_state: dict[str, Any],
    estimator: RangeEstimator,
) -> dict[str, Any]:
    summary = estimator.summarize(distribution)
    return {
        "hand_id": hand_id,
        "player_id": player_id,
        "distribution": summary["distribution"],
        "top_hands": summary["top_hands"],
        "matrix": summary["matrix"],
        "entropy": summary["entropy"],
        "timeline": snapshots,
        "board_state": board_state,
    }

from __future__ import annotations

from typing import Any

from fastapi import Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from backend.dependencies import get_range_estimator, get_repository
from backend.hand_import import parse_hand_history
from backend.profile_stats import build_observation, observe_action, observe_showdown, sample_sizes, start_hand
from backend.schemas import ActionRequest, ImportHandRequest, RangeResponse, ShowdownRequest, StartHandRequest
from database.repository import SQLiteRepository
from engine.evaluator import hand_class_of, holding_strength
from engine.likelihood import legal_actions
from engine.range_engine import RangeEstimator, action_label
from engine.scoring import BASELINE_LOG_LOSS, plain_language, score_prediction, summarize_scores
from engine.state import (
    AGGRESSIVE_ACTIONS,
    ActionActor,
    ActionType,
    BoardState,
    PlayerProfile,
    PokerAction,
    Street,
    build_action_context,
)
from engine.strategy import recommend_move
from training.collect import append_examples, build_examples

RECENT_WINDOW = 20

app = FastAPI(title="Poker Range Estimator", version="0.2.0")

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
def start_hand_endpoint(
    request: StartHandRequest,
    repository: SQLiteRepository = Depends(get_repository),
    estimator: RangeEstimator = Depends(get_range_estimator),
) -> dict[str, Any]:
    profile = (
        PlayerProfile(**request.session_profile) if request.session_profile else PlayerProfile(player_id=request.player_id)
    )
    profile.player_id = request.player_id
    profile = start_hand(profile)

    board_state = request.board_state.model_dump(mode="json")
    board_state["hand_complete"] = False
    dead = [*board_state.get("board_cards", []), *board_state.get("hero_cards", [])]
    distribution = estimator.initial_distribution(dead)
    snapshots = [
        {
            "sequence": 0,
            "action_label": "Initial Range",
            "distribution": distribution,
            "entropy": estimator.summarize(distribution, dead)["entropy"],
            "board_cards": board_state.get("board_cards", []),
            "hero_cards": board_state.get("hero_cards", []),
            "street": board_state.get("street", Street.PREFLOP.value),
        }
    ]
    repository.save_session(request.hand_id, profile.player_id, distribution, snapshots, board_state, profile)
    return _range_response(
        request.hand_id, profile.player_id, distribution, snapshots, board_state, profile, estimator, repository
    )


@app.post("/action", response_model=RangeResponse)
def observe_action_endpoint(
    request: ActionRequest,
    repository: SQLiteRepository = Depends(get_repository),
    estimator: RangeEstimator = Depends(get_range_estimator),
) -> dict[str, Any]:
    session = repository.get_session(request.hand_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Hand session not found. Call /hand/start first.")
    if session["board_state"].get("hand_complete"):
        raise HTTPException(
            status_code=409,
            detail="This hand is already complete. Start a new hand to keep modelling.",
        )

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
    previous_actions = _actions_from_snapshots(session["snapshots"])
    board_state = BoardState(
        street=request.street,
        board_cards=board_cards,
        hero_cards=hero_cards,
        pot=max(request.pot_before, session["board_state"].get("pot", 0.0)) + request.amount,
        effective_stack=request.effective_stack,
        position=request.position,
        previous_actions=previous_actions,
    )
    previous_dead = [
        *session["board_state"].get("board_cards", []),
        *session["board_state"].get("hero_cards", []),
    ]

    if request.actor == ActionActor.OPPONENT:
        distribution = estimator.update_range(
            session["current_distribution"], action, board_state, profile, previous_dead
        )
        updated_profile = observe_action(profile, build_observation(action, previous_actions))
    else:
        # Hero actions do not move the range by themselves, but they are now part of the
        # context every later opponent action is read against.
        distribution = session["current_distribution"]
        updated_profile = profile

    hand_complete = request.actor == ActionActor.OPPONENT and request.action_type == ActionType.FOLD
    dead = [*board_cards, *hero_cards]
    summary = estimator.summarize(distribution, dead)
    explanation = _explain_observed_action(
        action, profile, updated_profile, request.actor == ActionActor.OPPONENT, hand_complete
    )
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
            "board_cards": board_cards,
            "hero_cards": hero_cards,
            "street": action.street.value,
            "terminal": hand_complete,
        },
    ]
    board_payload = {
        "street": request.street.value,
        "board_cards": board_cards,
        "hero_cards": hero_cards,
        "pot": board_state.pot,
        "effective_stack": request.effective_stack,
        "position": request.position,
        "hand_complete": hand_complete,
    }
    repository.save_session(request.hand_id, request.player_id, distribution, snapshots, board_payload, updated_profile)
    return _range_response(
        request.hand_id,
        request.player_id,
        distribution,
        snapshots,
        board_payload,
        updated_profile,
        estimator,
        repository,
    )


@app.post("/showdown")
def showdown(
    request: ShowdownRequest,
    repository: SQLiteRepository = Depends(get_repository),
) -> dict[str, Any]:
    """Grade the prediction against the hand the opponent actually held."""
    session = repository.get_session(request.hand_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Hand session not found. Nothing to score.")

    true_class = hand_class_of(*request.hole_cards[:2]) if len(request.hole_cards) >= 2 else ""
    if not true_class:
        raise HTTPException(status_code=422, detail="Showdown needs two valid hole cards, for example ['Ah', 'Kd'].")

    profile: PlayerProfile = session["session_profile"]
    snapshots: list[dict[str, Any]] = session["snapshots"]
    board_state: dict[str, Any] = session["board_state"]
    board_cards = board_state.get("board_cards", [])
    hero_cards = board_state.get("hero_cards", [])

    scores: list[dict[str, Any]] = []
    dataset_rows: list[dict[str, Any]] = []
    for street, snapshot in _distribution_per_street(snapshots).items():
        score = score_prediction(snapshot["distribution"], true_class)
        repository.save_prediction(
            request.hand_id, request.player_id, street, snapshot["distribution"], true_class, score.as_dict()
        )
        scores.append({"street": street, **score.as_dict()})
        dataset_rows.extend(
            build_examples(
                hand_id=request.hand_id,
                true_class=true_class,
                distribution=snapshot["distribution"],
                board_cards=snapshot.get("board_cards", board_cards),
                hero_cards=snapshot.get("hero_cards", hero_cards),
                street=street,
                profile=profile,
                bet_fraction_pot=snapshot.get("bet_fraction_pot", 0.0),
            )
        )
    rows_written = append_examples(dataset_rows)

    showdown_percentile = None
    if len(board_cards) >= 3:
        showdown_percentile, _ = holding_strength(request.hole_cards[:2], board_cards)
    aggressive_values = {action.value for action in AGGRESSIVE_ACTIONS}
    was_aggressive = any(
        snapshot.get("action", {}).get("actor") == ActionActor.OPPONENT.value
        and snapshot.get("action", {}).get("action_type") in aggressive_values
        for snapshot in snapshots
    )
    profile = observe_showdown(profile, was_aggressive, showdown_percentile)

    board_state = {**board_state, "hand_complete": True}
    repository.save_session(
        request.hand_id, request.player_id, session["current_distribution"], snapshots, board_state, profile
    )

    return {
        "status": "scored",
        "hole_cards": request.hole_cards,
        "won": request.won,
        "true_class": true_class,
        "scores": scores,
        "final_score": scores[-1] if scores else None,
        "training_rows_written": rows_written,
        "profile": profile.as_dict(),
        "calibration": _calibration_payload(repository, request.player_id),
    }


@app.get("/calibration")
def calibration(
    player_id: str | None = None,
    repository: SQLiteRepository = Depends(get_repository),
) -> dict[str, Any]:
    """Running measured skill. The number that says whether any of this works."""
    return _calibration_payload(repository, player_id)


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
        repository,
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
    profile = repository.get_player(player_id)
    return {**profile.as_dict(), "sample_sizes": sample_sizes(profile)}


@app.get("/history")
def get_history(repository: SQLiteRepository = Depends(get_repository)) -> list[dict[str, Any]]:
    return repository.list_history()


@app.post("/import")
def import_hand(request: ImportHandRequest, repository: SQLiteRepository = Depends(get_repository)) -> dict[str, Any]:
    parsed = parse_hand_history(request.raw_text, request.site)
    history: dict[str, list[PokerAction]] = {}
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
        prior_actions = history.setdefault(player_id, [])
        repository.save_player(observe_action(profile, build_observation(action, prior_actions)))
        prior_actions.append(action)
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
    return _range_response(
        hand_id,
        session["player_id"],
        snapshot["distribution"],
        snapshots[: sequence + 1],
        session["board_state"],
        session["session_profile"],
        estimator,
        repository,
    )


# --------------------------------------------------------------------------------------------
# helpers
# --------------------------------------------------------------------------------------------


def _range_response(
    hand_id: str,
    player_id: str,
    distribution: dict[str, float],
    snapshots: list[dict[str, Any]],
    board_state: dict[str, Any],
    profile: PlayerProfile,
    estimator: RangeEstimator,
    repository: SQLiteRepository,
) -> dict[str, Any]:
    dead = [*board_state.get("board_cards", []), *board_state.get("hero_cards", [])]
    summary = estimator.summarize(distribution, dead)
    latest_action = _latest_opponent_action(snapshots)
    street = Street(board_state.get("street", Street.PREFLOP.value))
    calibration_payload = _calibration_payload(repository, player_id)
    street_summary = calibration_payload["by_street"].get(street.value, {})
    scored = int(street_summary.get("count", 0))
    measured_skill = float(street_summary["mean_skill"]) if scored else None

    recommendation = recommend_move(
        distribution,
        BoardState(
            street=street,
            board_cards=board_state.get("board_cards", []),
            hero_cards=board_state.get("hero_cards", []),
            pot=float(board_state.get("pot", 0.0)),
            effective_stack=float(board_state.get("effective_stack", 0.0)),
            position=board_state.get("position", "BTN"),
            previous_actions=_actions_from_snapshots(snapshots),
        ),
        profile,
        latest_action,
        measured_skill=measured_skill,
        scored_showdowns=scored,
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
        "adaptation_notes": _adaptation_notes(profile, snapshots, board_state, calibration_payload),
        "hand_complete": bool(board_state.get("hand_complete", False)),
        "profile_samples": sample_sizes(profile),
        "calibration": calibration_payload,
        "legal_actions_by_street": _legal_actions_by_street(board_state, snapshots),
    }


def _legal_actions_by_street(
    board_state: dict[str, Any], snapshots: list[dict[str, Any]]
) -> dict[str, list[str]]:
    """What the opponent could legally do next on each street, from the policy's own source.

    Keyed by street because the user can move to the flop before anything has been logged
    there, and the controls must follow them. An empty list means nothing is pending on
    that street: either the hand is over or the betting has already closed.
    """
    if board_state.get("hand_complete"):
        return {street.value: [] for street in Street}

    history = _actions_from_snapshots(snapshots)
    next_sequence = max((action.sequence for action in history), default=-1) + 1
    by_street: dict[str, list[str]] = {}

    for street in Street:
        if _street_is_closed([action for action in history if action.street == street]):
            # Offering a stale action set here would be worse than saying nothing: the UI
            # reads this list literally.
            by_street[street.value] = []
            continue
        probe = PokerAction(
            player_id="villain",
            action_type=ActionType.CHECK,
            street=street,
            position=board_state.get("position", "BTN"),
            actor=ActionActor.OPPONENT,
            pot_before=float(board_state.get("pot", 0.0)),
            sequence=next_sequence,
        )
        context = build_action_context(
            BoardState(
                street=street,
                board_cards=board_state.get("board_cards", []),
                hero_cards=board_state.get("hero_cards", []),
                pot=float(board_state.get("pot", 0.0)),
                position=probe.position,
                previous_actions=history,
            ),
            probe,
        )
        by_street[street.value] = [action.value for action in legal_actions(context)]
    return by_street


def _street_is_closed(street_history: list[PokerAction]) -> bool:
    """Heads-up: a call closes the betting, and so does a check behind a check."""
    if not street_history:
        return False
    last = street_history[-1]
    if last.action_type == ActionType.CALL:
        return True
    if len(street_history) >= 2:
        previous = street_history[-2]
        both_checked = last.action_type == ActionType.CHECK and previous.action_type == ActionType.CHECK
        if both_checked and last.actor != previous.actor:
            return True
    return False


def _calibration_payload(repository: SQLiteRepository, player_id: str | None = None) -> dict[str, Any]:
    rows = repository.list_predictions(player_id=player_id)
    overall = summarize_scores(rows)
    by_street = {
        street: summarize_scores([row for row in rows if row["street"] == street])
        for street in (Street.PREFLOP.value, Street.FLOP.value, Street.TURN.value, Street.RIVER.value)
    }
    return {
        "baseline_log_loss": BASELINE_LOG_LOSS,
        "overall": overall,
        "by_street": {street: summary for street, summary in by_street.items() if summary["count"]},
        "recent": summarize_scores(rows[:RECENT_WINDOW]),
        "recent_window": RECENT_WINDOW,
        "summary": plain_language(overall),
        "beats_guessing": bool(overall["count"]) and float(overall["mean_skill"]) > 0.0,
    }


def _actions_from_snapshots(snapshots: list[dict[str, Any]]) -> list[PokerAction]:
    actions: list[PokerAction] = []
    for snapshot in snapshots:
        payload = snapshot.get("action")
        if not payload:
            continue
        actions.append(
            PokerAction(
                player_id=payload.get("player_id", "villain"),
                actor=ActionActor(payload.get("actor", ActionActor.OPPONENT.value)),
                action_type=ActionType(payload["action_type"]),
                street=Street(payload["street"]),
                position=payload.get("position", "IP"),
                amount=float(payload.get("amount", 0.0)),
                pot_before=float(payload.get("pot_before", 0.0)),
                bet_fraction_pot=float(payload.get("bet_fraction_pot", 0.0)),
                sequence=int(snapshot.get("sequence", 0)),
            )
        )
    return actions


def _distribution_per_street(snapshots: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    """The range as of the end of each street, so scoring shows *where* the model fails."""
    per_street: dict[str, dict[str, Any]] = {}
    for snapshot in snapshots:
        payload = snapshot.get("action")
        if not payload or payload.get("actor") != ActionActor.OPPONENT.value:
            continue
        per_street[payload["street"]] = {
            "distribution": snapshot["distribution"],
            "board_cards": snapshot.get("board_cards", []),
            "hero_cards": snapshot.get("hero_cards", []),
            "bet_fraction_pot": float(payload.get("bet_fraction_pot", 0.0)),
        }
    return per_street


def _latest_opponent_action(snapshots: list[dict[str, Any]]) -> PokerAction | None:
    for action in reversed(_actions_from_snapshots(snapshots)):
        if action.actor == ActionActor.OPPONENT:
            return action
    return None


def _explain_observed_action(
    action: PokerAction,
    before: PlayerProfile,
    after: PlayerProfile,
    updates_range: bool,
    hand_complete: bool,
) -> str:
    if not updates_range:
        return (
            "Hero action recorded. It does not move the range on its own, but every later opponent "
            "action is now read against it."
        )
    if hand_complete:
        return (
            "Opponent folded, so the hand is over. This is the terminal read: it is the range they "
            "gave up with, and it is frozen here."
        )

    sizing = action.bet_fraction_pot or (action.amount / action.pot_before if action.pot_before else 0.0)
    if action.action_type in AGGRESSIVE_ACTIONS:
        tendency = "large aggressive" if sizing >= 0.75 else "aggressive"
        return (
            f"Observed {tendency} action. Aggression factor moved from {before.aggression:.2f} to "
            f"{after.aggression:.2f}; measured bluff rate is {after.bluff_frequency * 100:.1f}% over "
            f"{after.showdown_aggressive_hands} showdowns with aggression."
        )
    if action.action_type == ActionType.CALL:
        return (
            f"Observed a call. Bluff-catchers and draws keep weight; VPIP is now "
            f"{after.vpip * 100:.1f}% over {after.preflop_hands} preflop hands."
        )
    if action.action_type == ActionType.CHECK:
        return f"Observed a check. Passive lines gain weight; aggression factor is {after.aggression:.2f}."
    return "Observed a fold."


def _adaptation_notes(
    profile: PlayerProfile,
    snapshots: list[dict[str, Any]],
    board_state: dict[str, Any],
    calibration_payload: dict[str, Any],
) -> list[str]:
    notes = [
        calibration_payload["summary"],
        f"Profile from measured counts: VPIP {profile.vpip * 100:.1f}% ({profile.preflop_hands} preflop hands), "
        f"cbet {profile.cbet * 100:.1f}% ({profile.cbet_opportunities} opportunities), "
        f"bluff {profile.bluff_frequency * 100:.1f}% ({profile.showdown_aggressive_hands} aggressive showdowns).",
    ]
    if board_state.get("hand_complete"):
        notes.append("Hand complete. The range above is frozen; start a new hand to keep modelling.")
    opponent_actions = [
        snapshot.get("action", {})
        for snapshot in snapshots
        if snapshot.get("action", {}).get("actor") == ActionActor.OPPONENT.value
    ]
    if opponent_actions:
        aggressive_values = {action.value for action in AGGRESSIVE_ACTIONS}
        aggressive = [action for action in opponent_actions if action.get("action_type") in aggressive_values]
        notes.append(f"This hand: {len(opponent_actions)} opponent actions, {len(aggressive)} of them aggressive.")
    else:
        notes.append("Pattern read: waiting for opponent actions before adapting the range.")
    return notes

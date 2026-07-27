from __future__ import annotations

import json

from fastapi.testclient import TestClient

import training.collect as collect


def _start(client: TestClient, hand_id: str, **board: object) -> dict:
    response = client.post(
        "/hand/start",
        json={"hand_id": hand_id, "player_id": "villain", "board_state": board},
    )
    assert response.status_code == 200, response.text
    return response.json()


def _act(client: TestClient, hand_id: str, **payload: object) -> tuple[int, dict]:
    response = client.post("/action", json={"hand_id": hand_id, "player_id": "villain", **payload})
    return response.status_code, response.json()


def test_hand_start_and_action_flow(client: TestClient) -> None:
    payload = _start(client, "test-hand")
    assert abs(sum(payload["distribution"].values()) - 1.0) < 1e-9
    assert payload["profile"]["hands_observed"] == 1, "hands are counted at hand start, not per action"
    assert payload["recommendation"]["action"] in {"check", "bet", "call", "raise", "fold"}
    assert payload["hand_complete"] is False

    status, updated = _act(
        client,
        "test-hand",
        action_type="raise",
        street="preflop",
        position="UTG",
        amount=3,
        pot_before=1.5,
        bet_fraction_pot=2,
        hero_cards=["Ah", "Kd"],
    )
    assert status == 200
    assert len(updated["timeline"]) == 2
    assert abs(sum(updated["distribution"].values()) - 1.0) < 1e-9
    assert updated["profile"]["hands_observed"] == 1
    assert updated["profile"]["preflop_hands"] == 1
    assert updated["adaptation_notes"]
    assert updated["recommendation"]["reasons"]


def test_legal_actions_track_the_spot_on_every_street(client: TestClient) -> None:
    """The UI offers exactly these, so they must be real."""
    payload = _start(client, "legal-hand", pot=1.5, effective_stack=100)
    legal = payload["legal_actions_by_street"]
    assert set(legal) == {"preflop", "flop", "turn", "river"}
    assert set(legal["preflop"]) == {"fold", "check", "call", "raise", "jam"}
    # A street with nothing logged yet has no bet in front, so there is nothing to fold to.
    assert set(legal["flop"]) == {"check", "bet", "jam"}

    _act(
        client,
        "legal-hand",
        actor="hero",
        action_type="bet",
        street="flop",
        position="BB",
        amount=5,
        pot_before=7,
        board_cards=["Ks", "7d", "2c"],
    )
    facing = client.get("/range/legal-hand").json()["legal_actions_by_street"]["flop"]
    assert "check" not in facing, "you cannot check facing a bet"
    assert "fold" in facing

    unopened = _start(client, "unopened-hand", pot=1.5)["legal_actions_by_street"]["preflop"]
    assert "three_bet" not in unopened, "no three-bet without a raise in front"


def test_a_closed_street_offers_nothing(client: TestClient) -> None:
    """A call closes the betting. Offering a stale action set would be worse than saying so."""
    _start(client, "closed-hand", pot=1.5)
    _act(
        client,
        "closed-hand",
        action_type="raise",
        street="preflop",
        position="BTN",
        amount=3,
        pot_before=1.5,
        bet_fraction_pot=2.0,
    )
    open_spot = client.get("/range/closed-hand").json()
    assert open_spot["legal_actions_by_street"]["preflop"], "hero still has a decision here"

    _act(
        client,
        "closed-hand",
        actor="hero",
        action_type="call",
        street="preflop",
        position="BB",
        amount=3,
        pot_before=4.5,
    )
    closed = client.get("/range/closed-hand").json()["legal_actions_by_street"]
    assert closed["preflop"] == [], "preflop is over once the raise is called"
    assert closed["flop"], "but the flop is wide open"


def test_a_completed_hand_offers_no_further_actions(client: TestClient) -> None:
    _start(client, "done-hand")
    _, payload = _act(
        client, "done-hand", action_type="fold", street="preflop", position="BTN", amount=0, pot_before=1.5
    )
    assert payload["hand_complete"] is True
    assert all(actions == [] for actions in payload["legal_actions_by_street"].values())


def test_hero_action_is_context_only_but_still_recorded(client: TestClient) -> None:
    original = _start(client, "hero-context-hand")["distribution"]

    status, updated = _act(
        client,
        "hero-context-hand",
        actor="hero",
        action_type="bet",
        street="flop",
        position="IP",
        amount=4,
        pot_before=6,
        board_cards=["As", "7d", "2c"],
        hero_cards=["Ah", "Kd"],
        effective_stack=96,
    )
    assert status == 200
    assert updated["profile"]["preflop_hands"] == 0
    assert updated["timeline"][-1]["action"]["actor"] == "hero"
    assert original  # the pre-flop range existed before hero acted


def test_hero_actions_shift_the_read_on_a_later_opponent_action(client: TestClient) -> None:
    """Facing a hero three-bet changes what the opponent's call means."""

    def call_range(hand_id: str, hero_three_bets: bool) -> dict:
        _start(client, hand_id, pot=1.5, effective_stack=100)
        _act(
            client,
            hand_id,
            action_type="raise",
            street="preflop",
            position="BTN",
            amount=3,
            pot_before=1.5,
            bet_fraction_pot=2.0,
        )
        if hero_three_bets:
            _act(
                client,
                hand_id,
                actor="hero",
                action_type="three_bet",
                street="preflop",
                position="BB",
                amount=10,
                pot_before=4.5,
            )
        _act(
            client,
            hand_id,
            action_type="call",
            street="preflop",
            position="BTN",
            amount=7 if hero_three_bets else 0,
            pot_before=11.5 if hero_three_bets else 4.5,
        )
        return client.get(f"/range/{hand_id}").json()["distribution"]

    flat = call_range("no-3bet", hero_three_bets=False)
    squeezed = call_range("with-3bet", hero_three_bets=True)
    assert squeezed["72o"] < flat["72o"], "calling a three-bet should look stronger than calling a raise"


def test_hero_cards_are_removed_from_the_opponent_range(client: TestClient) -> None:
    payload = _start(client, "removal-hand", hero_cards=["Ah", "Ad"])
    assert payload["distribution"]["AA"] > 0
    assert payload["distribution"]["AA"] < payload["distribution"]["KK"] / 5
    cells = {cell["hand"]: cell for cell in payload["matrix"]}
    assert cells["AA"]["combo_count"] == 1
    assert cells["KK"]["combo_count"] == 6


def test_board_cards_zero_out_impossible_classes_permanently(client: TestClient) -> None:
    _start(client, "block-hand", hero_cards=["Ac", "Ks"])
    status, payload = _act(
        client,
        "block-hand",
        action_type="bet",
        street="flop",
        position="BTN",
        amount=5,
        pot_before=7,
        bet_fraction_pot=0.71,
        board_cards=["Ah", "Ad", "As"],
        hero_cards=["Ac", "Ks"],
    )
    assert status == 200
    assert payload["distribution"]["AA"] == 0.0

    status, later = _act(
        client,
        "block-hand",
        action_type="bet",
        street="turn",
        position="BTN",
        amount=12,
        pot_before=17,
        bet_fraction_pot=0.7,
        board_cards=["Ah", "Ad", "As", "7c"],
        hero_cards=["Ac", "Ks"],
    )
    assert status == 200
    assert later["distribution"]["AA"] == 0.0, "a blocked class must never come back"


def test_an_opponent_fold_ends_the_hand(client: TestClient) -> None:
    _start(client, "fold-hand")
    status, payload = _act(
        client, "fold-hand", action_type="fold", street="preflop", position="BTN", amount=0, pot_before=1.5
    )
    assert status == 200
    assert payload["hand_complete"] is True
    assert "terminal read" in payload["timeline"][-1]["explanation"]

    status, error = _act(
        client, "fold-hand", action_type="bet", street="flop", position="BTN", amount=5, pot_before=7
    )
    assert status == 409
    assert "complete" in error["detail"]


def test_showdown_scores_and_persists_the_prediction(client: TestClient) -> None:
    _start(client, "score-hand", hero_cards=["Ac", "Kc"], pot=1.5, effective_stack=100)
    _act(
        client,
        "score-hand",
        action_type="raise",
        street="preflop",
        position="BTN",
        amount=3,
        pot_before=1.5,
        bet_fraction_pot=2.0,
    )
    _act(
        client,
        "score-hand",
        action_type="bet",
        street="flop",
        position="BTN",
        amount=7,
        pot_before=7,
        bet_fraction_pot=1.0,
        board_cards=["Ks", "7d", "2c"],
        hero_cards=["Ac", "Kc"],
    )

    response = client.post(
        "/showdown",
        json={"hand_id": "score-hand", "player_id": "villain", "hole_cards": ["Kh", "Qd"], "won": True},
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["status"] == "scored"
    assert body["true_class"] == "KQo"
    streets = {score["street"] for score in body["scores"]}
    assert streets == {"preflop", "flop"}, "the range is scored as of every street, not just the last"
    for score in body["scores"]:
        assert score["baseline_log_loss"] > 7.4
        assert abs(score["skill"] - (score["baseline_log_loss"] - score["log_loss"])) < 1e-9

    calibration = client.get("/calibration").json()
    assert calibration["overall"]["count"] == 2
    assert set(calibration["by_street"]) == {"preflop", "flop"}
    assert "bits" in calibration["summary"]

    dataset = collect.DATASET_PATH
    assert dataset.exists(), "every scored showdown must emit training data"
    rows = [json.loads(line) for line in dataset.read_text(encoding="utf-8").splitlines() if line.strip()]
    assert rows
    assert len(rows[0]["features"]) == len(collect.FEATURE_NAMES)
    assert sum(row["label"] for row in rows) == len(streets), "one positive per scored street"
    assert {row["meta"]["hand_class"] for row in rows if row["label"] == 1.0} == {"KQo"}


def test_showdown_teaches_the_profile_what_a_bluff_is(client: TestClient) -> None:
    _start(client, "bluff-hand", pot=1.5, effective_stack=100)
    _act(
        client,
        "bluff-hand",
        action_type="bet",
        street="flop",
        position="BTN",
        amount=7,
        pot_before=7,
        bet_fraction_pot=1.0,
        board_cards=["Ks", "7d", "2c"],
    )
    before = client.get("/range/bluff-hand").json()["profile"]["bluff_frequency"]
    body = client.post(
        "/showdown",
        json={"hand_id": "bluff-hand", "player_id": "villain", "hole_cards": ["5h", "4d"], "won": False},
    ).json()
    assert body["profile"]["bluff_frequency"] > before
    assert body["profile"]["showdown_bluffs"] == 1


def test_showdown_needs_real_cards(client: TestClient) -> None:
    _start(client, "bad-showdown")
    response = client.post(
        "/showdown", json={"hand_id": "bad-showdown", "player_id": "villain", "hole_cards": ["ZZ", "Kd"]}
    )
    assert response.status_code == 422


def test_calibration_is_empty_and_honest_before_any_showdown(client: TestClient) -> None:
    payload = client.get("/calibration").json()
    assert payload["overall"]["count"] == 0
    assert payload["beats_guessing"] is False
    assert "No showdowns scored yet" in payload["summary"]


def test_recommendation_confidence_is_labeled_unvalidated_without_showdowns(client: TestClient) -> None:
    payload = _start(client, "confidence-hand", hero_cards=["Ah", "Kd"])
    assert "unvalidated" in payload["recommendation"]["confidence_basis"]


def test_rewind_returns_the_earlier_snapshot(client: TestClient) -> None:
    _start(client, "rewind-hand")
    _act(
        client,
        "rewind-hand",
        action_type="raise",
        street="preflop",
        position="BTN",
        amount=3,
        pot_before=1.5,
        bet_fraction_pot=2.0,
    )
    response = client.get("/range/rewind-hand/snapshot/0")
    assert response.status_code == 200
    assert len(response.json()["timeline"]) == 1


def test_player_endpoint_exposes_sample_sizes(client: TestClient) -> None:
    payload = client.get("/player/nobody").json()
    assert payload["sample_sizes"]["preflop_hands"] == 0
    assert payload["vpip"] == 0.24

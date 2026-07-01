from __future__ import annotations

from fastapi.testclient import TestClient

from backend.main import app


def test_hand_start_and_action_flow() -> None:
    client = TestClient(app)
    start = client.post("/hand/start", json={"hand_id": "test-hand", "player_id": "villain"})
    assert start.status_code == 200
    payload = start.json()
    assert abs(sum(payload["distribution"].values()) - 1.0) < 1e-9
    assert payload["profile"]["hands_observed"] == 0
    assert payload["recommendation"]["action"] in {"check", "bet", "call", "raise", "fold"}

    action = client.post(
        "/action",
        json={
            "hand_id": "test-hand",
            "player_id": "villain",
            "action_type": "raise",
            "street": "preflop",
            "position": "UTG",
            "amount": 3,
            "pot_before": 1.5,
            "bet_fraction_pot": 2,
            "hero_cards": ["Ah", "Kd"],
        },
    )
    assert action.status_code == 200
    updated = action.json()
    assert len(updated["timeline"]) == 2
    assert abs(sum(updated["distribution"].values()) - 1.0) < 1e-9
    assert updated["profile"]["hands_observed"] == 1
    assert updated["adaptation_notes"]
    assert updated["recommendation"]["reasons"]


def test_hero_action_is_context_only() -> None:
    client = TestClient(app)
    start = client.post("/hand/start", json={"hand_id": "hero-context-hand", "player_id": "villain"})
    assert start.status_code == 200
    original = start.json()["distribution"]

    action = client.post(
        "/action",
        json={
            "hand_id": "hero-context-hand",
            "player_id": "villain",
            "actor": "hero",
            "action_type": "bet",
            "street": "flop",
            "position": "IP",
            "amount": 4,
            "pot_before": 6,
            "board_cards": ["As", "7d", "2c"],
            "hero_cards": ["Ah", "Kd"],
            "effective_stack": 96,
        },
    )
    assert action.status_code == 200
    updated = action.json()
    assert updated["distribution"] == original
    assert updated["profile"]["hands_observed"] == 0
    assert updated["timeline"][-1]["action"]["actor"] == "hero"

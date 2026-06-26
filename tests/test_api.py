from __future__ import annotations

from fastapi.testclient import TestClient

from backend.main import app


def test_hand_start_and_action_flow() -> None:
    client = TestClient(app)
    start = client.post("/hand/start", json={"hand_id": "test-hand", "player_id": "villain"})
    assert start.status_code == 200
    payload = start.json()
    assert abs(sum(payload["distribution"].values()) - 1.0) < 1e-9

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
        },
    )
    assert action.status_code == 200
    updated = action.json()
    assert len(updated["timeline"]) == 2
    assert abs(sum(updated["distribution"].values()) - 1.0) < 1e-9

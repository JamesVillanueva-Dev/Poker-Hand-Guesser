from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any

from engine.state import PlayerProfile

DATABASE_PATH = Path(__file__).resolve().parent / "poker_range.sqlite3"


class SQLiteRepository:
    def __init__(self, path: Path = DATABASE_PATH) -> None:
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._initialize()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.path)
        connection.row_factory = sqlite3.Row
        return connection

    def _initialize(self) -> None:
        with self._connect() as connection:
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS player_profiles (
                    player_id TEXT PRIMARY KEY,
                    vpip REAL NOT NULL,
                    pfr REAL NOT NULL,
                    three_bet REAL NOT NULL,
                    fold_to_three_bet REAL NOT NULL,
                    cbet REAL NOT NULL,
                    aggression REAL NOT NULL,
                    river_aggression REAL NOT NULL,
                    bluff_frequency REAL NOT NULL,
                    showdown_frequency REAL NOT NULL,
                    hands_observed INTEGER NOT NULL
                );

                CREATE TABLE IF NOT EXISTS hand_sessions (
                    hand_id TEXT PRIMARY KEY,
                    player_id TEXT NOT NULL,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    current_distribution TEXT NOT NULL,
                    snapshots TEXT NOT NULL,
                    board_state TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS imported_hands (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    site TEXT NOT NULL,
                    raw_text TEXT NOT NULL,
                    parsed_json TEXT NOT NULL,
                    imported_at TEXT DEFAULT CURRENT_TIMESTAMP
                );
                """
            )

    def get_player(self, player_id: str) -> PlayerProfile:
        with self._connect() as connection:
            row = connection.execute("SELECT * FROM player_profiles WHERE player_id = ?", (player_id,)).fetchone()
        if row is None:
            profile = PlayerProfile(player_id=player_id)
            self.save_player(profile)
            return profile
        return PlayerProfile(**dict(row))

    def save_player(self, profile: PlayerProfile) -> None:
        values = profile.as_dict()
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO player_profiles (
                    player_id, vpip, pfr, three_bet, fold_to_three_bet, cbet, aggression,
                    river_aggression, bluff_frequency, showdown_frequency, hands_observed
                ) VALUES (
                    :player_id, :vpip, :pfr, :three_bet, :fold_to_three_bet, :cbet, :aggression,
                    :river_aggression, :bluff_frequency, :showdown_frequency, :hands_observed
                )
                ON CONFLICT(player_id) DO UPDATE SET
                    vpip = excluded.vpip,
                    pfr = excluded.pfr,
                    three_bet = excluded.three_bet,
                    fold_to_three_bet = excluded.fold_to_three_bet,
                    cbet = excluded.cbet,
                    aggression = excluded.aggression,
                    river_aggression = excluded.river_aggression,
                    bluff_frequency = excluded.bluff_frequency,
                    showdown_frequency = excluded.showdown_frequency,
                    hands_observed = excluded.hands_observed
                """,
                values,
            )

    def save_session(self, hand_id: str, player_id: str, distribution: dict[str, float], snapshots: list[dict[str, Any]], board_state: dict[str, Any]) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO hand_sessions (hand_id, player_id, current_distribution, snapshots, board_state)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(hand_id) DO UPDATE SET
                    current_distribution = excluded.current_distribution,
                    snapshots = excluded.snapshots,
                    board_state = excluded.board_state
                """,
                (hand_id, player_id, json.dumps(distribution), json.dumps(snapshots), json.dumps(board_state)),
            )

    def get_session(self, hand_id: str) -> dict[str, Any] | None:
        with self._connect() as connection:
            row = connection.execute("SELECT * FROM hand_sessions WHERE hand_id = ?", (hand_id,)).fetchone()
        if row is None:
            return None
        data = dict(row)
        data["current_distribution"] = json.loads(data["current_distribution"])
        data["snapshots"] = json.loads(data["snapshots"])
        data["board_state"] = json.loads(data["board_state"])
        return data

    def list_history(self, limit: int = 50) -> list[dict[str, Any]]:
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT hand_id, player_id, created_at, board_state FROM hand_sessions ORDER BY created_at DESC LIMIT ?",
                (limit,),
            ).fetchall()
        return [{**dict(row), "board_state": json.loads(row["board_state"])} for row in rows]

    def import_hand(self, site: str, raw_text: str, parsed: dict[str, Any]) -> int:
        with self._connect() as connection:
            cursor = connection.execute(
                "INSERT INTO imported_hands (site, raw_text, parsed_json) VALUES (?, ?, ?)",
                (site, raw_text, json.dumps(parsed)),
            )
            return int(cursor.lastrowid)

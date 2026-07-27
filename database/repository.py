from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any

from engine.state import PROFILE_COUNTERS, PlayerProfile

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
                    board_state TEXT NOT NULL,
                    session_profile TEXT
                );

                CREATE TABLE IF NOT EXISTS imported_hands (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    site TEXT NOT NULL,
                    raw_text TEXT NOT NULL,
                    parsed_json TEXT NOT NULL,
                    imported_at TEXT DEFAULT CURRENT_TIMESTAMP
                );

                CREATE TABLE IF NOT EXISTS predictions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    hand_id TEXT NOT NULL,
                    player_id TEXT NOT NULL,
                    street TEXT NOT NULL,
                    final_distribution TEXT NOT NULL,
                    true_class TEXT NOT NULL,
                    log_loss REAL NOT NULL,
                    baseline_log_loss REAL NOT NULL,
                    skill REAL NOT NULL,
                    percentile REAL NOT NULL,
                    top_10_hit INTEGER NOT NULL,
                    predicted_probability REAL NOT NULL,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE (hand_id, street)
                );
                """
            )
            columns = {
                row["name"]
                for row in connection.execute("PRAGMA table_info(hand_sessions)").fetchall()
            }
            if "session_profile" not in columns:
                connection.execute("ALTER TABLE hand_sessions ADD COLUMN session_profile TEXT")

            profile_columns = {
                row["name"]
                for row in connection.execute("PRAGMA table_info(player_profiles)").fetchall()
            }
            for counter in PROFILE_COUNTERS:
                if counter not in profile_columns:
                    connection.execute(
                        f"ALTER TABLE player_profiles ADD COLUMN {counter} INTEGER NOT NULL DEFAULT 0"
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
        columns = list(values)
        assignments = ", ".join(f"{column} = excluded.{column}" for column in columns if column != "player_id")
        with self._connect() as connection:
            connection.execute(
                f"""
                INSERT INTO player_profiles ({", ".join(columns)})
                VALUES ({", ".join(f":{column}" for column in columns)})
                ON CONFLICT(player_id) DO UPDATE SET {assignments}
                """,
                values,
            )

    def save_session(
        self,
        hand_id: str,
        player_id: str,
        distribution: dict[str, float],
        snapshots: list[dict[str, Any]],
        board_state: dict[str, Any],
        session_profile: PlayerProfile | None = None,
    ) -> None:
        profile_payload = json.dumps(session_profile.as_dict()) if session_profile else None
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO hand_sessions (hand_id, player_id, current_distribution, snapshots, board_state, session_profile)
                VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(hand_id) DO UPDATE SET
                    current_distribution = excluded.current_distribution,
                    snapshots = excluded.snapshots,
                    board_state = excluded.board_state,
                    session_profile = excluded.session_profile
                """,
                (hand_id, player_id, json.dumps(distribution), json.dumps(snapshots), json.dumps(board_state), profile_payload),
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
        if data.get("session_profile"):
            data["session_profile"] = PlayerProfile(**json.loads(data["session_profile"]))
        else:
            data["session_profile"] = PlayerProfile(player_id=data["player_id"])
        return data

    def list_history(self, limit: int = 50) -> list[dict[str, Any]]:
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT hand_id, player_id, created_at, board_state FROM hand_sessions ORDER BY created_at DESC LIMIT ?",
                (limit,),
            ).fetchall()
        return [{**dict(row), "board_state": json.loads(row["board_state"])} for row in rows]

    def save_prediction(
        self,
        hand_id: str,
        player_id: str,
        street: str,
        distribution: dict[str, float],
        true_class: str,
        score: dict[str, Any],
    ) -> None:
        """Persist one scored prediction. Re-scoring a street overwrites its row."""
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO predictions (
                    hand_id, player_id, street, final_distribution, true_class,
                    log_loss, baseline_log_loss, skill, percentile, top_10_hit, predicted_probability
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(hand_id, street) DO UPDATE SET
                    player_id = excluded.player_id,
                    final_distribution = excluded.final_distribution,
                    true_class = excluded.true_class,
                    log_loss = excluded.log_loss,
                    baseline_log_loss = excluded.baseline_log_loss,
                    skill = excluded.skill,
                    percentile = excluded.percentile,
                    top_10_hit = excluded.top_10_hit,
                    predicted_probability = excluded.predicted_probability,
                    created_at = CURRENT_TIMESTAMP
                """,
                (
                    hand_id,
                    player_id,
                    street,
                    json.dumps(distribution),
                    true_class,
                    float(score["log_loss"]),
                    float(score["baseline_log_loss"]),
                    float(score["skill"]),
                    float(score["percentile"]),
                    1 if score["top_10_hit"] else 0,
                    float(score["predicted_probability"]),
                ),
            )

    def list_predictions(
        self,
        player_id: str | None = None,
        street: str | None = None,
        limit: int | None = None,
    ) -> list[dict[str, Any]]:
        clauses: list[str] = []
        parameters: list[Any] = []
        if player_id:
            clauses.append("player_id = ?")
            parameters.append(player_id)
        if street:
            clauses.append("street = ?")
            parameters.append(street)
        where = f" WHERE {' AND '.join(clauses)}" if clauses else ""
        query = f"SELECT * FROM predictions{where} ORDER BY id DESC"
        if limit is not None:
            query += " LIMIT ?"
            parameters.append(limit)
        with self._connect() as connection:
            rows = connection.execute(query, parameters).fetchall()
        return [{**dict(row), "top_10_hit": bool(row["top_10_hit"])} for row in rows]

    def import_hand(self, site: str, raw_text: str, parsed: dict[str, Any]) -> int:
        with self._connect() as connection:
            cursor = connection.execute(
                "INSERT INTO imported_hands (site, raw_text, parsed_json) VALUES (?, ?, ?)",
                (site, raw_text, json.dumps(parsed)),
            )
            return int(cursor.lastrowid)

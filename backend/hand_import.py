from __future__ import annotations

import re
from typing import Any

from engine.state import ActionType, Street

SITE_PATTERNS = {
    "pokerstars": "PokerStars",
    "ggpoker": "GGPoker",
    "wsop": "WSOP Online",
    "ignition": "Ignition",
}


def detect_site(raw_text: str, fallback: str) -> str:
    lower = raw_text.lower()
    for key, label in SITE_PATTERNS.items():
        if key in lower:
            return label
    return fallback


def parse_hand_history(raw_text: str, site: str) -> dict[str, Any]:
    detected_site = detect_site(raw_text, site)
    actions: list[dict[str, Any]] = []
    current_street = Street.PREFLOP
    board_cards: list[str] = []

    for line in raw_text.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        upper = stripped.upper()
        if " FLOP " in upper or upper.startswith("*** FLOP"):
            current_street = Street.FLOP
            board_cards.extend(re.findall(r"[AKQJT2-9][shdc]", stripped))
            continue
        if " TURN " in upper or upper.startswith("*** TURN"):
            current_street = Street.TURN
            board_cards.extend(re.findall(r"[AKQJT2-9][shdc]", stripped))
            continue
        if " RIVER " in upper or upper.startswith("*** RIVER"):
            current_street = Street.RIVER
            board_cards.extend(re.findall(r"[AKQJT2-9][shdc]", stripped))
            continue

        action_type = _extract_action_type(stripped)
        if action_type is None:
            continue
        player = stripped.split(":", 1)[0] if ":" in stripped else "unknown"
        amount_match = re.search(r"(\d+(?:\.\d+)?)", stripped)
        amount = float(amount_match.group(1)) if amount_match else 0.0
        actions.append(
            {
                "player_id": player,
                "street": current_street.value,
                "action_type": action_type.value,
                "amount": amount,
                "raw_line": stripped,
            }
        )

    return {"site": detected_site, "board_cards": board_cards, "actions": actions}


def _extract_action_type(line: str) -> ActionType | None:
    lowered = line.lower()
    if "fold" in lowered:
        return ActionType.FOLD
    if "check" in lowered:
        return ActionType.CHECK
    if "call" in lowered:
        return ActionType.CALL
    if "raises" in lowered or "raise" in lowered:
        return ActionType.RAISE
    if "bets" in lowered or "bet" in lowered:
        return ActionType.BET
    return None

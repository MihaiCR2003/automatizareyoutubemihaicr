"""Continuitatea serialului (memoria povestii) intre episoade.

Reutilizeaza tabela "runs" existenta (storage generic run_id -> data),
salvand starea sub un run_id fix derivat din slug-ul serialului.
"""

from __future__ import annotations

from typing import Any

from src.config import CONFIG
from src.storage import db


def _state_key() -> str:
    return f"series_{CONFIG['series']['slug']}"


def get_state() -> dict[str, Any] | None:
    """Returneaza starea curenta a serialului (episode_number, memorie, etc.) sau None la episodul 1."""
    return db.get_run(_state_key())


def save_state(data: dict[str, Any]) -> None:
    """Salveaza starea serialului (suprascrie integral)."""
    db.save_run(_state_key(), {"status": "series_state", **data})

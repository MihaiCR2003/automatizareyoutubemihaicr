"""Stocare stare pipeline (idei in asteptare, status upload).

Foloseste Firebase Realtime DB daca este configurat (FIREBASE_DB_URL +
firebase_credentials.json). Altfel, cade automat pe un fisier JSON local
(output/runs.json), util pentru testare fara cont Firebase.
"""

from __future__ import annotations

import json
from typing import Any

from src.config import env, path_from_root

_app = None

_LOCAL_STORE = path_from_root("output", "runs.json")


def _firebase_configured() -> bool:
    cred_path = path_from_root(env("FIREBASE_CREDENTIALS_FILE", "config/firebase_credentials.json"))
    return cred_path.exists() and bool(env("FIREBASE_DB_URL"))


def _get_app():
    global _app
    if _app is None:
        import firebase_admin
        from firebase_admin import credentials

        cred_path = path_from_root(env("FIREBASE_CREDENTIALS_FILE", "config/firebase_credentials.json"))
        cred = credentials.Certificate(str(cred_path))
        _app = firebase_admin.initialize_app(
            cred, {"databaseURL": env("FIREBASE_DB_URL")}
        )
    return _app


def _load_local() -> dict[str, Any]:
    if _LOCAL_STORE.exists():
        return json.loads(_LOCAL_STORE.read_text(encoding="utf-8"))
    return {}


def _save_local(runs: dict[str, Any]) -> None:
    _LOCAL_STORE.parent.mkdir(parents=True, exist_ok=True)
    _LOCAL_STORE.write_text(json.dumps(runs, ensure_ascii=False, indent=2), encoding="utf-8")


def save_run(run_id: str, data: dict[str, Any]) -> None:
    """Salveaza datele unei rulari (script, status, link video etc.)."""
    if _firebase_configured():
        from firebase_admin import db

        _get_app()
        db.reference(f"runs/{run_id}").set(data)
        return

    runs = _load_local()
    runs[run_id] = data
    _save_local(runs)


def update_run(run_id: str, updates: dict[str, Any]) -> None:
    if _firebase_configured():
        from firebase_admin import db

        _get_app()
        db.reference(f"runs/{run_id}").update(updates)
        return

    runs = _load_local()
    runs.setdefault(run_id, {}).update(updates)
    _save_local(runs)


def get_run(run_id: str) -> dict[str, Any] | None:
    if _firebase_configured():
        from firebase_admin import db

        _get_app()
        return db.reference(f"runs/{run_id}").get()

    return _load_local().get(run_id)


def get_pending_runs() -> dict[str, Any]:
    """Returneaza rularile care asteapta aprobare/upload."""
    if _firebase_configured():
        from firebase_admin import db

        _get_app()
        runs = db.reference("runs").order_by_child("status").equal_to("pending_approval").get()
        return runs or {}

    return {
        run_id: data
        for run_id, data in _load_local().items()
        if data.get("status") == "pending_approval"
    }

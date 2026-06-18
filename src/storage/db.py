"""Stocare stare pipeline (idei in asteptare, status upload).

Foloseste Supabase (Postgres via REST/PostgREST) daca este configurat
(SUPABASE_URL + SUPABASE_KEY). Altfel, cade automat pe un fisier JSON
local (output/runs.json), util pentru testare fara cont Supabase.

Schema necesara este in supabase/schema.sql.
"""

from __future__ import annotations

import json
from typing import Any

import requests

from src.config import env, path_from_root

_LOCAL_STORE = path_from_root("output", "runs.json")


def _supabase_configured() -> bool:
    return bool(env("SUPABASE_URL")) and bool(env("SUPABASE_KEY"))


def _supabase_headers() -> dict[str, str]:
    key = env("SUPABASE_KEY")
    return {
        "apikey": key,
        "Authorization": f"Bearer {key}",
        "Content-Type": "application/json",
    }


def _runs_url() -> str:
    base = env("SUPABASE_URL").rstrip("/")
    if not base.endswith("/rest/v1"):
        base = f"{base}/rest/v1"
    return f"{base}/runs"


def _load_local() -> dict[str, Any]:
    if _LOCAL_STORE.exists():
        return json.loads(_LOCAL_STORE.read_text(encoding="utf-8"))
    return {}


def _save_local(runs: dict[str, Any]) -> None:
    _LOCAL_STORE.parent.mkdir(parents=True, exist_ok=True)
    _LOCAL_STORE.write_text(json.dumps(runs, ensure_ascii=False, indent=2), encoding="utf-8")


def save_run(run_id: str, data: dict[str, Any]) -> None:
    """Salveaza datele unei rulari (script, status, link video etc.)."""
    if _supabase_configured():
        payload = {"run_id": run_id, "status": data.get("status"), "data": data}
        headers = {**_supabase_headers(), "Prefer": "resolution=merge-duplicates"}
        response = requests.post(_runs_url(), headers=headers, json=payload, timeout=30)
        response.raise_for_status()
        return

    runs = _load_local()
    runs[run_id] = data
    _save_local(runs)


def update_run(run_id: str, updates: dict[str, Any]) -> None:
    if _supabase_configured():
        run = get_run(run_id) or {}
        run.update(updates)
        save_run(run_id, run)
        return

    runs = _load_local()
    runs.setdefault(run_id, {}).update(updates)
    _save_local(runs)


def get_run(run_id: str) -> dict[str, Any] | None:
    if _supabase_configured():
        response = requests.get(
            _runs_url(),
            headers=_supabase_headers(),
            params={"run_id": f"eq.{run_id}", "select": "data"},
            timeout=30,
        )
        response.raise_for_status()
        rows = response.json()
        return rows[0]["data"] if rows else None

    return _load_local().get(run_id)


def get_recent_topics(days: int = 7) -> list[str]:
    """Returns topics used in the last N days to avoid repetition across runs."""
    from datetime import datetime, timedelta

    cutoff = datetime.now() - timedelta(days=days)

    if _supabase_configured():
        try:
            response = requests.get(
                _runs_url(),
                headers=_supabase_headers(),
                params={"select": "data", "order": "run_id.desc", "limit": "100"},
                timeout=30,
            )
            if not response.ok:
                return []
            runs_data = [row.get("data") for row in response.json()]
        except requests.RequestException:
            return []
    else:
        runs_data = list(_load_local().values())

    recent: list[str] = []
    for data in runs_data:
        if not isinstance(data, dict):
            continue
        try:
            run_time = datetime.fromisoformat(data.get("created_at", ""))
        except (ValueError, TypeError):
            continue
        if run_time >= cutoff and data.get("topic"):
            recent.append(data["topic"])

    return recent


def get_pending_runs() -> dict[str, Any]:
    """Returneaza rularile care asteapta aprobare/upload."""
    if _supabase_configured():
        response = requests.get(
            _runs_url(),
            headers=_supabase_headers(),
            params={"status": "eq.pending_approval", "select": "run_id,data"},
            timeout=30,
        )
        response.raise_for_status()
        return {row["run_id"]: row["data"] for row in response.json()}

    return {
        run_id: data
        for run_id, data in _load_local().items()
        if data.get("status") == "pending_approval"
    }

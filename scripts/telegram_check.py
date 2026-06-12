"""Verifica mesaje noi in Telegram pentru comenzi /video sau /generate.

Folosit de workflow-ul telegram-listener.yml: citeste update-urile noi de la
Telegram, retine ultimul update_id procesat (in Supabase / fallback local),
trimite o confirmare imediata pe Telegram si scrie output-uri pentru
GitHub Actions (should_run, topic) astfel incat job-ul de generare sa fie
declansat doar daca a fost gasita o comanda noua.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import requests

from src.config import env
from src.storage import db

STATE_RUN_ID = "_telegram_listener_state"
COMMANDS = ("/video", "/generate")


def main() -> None:
    token = env("TELEGRAM_BOT_TOKEN")
    chat_id = str(env("TELEGRAM_CHAT_ID"))

    state = db.get_run(STATE_RUN_ID) or {}
    last_update_id = state.get("last_update_id", 0)

    response = requests.get(
        f"https://api.telegram.org/bot{token}/getUpdates",
        params={"offset": last_update_id + 1, "timeout": 0},
        timeout=30,
    )
    response.raise_for_status()
    updates = response.json().get("result", [])

    topic = None
    max_update_id = last_update_id

    for update in updates:
        max_update_id = max(max_update_id, update["update_id"])
        message = update.get("message") or {}
        text = (message.get("text") or "").strip()

        if str(message.get("chat", {}).get("id")) != chat_id:
            continue

        for cmd in COMMANDS:
            if text.startswith(cmd):
                topic = text[len(cmd):].strip()
                break

    if max_update_id > last_update_id:
        db.save_run(STATE_RUN_ID, {"status": "system", "last_update_id": max_update_id})

    github_output = os.environ.get("GITHUB_OUTPUT")
    if not github_output:
        return

    with open(github_output, "a", encoding="utf-8") as f:
        if topic is not None:
            f.write("should_run=true\n")
            f.write("topic<<TOPIC_EOF\n")
            f.write(f"{topic}\n")
            f.write("TOPIC_EOF\n")

            requests.post(
                f"https://api.telegram.org/bot{token}/sendMessage",
                json={
                    "chat_id": chat_id,
                    "text": (
                        "Am primit comanda! Pornesc generarea unui video nou"
                        + (f" despre: {topic}" if topic else " (subiect din trending)")
                        + ". Iti trimit un mesaj cand incepe generarea efectiva."
                    ),
                },
                timeout=15,
            )
        else:
            f.write("should_run=false\n")


if __name__ == "__main__":
    main()

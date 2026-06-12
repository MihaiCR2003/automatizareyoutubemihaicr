"""Trimite notificari simple catre Telegram (folosit de pipeline-ul automat)."""

from __future__ import annotations

from pathlib import Path

import requests

from src.config import env

API_BASE = "https://api.telegram.org/bot{token}"


def _api_url(method: str) -> str:
    token = env("TELEGRAM_BOT_TOKEN")
    return f"{API_BASE.format(token=token)}/{method}"


def send_message(text: str) -> None:
    chat_id = env("TELEGRAM_CHAT_ID")
    requests.post(_api_url("sendMessage"), data={"chat_id": chat_id, "text": text}, timeout=30)


def send_video(video_path: Path, caption: str = "") -> None:
    chat_id = env("TELEGRAM_CHAT_ID")
    with open(video_path, "rb") as f:
        requests.post(
            _api_url("sendVideo"),
            data={"chat_id": chat_id, "caption": caption},
            files={"video": f},
            timeout=300,
        )


def send_photo(photo_path: Path, caption: str = "") -> None:
    chat_id = env("TELEGRAM_CHAT_ID")
    with open(photo_path, "rb") as f:
        requests.post(
            _api_url("sendPhoto"),
            data={"chat_id": chat_id, "caption": caption},
            files={"photo": f},
            timeout=120,
        )

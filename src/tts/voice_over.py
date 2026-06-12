"""Generare voice-over natural in limba romana folosind Edge TTS (gratuit, fara API key)."""

from __future__ import annotations

import asyncio
from pathlib import Path

import edge_tts

from src.config import CONFIG


def generate_voice_over(text: str, output_path: Path) -> Path:
    """Genereaza fisierul audio de voice-over si il salveaza la output_path."""
    tts_cfg = CONFIG["tts"]
    voice = tts_cfg["voice"]
    rate = tts_cfg.get("rate", "+0%")
    pitch = tts_cfg.get("pitch", "+0Hz")

    output_path.parent.mkdir(parents=True, exist_ok=True)
    communicate = edge_tts.Communicate(text, voice, rate=rate, pitch=pitch)
    asyncio.run(communicate.save(str(output_path)))

    return output_path


if __name__ == "__main__":
    generate_voice_over(
        "Acesta este un test de voce in limba romana, cu diacritice: ă, â, î, ș, ț.",
        Path("output/test_voice.mp3"),
    )

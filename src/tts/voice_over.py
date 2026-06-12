"""Generare voice-over natural in limba romana folosind Edge TTS (gratuit, fara API key)."""

from __future__ import annotations

import asyncio
from pathlib import Path

import edge_tts
from pydub import AudioSegment

from src.config import CONFIG


def _synthesize(text: str, output_path: Path) -> None:
    tts_cfg = CONFIG["tts"]
    voice = tts_cfg["voice"]
    rate = tts_cfg.get("rate", "+0%")
    pitch = tts_cfg.get("pitch", "+0Hz")

    communicate = edge_tts.Communicate(text, voice, rate=rate, pitch=pitch)
    asyncio.run(communicate.save(str(output_path)))


def generate_voice_over(text: str, output_path: Path) -> Path:
    """Genereaza fisierul audio de voice-over si il salveaza la output_path."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    _synthesize(text, output_path)
    return output_path


def generate_voice_over_segments(segments: list[dict], output_dir: Path) -> tuple[Path, list[dict]]:
    """Genereaza voice-over separat pentru fiecare segment si le imbina intr-un singur fisier.

    Sintetizand fiecare segment individual obtinem durata audio reala a fiecaruia,
    folosita apoi pentru a sincroniza exact subtitrarile si expresiile personajului
    cu vocea (in loc de o estimare proportionala dupa lungimea textului).

    Returneaza calea fisierului audio final si segmentele imbogatite cu
    cheile "start" si "duration" (in secunde).
    """
    output_dir.mkdir(parents=True, exist_ok=True)

    combined = AudioSegment.empty()
    timed_segments = []

    for i, seg in enumerate(segments):
        text = seg.get("text", "").strip()
        if not text:
            continue

        seg_path = output_dir / f"_segment_{i:02d}.mp3"
        _synthesize(text, seg_path)

        audio = AudioSegment.from_file(seg_path)
        start = len(combined) / 1000.0
        duration = len(audio) / 1000.0

        combined += audio
        timed_segments.append({**seg, "start": start, "duration": duration})

        seg_path.unlink(missing_ok=True)

    output_path = output_dir / "voice_over.mp3"
    combined.export(output_path, format="mp3")

    return output_path, timed_segments


if __name__ == "__main__":
    generate_voice_over(
        "Acesta este un test de voce in limba romana, cu diacritice: ă, â, î, ș, ț.",
        Path("output/test_voice.mp3"),
    )

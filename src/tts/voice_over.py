"""Generare voice-over natural in limba romana folosind Edge TTS (gratuit, fara API key)."""

from __future__ import annotations

import asyncio
import random
from pathlib import Path

import edge_tts
from pydub import AudioSegment

from src.config import CONFIG


def _pick_voice() -> str:
    tts_cfg = CONFIG["tts"]
    voices = tts_cfg.get("voices")
    if voices:
        return random.choice(voices)
    return tts_cfg["voice"]


async def _synthesize_with_timings(text: str, voice: str, rate: str, pitch: str, output_path: Path) -> list[dict]:
    """Sintetizeaza `text` si salveaza audio-ul, returnand timpii fiecarui cuvant (in secunde)."""
    communicate = edge_tts.Communicate(text, voice, rate=rate, pitch=pitch)
    word_boundaries = []

    with open(output_path, "wb") as f:
        async for chunk in communicate.stream():
            if chunk["type"] == "audio":
                f.write(chunk["data"])
            elif chunk["type"] == "WordBoundary":
                word_boundaries.append(
                    {
                        "text": chunk["text"],
                        "offset": chunk["offset"] / 1e7,
                        "duration": chunk["duration"] / 1e7,
                    }
                )

    return word_boundaries


def generate_voice_over(text: str, output_path: Path) -> Path:
    """Genereaza fisierul audio de voice-over si il salveaza la output_path."""
    tts_cfg = CONFIG["tts"]
    rate = tts_cfg.get("rate", "+0%")
    pitch = tts_cfg.get("pitch", "+0Hz")

    output_path.parent.mkdir(parents=True, exist_ok=True)
    asyncio.run(_synthesize_with_timings(text, _pick_voice(), rate, pitch, output_path))
    return output_path


def generate_voice_over_segments(segments: list[dict], output_dir: Path) -> tuple[Path, list[dict]]:
    """Genereaza voice-over separat pentru fiecare segment si le imbina intr-un singur fisier.

    Sintetizand fiecare segment individual obtinem durata audio reala si timpii
    exacti ai fiecarui cuvant, folositi apoi pentru a sincroniza perfect
    subtitrarile (efect karaoke, cuvant cu cuvant) si expresiile personajului
    cu vocea.

    Returneaza calea fisierului audio final si segmentele imbogatite cu
    cheile "start", "duration" (secunde) si "words" (lista de
    {text, start, duration}).
    """
    tts_cfg = CONFIG["tts"]
    rate = tts_cfg.get("rate", "+0%")
    pitch = tts_cfg.get("pitch", "+0Hz")
    voice = _pick_voice()

    output_dir.mkdir(parents=True, exist_ok=True)

    combined = AudioSegment.empty()
    timed_segments = []

    for i, seg in enumerate(segments):
        text = seg.get("text", "").strip()
        if not text:
            continue

        seg_path = output_dir / f"_segment_{i:02d}.mp3"
        word_boundaries = asyncio.run(_synthesize_with_timings(text, voice, rate, pitch, seg_path))

        audio = AudioSegment.from_file(seg_path)
        start = len(combined) / 1000.0
        duration = len(audio) / 1000.0
        combined += audio

        words = [
            {"text": wb["text"], "start": start + wb["offset"], "duration": wb["duration"]}
            for wb in word_boundaries
        ]

        timed_segments.append({**seg, "start": start, "duration": duration, "words": words})
        seg_path.unlink(missing_ok=True)

    output_path = output_dir / "voice_over.mp3"
    combined.export(output_path, format="mp3")

    return output_path, timed_segments


if __name__ == "__main__":
    generate_voice_over(
        "Acesta este un test de voce in limba romana, cu diacritice: ă, â, î, ș, ț.",
        Path("output/test_voice.mp3"),
    )

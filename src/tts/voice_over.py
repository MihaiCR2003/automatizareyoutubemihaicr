"""Generare voice-over natural in limba romana folosind Edge TTS (gratuit, fara API key)."""

from __future__ import annotations

import asyncio
import random
import re
from pathlib import Path

import edge_tts
from pydub import AudioSegment

from src.config import CONFIG

# Cuvinte/expresii in limba engleza marcate in script intre tilde, ex: ~Elon Musk~,
# pentru a fi pronuntate cu o voce nativa engleza.
_LANG_CHUNK_RE = re.compile(r"~([^~]+)~")


def _pick_voice_pair() -> dict:
    """Alege o pereche de voci (romana + engleza) pentru acest video."""
    tts_cfg = CONFIG["tts"]
    voices = tts_cfg.get("voices")
    if voices:
        pair = random.choice(voices)
        return {"ro": pair["ro"], "en": pair.get("en", tts_cfg.get("voice_en"))}
    return {"ro": tts_cfg["voice"], "en": tts_cfg.get("voice_en")}


def _jitter(value: str, spread: int) -> str:
    """Aplica o variatie aleatoare mica unei valori gen '+2%' sau '+5Hz', pentru o voce mai umana."""
    if not spread:
        return value

    match = re.match(r"([+-]?\d+)(.*)", value)
    if not match:
        return value

    base, unit = int(match.group(1)), match.group(2)
    return f"{base + random.randint(-spread, spread):+d}{unit}"


async def _synthesize_with_timings(text: str, voice: str, rate: str, pitch: str, output_path: Path) -> list[dict]:
    """Sintetizeaza `text` si salveaza audio-ul, returnand timpii fiecarui cuvant (in secunde)."""
    communicate = edge_tts.Communicate(text, voice, rate=rate, pitch=pitch, boundary="WordBoundary")
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


def _has_letters(text: str) -> bool:
    return bool(re.search(r"[^\W\d_]", text, re.UNICODE))


def _split_lang_chunks(text: str) -> list[tuple[str, bool]]:
    """Imparte textul in bucati (text, este_engleza) pe baza marcajelor ~...~.

    Bucatile formate doar din punctuatie (ex: un "." ramas singur dupa un
    marcaj de final) sunt alipite la bucata precedenta, pentru ca edge-tts
    nu poate sintetiza text fara litere.
    """
    raw_chunks = []
    last_end = 0

    for m in _LANG_CHUNK_RE.finditer(text):
        before = text[last_end : m.start()]
        if before.strip():
            raw_chunks.append((before, False))

        foreign = m.group(1)
        if foreign.strip():
            raw_chunks.append((foreign, True))

        last_end = m.end()

    remainder = text[last_end:]
    if remainder.strip():
        raw_chunks.append((remainder, False))

    if not raw_chunks:
        return [(text, False)]

    chunks: list[tuple[str, bool]] = []
    for chunk_text, is_english in raw_chunks:
        if chunks and not _has_letters(chunk_text):
            prev_text, prev_is_english = chunks[-1]
            chunks[-1] = (prev_text + chunk_text, prev_is_english)
        else:
            chunks.append((chunk_text, is_english))

    return chunks


def generate_voice_over(text: str, output_path: Path) -> Path:
    """Genereaza fisierul audio de voice-over si il salveaza la output_path."""
    tts_cfg = CONFIG["tts"]
    rate = tts_cfg.get("rate", "+0%")
    pitch = tts_cfg.get("pitch", "+0Hz")

    output_path.parent.mkdir(parents=True, exist_ok=True)
    asyncio.run(_synthesize_with_timings(text, _pick_voice_pair()["ro"], rate, pitch, output_path))
    return output_path


def generate_voice_over_segments(segments: list[dict], output_dir: Path) -> tuple[Path, list[dict]]:
    """Genereaza voice-over separat pentru fiecare segment si le imbina intr-un singur fisier.

    Sintetizand fiecare segment individual obtinem durata audio reala si timpii
    exacti ai fiecarui cuvant, folositi apoi pentru a sincroniza perfect
    subtitrarile (efect karaoke, cuvant cu cuvant) si expresiile personajului
    cu vocea.

    Cuvintele/expresiile marcate in text cu ~asa~ (nume proprii, termeni in
    limba engleza etc.) sunt sintetizate separat cu o voce nativa engleza,
    pentru o pronuntie corecta, apoi imbinate in audio-ul segmentului.

    Returneaza calea fisierului audio final si segmentele imbogatite cu
    cheile "start", "duration" (secunde) si "words" (lista de
    {text, start, duration}).
    """
    tts_cfg = CONFIG["tts"]
    base_rate = tts_cfg.get("rate", "+0%")
    base_pitch = tts_cfg.get("pitch", "+0Hz")
    rate_jitter = tts_cfg.get("rate_jitter", 0)
    pitch_jitter = tts_cfg.get("pitch_jitter", 0)
    voice_pair = _pick_voice_pair()

    output_dir.mkdir(parents=True, exist_ok=True)

    combined = AudioSegment.empty()
    timed_segments = []

    for i, seg in enumerate(segments):
        raw_text = seg.get("text", "").strip()
        if not raw_text:
            continue

        rate = _jitter(base_rate, rate_jitter)
        pitch = _jitter(base_pitch, pitch_jitter)

        seg_start = len(combined) / 1000.0
        seg_audio = AudioSegment.empty()
        words = []

        for chunk_text, is_english in _split_lang_chunks(raw_text):
            chunk_text = chunk_text.strip()
            if not chunk_text:
                continue

            voice = voice_pair["en"] if (is_english and voice_pair.get("en")) else voice_pair["ro"]

            chunk_path = output_dir / f"_segment_{i:02d}_{len(words):03d}.mp3"
            word_boundaries = asyncio.run(_synthesize_with_timings(chunk_text, voice, rate, pitch, chunk_path))

            chunk_audio = AudioSegment.from_file(chunk_path)
            chunk_offset = len(seg_audio) / 1000.0

            words.extend(
                {
                    "text": wb["text"],
                    "start": seg_start + chunk_offset + wb["offset"],
                    "duration": wb["duration"],
                }
                for wb in word_boundaries
            )

            seg_audio += chunk_audio
            chunk_path.unlink(missing_ok=True)

        combined += seg_audio
        duration = len(seg_audio) / 1000.0

        timed_segments.append({**seg, "start": seg_start, "duration": duration, "words": words})

    output_path = output_dir / "voice_over.mp3"
    combined.export(output_path, format="mp3")

    return output_path, timed_segments


if __name__ == "__main__":
    generate_voice_over(
        "Acesta este un test de voce in limba romana, cu diacritice: ă, â, î, ș, ț.",
        Path("output/test_voice.mp3"),
    )

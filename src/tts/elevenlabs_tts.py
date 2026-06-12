"""Generare voice-over natural in limba romana folosind ElevenLabs (free tier)."""

from __future__ import annotations

from pathlib import Path

from elevenlabs.client import ElevenLabs

from src.config import CONFIG, env


def generate_voice_over(text: str, output_path: Path) -> Path:
    """Genereaza fisierul audio de voice-over si il salveaza la output_path.

    Free tier ElevenLabs: 10,000 caractere/luna - verifica lungimea textului
    inainte de a face request-uri repetate.
    """
    api_key = env("ELEVENLABS_API_KEY")
    voice_id = env("ELEVENLABS_VOICE_ID")
    model = CONFIG["tts"]["model"]

    client = ElevenLabs(api_key=api_key)

    audio = client.text_to_speech.convert(
        voice_id=voice_id,
        model_id=model,
        text=text,
        output_format="mp3_44100_128",
    )

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "wb") as f:
        for chunk in audio:
            f.write(chunk)

    return output_path


if __name__ == "__main__":
    generate_voice_over(
        "Acesta este un test de voce in limba romana.",
        Path("output/test_voice.mp3"),
    )

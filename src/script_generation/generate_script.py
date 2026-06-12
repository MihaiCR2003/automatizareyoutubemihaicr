"""Genereaza scriptul pentru un YouTube Short folosind Google Gemini API (free tier)."""

from __future__ import annotations

import json

import requests

from src.config import CONFIG, env

GEMINI_API_URL = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"


def _build_prompt(topic: str) -> str:
    max_tokens = CONFIG["script_generation"]["max_tokens"]
    return (
        "Esti un scenarist pentru YouTube Shorts in limba romana. "
        f"Scrie un scenariu scurt, captivant, despre subiectul: \"{topic}\". "
        "Scenariul trebuie sa contina: un titlu atractiv, o descriere scurta pentru YouTube, "
        "5-8 tag-uri relevante, si textul de voice-over (maxim 60 de secunde de vorbire, "
        "stil natural, conversational). "
        "Raspunde STRICT in format JSON cu cheile: titlu, descriere, tags, voice_over."
        f" Limiteaza raspunsul la aproximativ {max_tokens} tokeni."
    )


def generate_script(topic: str) -> dict:
    """Genereaza un dict cu titlu, descriere, tags si voice_over pentru un subiect dat."""
    model = CONFIG["script_generation"]["model"]
    api_key = env("GEMINI_API_KEY")

    payload = {
        "contents": [{"parts": [{"text": _build_prompt(topic)}]}],
        "generationConfig": {
            "temperature": 0.8,
            "maxOutputTokens": CONFIG["script_generation"]["max_tokens"],
        },
    }

    response = requests.post(
        GEMINI_API_URL.format(model=model),
        params={"key": api_key},
        json=payload,
        timeout=120,
    )
    if not response.ok:
        print(f"Gemini API error {response.status_code}: {response.text}")
    response.raise_for_status()
    result = response.json()

    generated_text = result["candidates"][0]["content"]["parts"][0]["text"]

    return _parse_script_response(generated_text, fallback_topic=topic)


def _parse_script_response(text: str, fallback_topic: str) -> dict:
    """Extrage JSON-ul din raspunsul modelului, cu fallback in caz de format invalid."""
    start = text.find("{")
    end = text.rfind("}")

    if start != -1 and end != -1:
        try:
            return json.loads(text[start : end + 1])
        except json.JSONDecodeError:
            pass

    return {
        "titlu": fallback_topic,
        "descriere": f"Un video despre {fallback_topic}.",
        "tags": [fallback_topic],
        "voice_over": text.strip(),
    }


if __name__ == "__main__":
    script = generate_script("Inteligenta artificiala in 2026")
    print(json.dumps(script, ensure_ascii=False, indent=2))

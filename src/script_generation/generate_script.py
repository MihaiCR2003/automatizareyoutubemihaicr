"""Genereaza scriptul pentru un YouTube Short folosind Google Gemini API (free tier)."""

from __future__ import annotations

import json

import requests

from src.config import CONFIG, env

GEMINI_API_URL = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"


EXPRESII_DISPONIBILE = [
    "neutral",
    "smile",
    "pointing",
    "explaining",
    "thinking",
    "surprised",
    "scared",
    "laughing",
]


def _build_prompt(topic: str, context: str = "") -> str:
    max_tokens = CONFIG["script_generation"]["max_tokens"]
    target_seconds = CONFIG["video"]["max_duration_seconds"]
    expresii = ", ".join(EXPRESII_DISPONIBILE)

    context_block = ""
    if context:
        context_block = (
            f"\nContext / stiri recente despre acest subiect (foloseste-le pentru acuratete si detalii): "
            f"\"{context}\"\n"
        )

    return (
        "Esti un scenarist expert pentru YouTube Shorts in limba romana, specializat in "
        "continut captivant care tine privitorul lipit de ecran. "
        f"Scrie un scenariu despre subiectul trending: \"{topic}\"."
        f"{context_block}"
        f"\n\nVoice-over-ul trebuie sa dureze in jur de {target_seconds} de secunde "
        "(aproximativ 1.8-2 cuvinte/secunda in limba romana, deci aproximativ "
        f"{int(target_seconds * 1.9)} de cuvinte in total). "
        "\n\nStructura narativa OBLIGATORIE pentru a maximiza retentia: "
        "1) HOOK (primele 3-5 secunde) - o intrebare provocatoare, un fapt soc sau o promisiune "
        "care creeaza curiozitate imediata, fara introduceri plictisitoare; "
        "2) BUILD-UP - dezvolta contextul si creste tensiunea/curiozitatea treptat, "
        "introduce detalii surprinzatoare pe rand; "
        "3) CLIMAX/TWIST - punctul culminant, revelatia sau informatia cea mai surprinzatoare; "
        "4) CONCLUZIE + CALL TO ACTION - o concluzie memorabila si o indemnare scurta "
        "(ex: abonare, parerea ta in comentarii, urmareste pentru partea 2). "
        "Foloseste propozitii scurte, ritm rapid, intrebari retorice si mici cliffhanger-uri "
        "intre segmente (\"dar asta nu e tot...\", \"si aici devine interesant...\") "
        "pentru a tine privitorul captivat pana la final."
        "\n\nScenariul trebuie sa contina: "
        "un titlu atractiv (sub 100 caractere, stil clickbait dar adevarat), "
        "o descriere pentru YouTube (2-3 propozitii + 3-5 hashtag-uri relevante la final), "
        "5-8 tag-uri relevante pentru subiect (fara #), "
        "si textul complet de voice-over, impartit in segmente narative scurte (propozitie/idee). "
        "Fiecare segment are propriul text si o expresie faciala pentru personaj, "
        f"aleasa STRICT din lista: {expresii}. "
        "Alege expresia in functie de continutul segmentului "
        "(ex: 'scared' pentru momente infricosatoare/tensionate, 'surprised' pentru o revelatie, "
        "'laughing' pentru ceva amuzant, 'explaining'/'thinking' pentru informatii, "
        "'pointing' pentru a atrage atentia, 'smile'/'neutral' pentru introducere/incheiere). "
        "\n\nRaspunde STRICT in format JSON cu cheile: titlu, descriere, tags, voice_over, "
        "segments (lista de obiecte cu cheile: text, expresie)."
        f" Limiteaza raspunsul la aproximativ {max_tokens} tokeni."
    )


def generate_script(topic: str, context: str = "") -> dict:
    """Genereaza un dict cu titlu, descriere, tags si voice_over pentru un subiect dat."""
    model = CONFIG["script_generation"]["model"]
    api_key = env("GEMINI_API_KEY")

    if not api_key:
        raise RuntimeError(
            "GEMINI_API_KEY nu este setat (variabila de mediu este goala sau lipseste)."
        )

    payload = {
        "contents": [{"parts": [{"text": _build_prompt(topic, context)}]}],
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
            parsed = json.loads(text[start : end + 1])
            if not parsed.get("segments"):
                parsed["segments"] = [
                    {"text": parsed.get("voice_over", ""), "expresie": "neutral"}
                ]
            return parsed
        except json.JSONDecodeError:
            pass

    return {
        "titlu": fallback_topic,
        "descriere": f"Un video despre {fallback_topic}.",
        "tags": [fallback_topic],
        "voice_over": text.strip(),
        "segments": [{"text": text.strip(), "expresie": "neutral"}],
    }


if __name__ == "__main__":
    script = generate_script("Inteligenta artificiala in 2026")
    print(json.dumps(script, ensure_ascii=False, indent=2))

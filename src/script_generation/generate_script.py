"""Genereaza scriptul pentru un YouTube Short folosind Google Gemini API."""

from __future__ import annotations

import json
import time

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

# Forme vechi/gresite ale diacriticelor (cu sedila, U+015E/U+015F/U+0162/U+0163)
# -> forme corecte romanesti (cu virgula, U+0218/U+0219/U+021A/U+021B).
_CEDILLA_TO_COMMA = str.maketrans(
    {
        "Ş": "Ș",  # Ş -> Ș
        "ş": "ș",  # ş -> ș
        "Ţ": "Ț",  # Ţ -> Ț
        "ţ": "ț",  # ţ -> ț
    }
)


def normalize_diacritics(text: str) -> str:
    """Converteste diacriticele cu sedila (ş, ţ) in formele corecte romanesti (ș, ț).

    Edge TTS pronunta diferit cele doua forme, vizual identice dar cu coduri Unicode
    diferite; aceasta normalizare asigura pronuntia corecta indiferent de varianta
    folosita de model.
    """
    if not isinstance(text, str):
        return text
    return text.translate(_CEDILLA_TO_COMMA)


def _niche_description() -> str:
    return CONFIG.get("content_strategy", {}).get(
        "niche",
        "fotbal si sport, istorie si civilizatii antice, secrete si mistere, curiozitati fascinante, stiinta si tehnologie",
    )


def _build_prompt(topic: str, context: str = "") -> str:
    context_block = ""
    if context:
        context_block = (
            f"\nContext / recent information about this topic (use it for accuracy and detail): "
            f"\"{context}\"\n"
        )

    niche = _niche_description()
    intro = (
        f"You are a professional YouTube Shorts scriptwriter specialized in viral English-language "
        f"content about: {niche}. "
        f"Write a compelling, well-researched, screen-gluing script about: \"{topic}\"."
        f"{context_block}"
    )

    return intro + _script_instructions()


def _build_candidates_prompt(candidates: list[dict]) -> str:
    """Builds a prompt that selects the best topic from a list of trending candidates."""
    candidates_text = "\n".join(
        f"{i + 1}. \"{c['topic']}\""
        + (f" — context: {c['context']}" if c.get("context") else "")
        for i, c in enumerate(candidates)
    )

    niche = _niche_description()
    intro = (
        f"You are a professional YouTube Shorts scriptwriter managing an English-language channel "
        f"specialized in: {niche}. "
        f"Your goal is to grow subscribers and views through viral, captivating content."
        "\n\nHere is a list of currently trending topics:\n"
        f"{candidates_text}\n\n"
        f"Choose the topic with the highest virality potential for the channel niche ({niche}). "
        "Prioritize in this order: (1) football/sport with a shocking or fascinating angle, "
        "(2) fascinating or mysterious historical stories, (3) secrets and mysteries, "
        "(4) mind-blowing facts or scientific curiosities, (5) technology and artificial intelligence. "
        "COMPLETELY AVOID: weather/forecasts, minor local news, celebrity gossip, "
        "personal disputes, transfers of unknown players. "
        "If no topic in the list fits the niche well, pick the closest one and find a creative "
        "angle that frames it within the channel's niche."
        "\n\nStart the JSON response with the key \"subiect_ales\" (the exact topic chosen from the list), "
        "then write the script for that topic."
    )

    return (
        intro
        + _script_instructions()
        + "\n\nRemember to include the key \"subiect_ales\" in the JSON response, "
        "alongside titlu, descriere, tags, voice_over, segments."
    )


def _pronunciation_and_diction_instructions(tone_description: str) -> str:
    """Common language, pronunciation and punctuation rules reused across all script types."""
    return (
        f"\n\nLANGUAGE: Write entirely in clear, natural American English. {tone_description} "
        "Verify factual accuracy using any context provided — do not invent false details."
        "\n\nPUNCTUATION AND PACING FOR NATURAL TTS (VERY IMPORTANT): The text-to-speech voice "
        "pauses and changes intonation EXACTLY based on punctuation marks. Punctuation is how you "
        "direct the narrator — where to stop, pause, question, or exclaim. Every sentence MUST end "
        "with the correct mark: period (.) for statements with a short normal pause; question mark (?) "
        "when the narrator asks or raises curiosity, with rising intonation; exclamation mark (!) for "
        "tension, surprise, or strong emotion, with energetic intonation. Use commas for short natural "
        "pauses inside sentences. Use em dashes (—) or ellipses (...) only for longer dramatic pauses "
        "before a revelation or cliffhanger. NEVER split a sentence without punctuation between the "
        "parts — every text fragment sent to the voice MUST be a complete sentence ending correctly, "
        "otherwise the voice cuts off mid-thought and sounds unnatural. Use exclamation marks (!) "
        "frequently for enthusiasm and energy, and question marks (?) to build curiosity and pull the "
        "viewer in. Vary sentence length: alternate short punchy sentences with longer descriptive "
        "ones. Avoid dry lists of facts; write as if you are telling a story to a friend face to face, "
        "full of energy — not reading a report."
        "\n\nIMPORTANT: Do NOT include any greeting or introduction at the start. Do NOT say the "
        "words 'title', 'json', 'description', 'tags', or any technical labels in the voice_over — "
        "the voice_over must be only the story content, natural, as if a real person is speaking."
    )


def _script_instructions() -> str:
    max_tokens = CONFIG["script_generation"]["max_tokens"]
    target_seconds = CONFIG["video"]["max_duration_seconds"]
    expresii = ", ".join(EXPRESII_DISPONIBILE)

    return (
        f"\n\nThe voice-over must last approximately {target_seconds} seconds "
        "(approximately 2.5 words per second in English, so roughly "
        f"{int(target_seconds * 2.5)} words total). "
        + _pronunciation_and_diction_instructions(
            "Use an energetic, enthusiastic tone — like a charismatic storyteller who is "
            "genuinely fascinated by what they're describing, not like a robot reading a report."
        )
        + "\n\nMANDATORY narrative structure to maximize viewer retention: "
        "1) HOOK (first 3-5 seconds) — a provocative question, a shocking fact, or a bold "
        "promise that creates instant curiosity, with NO boring introductions; "
        "2) BUILD-UP — develop the context and gradually increase tension and curiosity, "
        "reveal surprising details one at a time; "
        "3) CLIMAX/TWIST — the peak moment, the revelation or the most shocking piece of information; "
        "4) CONCLUSION + CALL TO ACTION — a memorable closing line and a short prompt "
        "(e.g. subscribe, drop your opinion in the comments, follow for part 2). "
        "Use short sentences, fast rhythm, rhetorical questions, and small cliffhangers "
        "between segments ('but that's not all...', 'and here's where it gets insane...') "
        "to keep the viewer hooked until the very end."
        "\n\nTITLE (critical for CTR — click-through rate): "
        "Write a title under 100 characters, extremely compelling, that creates strong curiosity "
        "and an irresistible urge to watch, in the style of the biggest viral YouTube Shorts channels. "
        "Use proven techniques: specific numbers ('3 things...', 'Top 5...'), high-impact emotional "
        "words ('Shocking', 'Insane', 'The Truth About...', 'Nobody Tells You...'), direct questions, "
        "or a curiosity gap (reveal part of the information but leave the most important part "
        "unanswered). Add 1-2 relevant emojis placed well (start, end, or between ideas) to grab "
        "attention in the feed (e.g. 😱 🤯 🔥 👀 ⚠️ 🚨), without overdoing it. "
        "The title must be truthful and reflect the content — ethical clickbait, not misleading."
        "\n\nDESCRIPTION (for SEO and engagement, professional large-channel style): "
        "Write 3-5 sentences structured as: a compelling summary that continues the curiosity from "
        "the title, 1-2 sentences with additional details/context that add SEO value, and a clear "
        "invitation to interact (question for comments, subscribe, or 'follow for more'). Use 1-2 "
        "relevant emojis in the text to make it lively, without overdoing it. At the end, add "
        "12-15 hashtags on a separate line chosen to maximize reach and views. Hashtags must combine: "
        "(1) high-volume generic Shorts hashtags used massively "
        "(e.g. #shorts #shortsfeed #viral #fyi #foryou #foryoupage #trending #explore), "
        "(2) niche/category hashtags with high volume for this TYPE of content "
        "(e.g. for facts/curiosities: #didyouknow #facts #funfacts #mindblowing; "
        "for mystery/secrets: #mystery #secrets #conspiracy #unexplained; "
        "for science/tech: #science #tech #ai #technology; for history: #history #ancienthistory), "
        "(3) 3-4 hashtags specific to the exact topic (name, place, event), "
        "(4) broad English-language audience hashtags (e.g. #english #usa #worldwide). "
        "Pick the most relevant and well-known hashtags for the subject and category of this video."
        "\n\nTAGS: 12-15 keywords (no #) relevant to the topic, including popular YouTube search "
        "variants related to the subject and content category (facts, mystery, science, history etc.)."
        "\n\nAnd the full voice-over text, split into short narrative segments (one sentence/idea each). "
        "Each segment has its own text and a facial expression for the character, "
        f"chosen STRICTLY from this list: {expresii}. "
        "Choose the expression based on the segment content "
        "('scared' for frightening/tense moments, 'surprised' for a revelation, "
        "'laughing' for something funny, 'explaining'/'thinking' for information, "
        "'pointing' to draw attention, 'smile'/'neutral' for opening/closing). "
        "\n\nRespond STRICTLY in JSON format with keys: titlu, descriere, tags, voice_over, "
        "segments (list of objects with keys: text, expresie)."
        f" Limit your response to approximately {max_tokens} tokens."
    )


def _call_gemini(prompt: str, max_tokens: int) -> str:
    """Apeleaza Gemini cu `prompt` si returneaza textul generat, cu retry pe erori temporare."""
    model = CONFIG["script_generation"]["model"]
    api_key = env("GEMINI_API_KEY")

    if not api_key:
        raise RuntimeError(
            "GEMINI_API_KEY nu este setat (variabila de mediu este goala sau lipseste)."
        )

    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {
            "temperature": 0.8,
            "maxOutputTokens": max_tokens,
            "thinkingConfig": {"thinkingBudget": 0},
        },
    }

    max_retries = 3
    for attempt in range(1, max_retries + 1):
        response = requests.post(
            GEMINI_API_URL.format(model=model),
            params={"key": api_key},
            json=payload,
            timeout=120,
        )
        if response.ok:
            break

        print(f"Gemini API error {response.status_code}: {response.text}")
        if response.status_code in (429, 503) and attempt < max_retries:
            time.sleep(10 * attempt)
            continue
        response.raise_for_status()

    result = response.json()
    return result["candidates"][0]["content"]["parts"][0]["text"]


def generate_script(topic: str, context: str = "") -> dict:
    """Genereaza un dict cu titlu, descriere, tags si voice_over pentru un subiect dat."""
    max_tokens = CONFIG["script_generation"]["max_tokens"]
    generated_text = _call_gemini(_build_prompt(topic, context), max_tokens)

    return _parse_script_response(generated_text, fallback_topic=topic)


def generate_script_from_candidates(candidates: list[dict]) -> dict:
    """Alege cel mai bun subiect dintr-o lista de candidati trending si genereaza scriptul.

    `candidates` este o lista de dict-uri cu cheile: topic, context.
    Returneaza scriptul (cu cheile uzuale) plus cheia "subiect_ales" cu subiectul ales.
    """
    max_tokens = CONFIG["script_generation"]["max_tokens"]
    fallback_topic = candidates[0]["topic"] if candidates else "Curiozitati interesante"

    generated_text = _call_gemini(_build_candidates_prompt(candidates), max_tokens)

    script = _parse_script_response(generated_text, fallback_topic=fallback_topic)
    script.setdefault("subiect_ales", fallback_topic)
    return script


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
            return _normalize_script_diacritics(parsed)
        except json.JSONDecodeError as exc:
            print(f"Nu am putut parsa JSON-ul de la Gemini ({exc}). Raspuns brut:\n{text}")

    return {
        "titlu": fallback_topic,
        "descriere": f"Un video despre {fallback_topic}.",
        "tags": [fallback_topic],
        "voice_over": normalize_diacritics(text.strip()),
        "segments": [{"text": normalize_diacritics(text.strip()), "expresie": "neutral"}],
        "subiect_ales": fallback_topic,
    }


def _normalize_script_diacritics(script: dict) -> dict:
    """Aplica `normalize_diacritics` pe toate campurile text ale scriptului."""
    for key in ("titlu", "descriere", "voice_over"):
        if key in script:
            script[key] = normalize_diacritics(script[key])

    for seg in script.get("segments") or []:
        if isinstance(seg, dict) and "text" in seg:
            seg["text"] = normalize_diacritics(seg["text"])

    return script


if __name__ == "__main__":
    script = generate_script("Inteligenta artificiala in 2026")
    print(json.dumps(script, ensure_ascii=False, indent=2))

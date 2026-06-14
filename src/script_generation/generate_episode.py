"""Genereaza episoade pentru serialul narativ (videoclipuri lungi, 1920x1080).

Continuitatea intre episoade este pastrata printr-un camp "memorie" (text
liber, actualizat de model la fiecare episod), care contine universul
povestii, personajele, starea curenta si cliffhanger-ul de final - suficient
pentru ca episodul urmator sa continue direct din acelasi punct.
"""

from __future__ import annotations

import json

from src.config import CONFIG
from src.script_generation.generate_script import (
    EXPRESII_DISPONIBILE,
    _call_gemini,
    _pronunciation_and_diction_instructions,
    normalize_diacritics,
)

_TONE_DESCRIPTION = (
    "un ton de narator de saga nordica - grav, captivant, cu tensiune crescatoare in "
    "momentele de horror si energie in scenele de actiune, fara a deveni monoton."
)


def _common_instructions(target_seconds: int) -> str:
    target_words = int(target_seconds * 1.9)
    expresii = ", ".join(EXPRESII_DISPONIBILE)

    return (
        f"\n\nEpisodul (voice_over) trebuie sa dureze in jur de {target_seconds} de secunde "
        "(aproximativ 1.8-2 cuvinte/secunda in limba romana, deci aproximativ "
        f"{target_words} de cuvinte in total)."
        + _pronunciation_and_diction_instructions(_TONE_DESCRIPTION)
        + "\n\nIMPARTIREA IN SEGMENTE: imparte voice_over-ul in segmente narative scurte "
        "(propozitie/idee, 1-3 propozitii fiecare). Fiecare segment are propriul text si o "
        f"expresie faciala pentru personajul narator (vikingul), aleasa STRICT din lista: "
        f"{expresii}. Alege expresia in functie de continutul segmentului "
        "(ex: 'scared' pentru momente infricosatoare/tensionate, 'surprised' pentru o "
        "revelatie, 'pointing' pentru a atrage atentia, 'explaining'/'thinking' pentru "
        "informatii/reflectii, 'laughing' pentru momente mai usoare, 'smile'/'neutral' pentru "
        "tranzitii calme)."
        "\n\nDESCRIERE (pentru SEO si engagement): scrie 3-5 propozitii care rezuma "
        "captivant evenimentele episodului fara sa dezvaluie finalul/cliffhanger-ul, urmate "
        "de o invitatie clara la interactiune (abonare pentru episodul urmator, parerea "
        "ta in comentarii). La final, adauga pe un rand separat 10-12 hashtag-uri relevante: "
        "combina hashtag-uri generice de volum mare (#povesti #story #audiobook #serial "
        "#shorts daca e cazul), hashtag-uri de gen (#horror #fantasy #actiune #drama "
        "#vikingi #mitologie #nordica, dupa caz), si hashtag-uri de localizare/limba "
        "(#romania #ro #povestiromanesti)."
        "\n\nTAGS: 10-12 tag-uri (cuvinte cheie, fara #) relevante pentru gen, personaje "
        "si universul povestii."
        "\n\nMEMORIE (FOARTE IMPORTANT, max 300 de cuvinte): la final, scrie in campul "
        "\"memorie\" un rezumat complet si autonom al starii povestii dupa acest episod - "
        "universul/lumea, personajele principale (nume, descriere scurta, motivatii, stare "
        "curenta), evenimentele cheie de pana acum si, in special, cliffhanger-ul exact cu "
        "care s-a terminat acest episod. Acest text va fi singura sursa de context pentru "
        "episodul urmator, deci trebuie sa fie clar si complet."
    )


def _build_new_series_prompt(target_seconds: int, total_episodes: int, genre: str) -> str:
    intro = (
        "Esti un scriitor profesionist roman, specializat in seriale narative pentru "
        "YouTube (gen audiobook/poveste narata), cu scopul de a tine privitorul captivat "
        f"episod de episod si de a creste numarul de abonati. "
        f"Creeaza o poveste ORIGINALA de tip {genre}, conceputa sa se intinda pe "
        f"{total_episodes} de episoade.\n\n"
        "Inventeaza: titlul serialului (scurt, memorabil), universul/lumea povestii "
        "(epoca, loc, atmosfera), si 3-5 personaje principale (nume, descriere scurta, "
        "motivatii, relatii intre ele). Apoi scrie EPISODUL 1: introduce lumea si "
        "personajele rapid si captivant (fara expuneri lungi si plictisitoare - arata prin "
        "actiune si dialog), porneste actiunea/conflictul cat mai rapid, si termina cu un "
        "cliffhanger puternic care sa starneasca curiozitatea pentru episodul 2."
    )

    return (
        intro
        + _common_instructions(target_seconds)
        + "\n\nRaspunde STRICT in format JSON cu cheile: titlu_serial (titlul serialului), "
        "titlu_episod (titlul specific episodului 1, sub 100 de caractere, atractiv), "
        "descriere, tags, voice_over, segments (lista de obiecte cu cheile: text, expresie), "
        "memorie."
    )


def _build_continuation_prompt(memorie: str, episode_number: int, total_episodes: int, target_seconds: int, genre: str) -> str:
    progress = episode_number / total_episodes

    if progress < 0.7:
        phase_note = (
            "Povestea este inca in dezvoltare: introduce complicatii noi, dezvolta "
            "personajele si conflictele existente, si pastreaza tensiunea in crestere."
        )
    elif progress < 0.95:
        phase_note = (
            "Povestea se apropie de punctul culminant general al serialului: "
            "intensifica conflictele, leaga firele narative deschise anterior si "
            "creste miza pentru personaje."
        )
    else:
        phase_note = (
            "Suntem in apropierea finalului serialului: episodul ar trebui sa avanseze "
            "decisiv spre rezolvarea conflictului central, pastrand totusi tensiune si "
            "un cliffhanger pana la episodul final."
        )

    intro = (
        f"Esti scriitorul aceluiasi serial narativ ({genre}) pentru YouTube, la episodul "
        f"{episode_number} din {total_episodes}.\n\n"
        f"MEMORIA POVESTII (stare completa de pana acum):\n\"{memorie}\"\n\n"
        "Continua povestea DIRECT din cliffhanger-ul descris in memorie, fara recapitulari "
        "lungi (cel mult o propozitie scurta de reamintire, daca ajuta la intelegere). "
        f"{phase_note} Termina episodul cu un nou cliffhanger sau o revelatie care sa "
        "starneasca curiozitatea pentru episodul urmator si sa invite la abonare."
    )

    return (
        intro
        + _common_instructions(target_seconds)
        + "\n\nRaspunde STRICT in format JSON cu cheile: titlu_episod (titlul specific "
        f"acestui episod, sub 100 de caractere, atractiv), descriere, tags, voice_over, "
        "segments (lista de obiecte cu cheile: text, expresie), memorie."
    )


def _extract_json(text: str) -> dict:
    start = text.find("{")
    end = text.rfind("}")

    if start != -1 and end != -1:
        try:
            return json.loads(text[start : end + 1])
        except json.JSONDecodeError as exc:
            print(f"Nu am putut parsa JSON-ul de la Gemini ({exc}). Raspuns brut:\n{text}")

    return {}


def generate_episode(state: dict | None) -> dict:
    """Genereaza urmatorul episod al serialului, pe baza starii (memoriei) curente.

    Daca `state` este None, genereaza episodul 1 (inventeaza o poveste noua).
    Returneaza un dict cu cheile: episode_number, titlu_serial (doar la ep. 1),
    titlu_episod, descriere, tags, voice_over, segments, memorie.
    """
    series_cfg = CONFIG["series"]
    target_seconds = series_cfg["video"]["max_duration_seconds"]
    total_episodes = series_cfg["total_episodes"]
    genre = series_cfg["genre"]
    max_tokens = series_cfg["script_generation"]["max_tokens"]

    if state is None:
        episode_number = 1
        prompt = _build_new_series_prompt(target_seconds, total_episodes, genre)
    else:
        episode_number = state.get("episode_number", 0) + 1
        prompt = _build_continuation_prompt(
            state["memorie"], episode_number, total_episodes, target_seconds, genre
        )

    generated_text = _call_gemini(prompt, max_tokens)
    script = _extract_json(generated_text)

    script["voice_over"] = normalize_diacritics(_as_text(script.get("voice_over", "")))
    script["segments"] = _normalize_segments(script.get("segments"))

    if not script["segments"]:
        script["segments"] = [{"text": script["voice_over"], "expresie": "neutral"}]

    script.setdefault("titlu_episod", f"Episodul {episode_number}")
    script.setdefault("descriere", "")
    script.setdefault("tags", [])
    script.setdefault("memorie", (state or {}).get("memorie", ""))

    for key in ("titlu_serial", "titlu_episod", "descriere", "memorie"):
        if key in script:
            script[key] = normalize_diacritics(_as_text(script[key]))

    script["episode_number"] = episode_number
    return script


def _as_text(value) -> str:
    """Converteste valoarea intr-un text simplu (Gemini poate intoarce ocazional liste de fraze)."""
    if isinstance(value, list):
        return " ".join(_as_text(v) for v in value)
    if value is None:
        return ""
    return str(value)


def _normalize_segments(segments) -> list[dict]:
    """Aduce segmentele la forma {text: str, expresie: str}, indiferent de variatiile JSON-ului Gemini."""
    if not isinstance(segments, list):
        return []

    normalized = []
    for seg in segments:
        if isinstance(seg, dict):
            text = normalize_diacritics(_as_text(seg.get("text", "")).strip())
            expresie = seg.get("expresie") if seg.get("expresie") in EXPRESII_DISPONIBILE else "neutral"
        else:
            text = normalize_diacritics(_as_text(seg).strip())
            expresie = "neutral"

        if text:
            normalized.append({"text": text, "expresie": expresie})

    return normalized

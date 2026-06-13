"""Genereaza scriptul pentru un YouTube Short folosind Google Gemini API (free tier)."""

from __future__ import annotations

import json
import time

import requests

from src.config import CONFIG, env

GEMINI_API_URL = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"


INTRO_TEMPLATE = "Salutare prieteni, astazi discutam despre {titlu}, si sper sa va placa, hai sa incepem!"


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
    context_block = ""
    if context:
        context_block = (
            f"\nContext / stiri recente despre acest subiect (foloseste-le pentru acuratete si detalii): "
            f"\"{context}\"\n"
        )

    intro = (
        "Esti un scenarist profesionist pentru YouTube Shorts in limba romana, specializat in "
        "continut de stiri/curiozitati captivant, bine documentat si tinut lipit de ecran. "
        f"Scrie un scenariu despre subiectul: \"{topic}\"."
        f"{context_block}"
    )

    return intro + _script_instructions()


def _build_candidates_prompt(candidates: list[dict]) -> str:
    """Construieste un prompt care alege cel mai bun subiect dintr-o lista de candidati trending."""
    candidates_text = "\n".join(
        f"{i + 1}. \"{c['topic']}\""
        + (f" - context: {c['context']}" if c.get("context") else "")
        for i, c in enumerate(candidates)
    )

    intro = (
        "Esti un scenarist profesionist pentru YouTube Shorts in limba romana, care administreaza "
        "un canal de stiri/curiozitati cu scopul de a creste cat mai mult numarul de abonati "
        "si vizualizari."
        "\n\nIata o lista de subiecte trending in Romania chiar acum:\n"
        f"{candidates_text}\n\n"
        "Alege subiectul cu cel mai mare potential de viralizare pentru un public larg "
        "(curiozitati, mister, stiinta, tehnologie, istorie, fapte socante, evenimente importante). "
        "Evita subiectele inguste de tip barfe locale TV/sport, transferuri de fotbalisti necunoscuti "
        "sau dispute personale intre persoane publice putin relevante, DOAR DACA nu exista "
        "o alternativa mai buna in lista - in acest caz, gaseste un unghi cat mai larg si interesant "
        "pentru subiectul ales."
        "\n\nIncepe raspunsul JSON cu cheia \"subiect_ales\" (subiectul exact ales din lista de mai sus), "
        "apoi scrie scenariul pentru acel subiect."
    )

    return (
        intro
        + _script_instructions()
        + "\n\nNu uita sa incluzi si cheia \"subiect_ales\" in JSON-ul de raspuns, "
        "alaturi de titlu, descriere, tags, voice_over, segments."
    )


def _script_instructions() -> str:
    max_tokens = CONFIG["script_generation"]["max_tokens"]
    target_seconds = CONFIG["video"]["max_duration_seconds"]
    expresii = ", ".join(EXPRESII_DISPONIBILE)

    return (
        f"\n\nVoice-over-ul trebuie sa dureze in jur de {target_seconds} de secunde "
        "(aproximativ 1.8-2 cuvinte/secunda in limba romana, deci aproximativ "
        f"{int(target_seconds * 1.9)} de cuvinte in total). "
        "\n\nCERINTE DE LIMBA (FOARTE IMPORTANT): Scrie in limba romana literara, corecta "
        "gramatical, cu toate diacriticele corecte si consistente: ă, â, î, ș, ț "
        "(NU folosi s/t simple in locul lui ș/ț si NU folosi diacritice gresite gen ş/ţ cu virgula). "
        "Foloseste un ton energic, vesel si entuziasmat - ca un narator de povesti/curiozitati "
        "carismatic, care este sincer fascinat de ce povesteste, nu ca un robot care citeste "
        "un raport. Verifica acuratetea informatiilor folosind contextul oferit, fara a inventa "
        "detalii false."
        "\n\nPUNCTUATIE PENTRU O VOCE NATURALA (FOARTE IMPORTANT, text-to-speech): "
        "fiecare propozitie TREBUIE sa se termine cu semnul de punctuatie corect "
        "(punct, semn de intrebare sau semn de exclamare) - aceste semne controleaza direct "
        "pauzele si intonatia vocii, deci sunt esentiale pentru un sunet natural, nu robotic. "
        "Foloseste des semne de exclamare (!) pentru a transmite entuziasm si energie, "
        "semne de intrebare (?) pentru a crea curiozitate si a implica privitorul, "
        "si virgule pentru pauze scurte naturale in interiorul propozitiilor. "
        "Scrie propozitii cu lungime variata (alterneaza propozitii scurte, ritmate, cu "
        "altele mai lungi si descriptive). Evita propozitii lungi, incarcate sau enumerari "
        "seci de fapte; scrie ca si cum ai povesti cuiva fata in fata, plin de energie, "
        "nu ca si cum ai citi un raport."
        "\n\nIMPORTANT: NU include nicio introducere/salut la inceput (acestea sunt adaugate "
        "separat de sistem) si NU pronunta in voice_over cuvinte ca \"titlu\", \"json\", "
        "\"descriere\", \"tags\" sau alte denumiri tehnice - voice_over-ul trebuie sa fie "
        "doar continutul povestii, natural, ca si cum ar vorbi un om real."
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
        "\n\nTITLU (foarte important pentru CTR - rata de click): "
        "scrie un titlu sub 100 de caractere, extrem de atractiv, care sa genereze curiozitate "
        "puternica si nevoia de a da click imediat, in stilul celor mai populare canale de "
        "curiozitati/povesti de pe YouTube Shorts. Foloseste tehnici dovedite: "
        "cifre concrete (\"3 lucruri...\", \"Top 5...\"), cuvinte cu impact emotional "
        "(\"Socant\", \"Incredibil\", \"Adevarul despre...\", \"Nimeni nu iti spune...\"), "
        "intrebari directe, sau un \"curiosity gap\" (dezvalui o parte din informatie, "
        "dar lasi cea mai importanta parte nedezvaluita). Adauga 1-2 emoji-uri relevante "
        "si bine plasate (la inceput, la final sau intre idei) pentru a atrage atentia in feed "
        "(ex: 😱 🤯 🔥 👀 ⚠️ 🚨), fara sa exagerezi. Titlul trebuie sa fie adevarat "
        "si sa reflecte continutul - clickbait etic, nu inselator."
        "\n\nDESCRIERE (pentru SEO si engagement, stil profesionist de canal mare): "
        "scrie 3-5 propozitii structurate astfel: un rezumat captivant care continua "
        "curiozitatea din titlu, 1-2 propozitii cu detalii/context suplimentar care dau "
        "valoare si SEO, si o invitatie clara la interactiune (intrebare pentru comentarii, "
        "abonare, sau \"urmareste pentru mai multe\"). Foloseste 1-2 emoji-uri relevante "
        "in text pentru a-l face mai viu, fara exagerare. La final, adauga 12-15 hashtag-uri "
        "pe un rand separat, alese pentru a maximiza acoperirea si vizualizarile. "
        "Hashtag-urile trebuie sa combine: "
        "(1) hashtag-uri generice de volum foarte mare, folosite masiv pe Shorts "
        "(ex: #shorts #shortsfeed #viral #fyi #foryou #foryoupage #trending #explore), "
        "(2) hashtag-uri de nisa/categorie cu volum mare si folosite frecvent pentru acest "
        "TIP de continut (ex: pentru curiozitati/fapte: #didyouknow #factos #curiozitati "
        "#stiaiCa; pentru mister/povesti: #mystery #scarystories #horror #povesti; pentru "
        "stiinta/tehnologie: #science #tech #stiinta; pentru istorie: #history #istorie), "
        "(3) 3-4 hashtag-uri specifice subiectului exact (nume, loc, eveniment), "
        "(4) hashtag-uri de localizare/limba pentru a ajunge la publicul romanesc "
        "(ex: #romania #ro #limbaromana). Alege cele mai relevante si cunoscute "
        "hashtag-uri pentru subiectul si categoria acestui video, nu hashtag-uri obscure."
        "\n\nTAGS: 12-15 tag-uri (cuvinte cheie, fara #) relevante pentru subiect, "
        "incluzand variante populare de cautare pe YouTube legate de subiect si de "
        "categoria continutului (curiozitati, mister, stiinta, istorie etc., dupa caz). "
        "\n\nsi textul complet de voice-over, impartit in segmente narative scurte (propozitie/idee). "
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

    generated_text = result["candidates"][0]["content"]["parts"][0]["text"]

    script = _parse_script_response(generated_text, fallback_topic=topic)
    return _prepend_intro(script)


def generate_script_from_candidates(candidates: list[dict]) -> dict:
    """Alege cel mai bun subiect dintr-o lista de candidati trending si genereaza scriptul.

    `candidates` este o lista de dict-uri cu cheile: topic, context.
    Returneaza scriptul (cu cheile uzuale) plus cheia "subiect_ales" cu subiectul ales.
    """
    model = CONFIG["script_generation"]["model"]
    api_key = env("GEMINI_API_KEY")

    if not api_key:
        raise RuntimeError(
            "GEMINI_API_KEY nu este setat (variabila de mediu este goala sau lipseste)."
        )

    payload = {
        "contents": [{"parts": [{"text": _build_candidates_prompt(candidates)}]}],
        "generationConfig": {
            "temperature": 0.8,
            "maxOutputTokens": CONFIG["script_generation"]["max_tokens"],
            "thinkingConfig": {"thinkingBudget": 0},
        },
    }

    fallback_topic = candidates[0]["topic"] if candidates else "Curiozitati interesante"

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

    generated_text = result["candidates"][0]["content"]["parts"][0]["text"]

    script = _parse_script_response(generated_text, fallback_topic=fallback_topic)
    script.setdefault("subiect_ales", fallback_topic)
    return _prepend_intro(script)


def _prepend_intro(script: dict) -> dict:
    """Adauga un intro fix, presetat, la inceputul voice-over-ului si segmentelor."""
    intro_text = INTRO_TEMPLATE.format(titlu=script["titlu"])

    script["voice_over"] = f"{intro_text} {script['voice_over']}"
    script["segments"] = [
        {"text": intro_text, "expresie": "smile"},
        *script["segments"],
    ]
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
            return parsed
        except json.JSONDecodeError as exc:
            print(f"Nu am putut parsa JSON-ul de la Gemini ({exc}). Raspuns brut:\n{text}")

    return {
        "titlu": fallback_topic,
        "descriere": f"Un video despre {fallback_topic}.",
        "tags": [fallback_topic],
        "voice_over": text.strip(),
        "segments": [{"text": text.strip(), "expresie": "neutral"}],
        "subiect_ales": fallback_topic,
    }


if __name__ == "__main__":
    script = generate_script("Inteligenta artificiala in 2026")
    print(json.dumps(script, ensure_ascii=False, indent=2))

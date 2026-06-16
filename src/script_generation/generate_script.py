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
            f"\nContext / stiri recente despre acest subiect (foloseste-le pentru acuratete si detalii): "
            f"\"{context}\"\n"
        )

    niche = _niche_description()
    intro = (
        f"Esti un scenarist profesionist pentru YouTube Shorts in limba romana, specializat in "
        f"continut viral despre: {niche}. "
        f"Scrie un scenariu captivant, bine documentat si tinut lipit de ecran despre subiectul: \"{topic}\"."
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

    niche = _niche_description()
    intro = (
        f"Esti un scenarist profesionist pentru YouTube Shorts in limba romana, care administreaza "
        f"un canal specializat in: {niche}. "
        f"Scopul este sa cresti numarul de abonati si vizualizari prin continut viral si captivant."
        "\n\nIata o lista de subiecte trending in Romania chiar acum:\n"
        f"{candidates_text}\n\n"
        f"Alege subiectul cu cel mai mare potential de viralizare pentru nisa canalului ({niche}). "
        "Prioritizeaza in aceasta ordine: (1) fotbal/sport cu unghi interesant sau socant, "
        "(2) povesti istorice fascinante sau misterioase, (3) secrete si mistere, "
        "(4) curiozitati stiintifice sau fapte socante, (5) tehnologie si inteligenta artificiala. "
        "EVITA complet: vreme/meteo, stiri locale fara impact national, barfe TV, "
        "dispute personale minore, transferuri de jucatori necunoscuti. "
        "Daca niciun subiect din lista nu se potriveste bine nisei, alege cel mai aproape "
        "si gaseste un unghi creativ care sa il incadreze in nisa canalului."
        "\n\nIncepe raspunsul JSON cu cheia \"subiect_ales\" (subiectul exact ales din lista), "
        "apoi scrie scenariul pentru acel subiect."
    )

    return (
        intro
        + _script_instructions()
        + "\n\nNu uita sa incluzi si cheia \"subiect_ales\" in JSON-ul de raspuns, "
        "alaturi de titlu, descriere, tags, voice_over, segments."
    )


def _pronunciation_and_diction_instructions(tone_description: str) -> str:
    """Reguli comune de limba/pronuntie/punctuatie, reutilizate de toate tipurile de scenarii."""
    return (
        "\n\nCERINTE DE LIMBA (FOARTE IMPORTANT, esential pentru pronuntie corecta): Scrie "
        "in limba romana literara, corecta gramatical, folosind OBLIGATORIU toate diacriticele "
        "corecte ale alfabetului romanesc, pentru fiecare cuvant care le contine: "
        "Ă Â Î Ș Ț (majuscule) si ă â î ș ț (minuscule). "
        "Vocea text-to-speech pronunta GRESIT cuvintele scrise fara diacritice sau cu "
        "diacritice incorecte (ex: \"sa\" vs \"să\", \"si\" vs \"și\", \"asta\" vs \"asta\" cu "
        "â/î la nevoie, \"tara\" vs \"țara\", \"fata\" vs \"față\"), deci NU este o chestiune "
        "doar de ortografie - lipsa diacriticelor schimba sensul si pronuntia complet. "
        "Foloseste STRICT formele corecte ș/ț (cu virgula dedesubt), NU s/t simple si NU "
        "formele vechi/gresite ş/ţ (cu sedila). Recitește mental fiecare propozitie inainte "
        "de a o scrie si asigura-te ca niciun cuvant care necesita ă, â, î, ș sau ț nu este "
        "scris fara el."
        f" Foloseste {tone_description} Verifica acuratetea informatiilor folosind contextul "
        "oferit, fara a inventa detalii false."
        "\n\nPUNCTUATIE, PAUZE SI INTONATIE PENTRU O VOCE NATURALA (FOARTE IMPORTANT, "
        "text-to-speech): vocea face pauze si schimba intonatia EXACT pe baza semnelor de "
        "punctuatie, deci punctuatia este modul tau de a regiza naratorul - unde se opreste, "
        "unde face pauza, unde intreaba, unde exclama. Fiecare propozitie TREBUIE sa se "
        "termine cu semnul corect: "
        "punct (.) pentru afirmatii, cu o pauza scurta normala dupa; "
        "semn de intrebare (?) cand naratorul intreaba sau ridica o nedumerire, cu o "
        "intonatie ascendenta; "
        "semn de exclamare (!) pentru tensiune, surpriza, ordine sau emotie puternica, cu "
        "intonatie energica. "
        "Foloseste virgule pentru pauze scurte naturale in interiorul propozitiilor, "
        "si linii de pauza (-) sau puncte de suspensie (...) doar atunci cand vrei o pauza mai "
        "lunga, dramatica, inainte de o revelatie sau un cliffhanger. NU rupe o propozitie in "
        "doua fara semn de punctuatie intre ele si NU lasa text fara niciun semn de "
        "punctuatie la final - fiecare fragment de text trimis spre sintetizare TREBUIE sa "
        "fie o propozitie/fraza completa, incheiata corect, altfel vocea se opreste brusc in "
        "mijlocul ideii si suna nenatural. "
        "Foloseste des semne de exclamare (!) pentru a transmite entuziasm si energie si "
        "semne de intrebare (?) pentru a crea curiozitate si a implica privitorul. "
        "Scrie propozitii cu lungime variata (alterneaza propozitii scurte, ritmate, cu "
        "altele mai lungi si descriptive). Evita propozitii lungi, incarcate sau enumerari "
        "seci de fapte; scrie ca si cum ai povesti cuiva fata in fata, plin de energie, "
        "nu ca si cum ai citi un raport."
        "\n\nPRONUNTIE CUVINTE STRAINE (FOARTE IMPORTANT): intregul voice_over este citit de o "
        "SINGURA voce romaneasca, care NU pronunta corect cuvinte scrise in ortografia "
        "originala engleza/straina. De aceea, de fiecare data cand ai nevoie de un nume propriu, "
        "cuvant, expresie sau termen strain (nume de persoane, orase, branduri, filme, jocuri, "
        "produse, termeni tehnici de tipul \"smartphone\", \"AI\", \"gaming\" etc.), scrie-l "
        "FONETIC, transcris cu litere si diacritice romanesti, exact cum se pronunta in limba "
        "originala, astfel incat vocea romaneasca sa-l pronunte corect "
        "(exemplu: \"Elon Musk\" -> \"Ilon Mask\", \"Neuralink\" -> \"Niuralink\", \"iPhone\" -> "
        "\"Aifon\", \"YouTube\" -> \"Iutiub\", \"AI\" -> \"Ei Ai\"). NU folosi ortografia "
        "originala si NU folosi vreun simbol special de marcaj - scrie totul ca text romanesc "
        "normal, natural, gata de citit de la cap la coada de o singura voce. Cuvintele straine "
        "deja asimilate complet in limba romana, cu pronuntie romaneasca uzuala, se scriu normal."
        "\n\nIMPORTANT: NU include nicio introducere/salut la inceput (acestea sunt adaugate "
        "separat de sistem) si NU pronunta in voice_over cuvinte ca \"titlu\", \"json\", "
        "\"descriere\", \"tags\" sau alte denumiri tehnice - voice_over-ul trebuie sa fie "
        "doar continutul povestii, natural, ca si cum ar vorbi un om real."
    )


def _script_instructions() -> str:
    max_tokens = CONFIG["script_generation"]["max_tokens"]
    target_seconds = CONFIG["video"]["max_duration_seconds"]
    expresii = ", ".join(EXPRESII_DISPONIBILE)

    return (
        f"\n\nVoice-over-ul trebuie sa dureze in jur de {target_seconds} de secunde "
        "(aproximativ 1.8-2 cuvinte/secunda in limba romana, deci aproximativ "
        f"{int(target_seconds * 1.9)} de cuvinte in total). "
        + _pronunciation_and_diction_instructions(
            "un ton energic, vesel si entuziasmat - ca un narator de povesti/curiozitati "
            "carismatic, care este sincer fascinat de ce povesteste, nu ca un robot care citeste "
            "un raport."
        )
        + "\n\nStructura narativa OBLIGATORIE pentru a maximiza retentia: "
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

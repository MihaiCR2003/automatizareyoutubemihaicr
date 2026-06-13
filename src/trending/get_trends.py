"""Identifica subiecte trending pentru continut video (Romania)."""

from __future__ import annotations

import xml.etree.ElementTree as ET

import requests

from src.config import CONFIG, env

RSS_URL = "https://trends.google.com/trending/rss"
YOUTUBE_VIDEOS_URL = "https://www.googleapis.com/youtube/v3/videos"

FALLBACK_TOPICS = [
    "Curiozitati despre spatiu",
    "Fapte interesante din istorie",
    "Trucuri de productivitate",
    "Mituri si adevaruri din stiinta",
    "Locuri uimitoare din Romania",
]


NEWS_ITEM_NS = "https://trends.google.com/trending/rss"


def get_trending_topics() -> list[str]:
    """Returneaza o lista de subiecte trending pentru Romania.

    Foloseste RSS-ul oficial Google Trends (gratuit, fara API key).
    Daca feed-ul nu este disponibil, cade pe o lista de subiecte generice.
    """
    return [item["topic"] for item in get_trending_topics_with_context()]


def _get_google_trends(count: int) -> list[dict]:
    """Subiecte cautate des pe Google, cu context din stirile asociate (RSS Google Trends)."""
    geo = CONFIG["trending"]["geo"]

    try:
        response = requests.get(RSS_URL, params={"geo": geo}, timeout=30)
        response.raise_for_status()

        root = ET.fromstring(response.content)
        results = []

        for item in root.iter("item"):
            title = item.findtext("title")
            if not title:
                continue

            details = []
            for news_item in item.iter(f"{{{NEWS_ITEM_NS}}}news_item"):
                snippet = news_item.findtext(f"{{{NEWS_ITEM_NS}}}news_item_snippet")
                news_title = news_item.findtext(f"{{{NEWS_ITEM_NS}}}news_item_title")
                text = (snippet or news_title or "").strip()
                if text:
                    details.append(text)

            results.append({"topic": title, "context": " ".join(details[:3])})

            if len(results) >= count:
                break

        return results
    except (requests.RequestException, ET.ParseError):
        return []


def _get_youtube_trending(count: int) -> list[dict]:
    """Video-uri populare chiar acum pe YouTube (ce vizioneaza/cauta lumea pe platforma).

    Foloseste YouTube Data API (necesita YOUTUBE_API_KEY, gratuit, cota mare).
    Daca cheia nu este configurata sau cererea esueaza, returneaza o lista vida.
    """
    api_key = env("YOUTUBE_API_KEY")
    if not api_key:
        return []

    geo = CONFIG["trending"]["geo"]

    try:
        response = requests.get(
            YOUTUBE_VIDEOS_URL,
            params={
                "part": "snippet",
                "chart": "mostPopular",
                "regionCode": geo,
                "maxResults": count,
                "key": api_key,
            },
            timeout=30,
        )
        response.raise_for_status()

        results = []
        for item in response.json().get("items", []):
            snippet = item.get("snippet", {})
            title = snippet.get("title")
            if not title:
                continue
            results.append({"topic": title, "context": snippet.get("description", "")[:300]})

        return results
    except requests.RequestException:
        return []


def get_trending_topics_with_context() -> list[dict]:
    """Returneaza subiecte cautate/vizionate de oameni acum, impreuna cu context.

    Combina doua surse: subiecte cautate pe Google (Google Trends RSS) si
    videoclipuri populare chiar acum pe YouTube (YouTube Data API, daca este
    configurata YOUTUBE_API_KEY) - astfel sunt favorizate subiectele cu sansa
    cea mai mare de vizualizari/abonati pe YouTube.

    Fiecare element are cheile: topic, context. Daca ambele surse sunt
    indisponibile, cade pe o lista de subiecte generice fara context.
    """
    count = CONFIG["trending"]["topics_count"]

    results = _get_google_trends(count) + _get_youtube_trending(count)

    seen = set()
    deduped = []
    for item in results:
        key = item["topic"].strip().lower()
        if key in seen:
            continue
        seen.add(key)
        deduped.append(item)

    if deduped:
        return deduped

    return [{"topic": topic, "context": ""} for topic in FALLBACK_TOPICS[:count]]


if __name__ == "__main__":
    for item in get_trending_topics_with_context():
        print(item["topic"])
        if item["context"]:
            print(f"  -> {item['context']}")

"""Identifica subiecte trending pentru continut video (Romania)."""

from __future__ import annotations

import random
import xml.etree.ElementTree as ET

import requests

from src.config import CONFIG, env

RSS_URL = "https://trends.google.com/trending/rss"
YOUTUBE_VIDEOS_URL = "https://www.googleapis.com/youtube/v3/videos"

NEWS_ITEM_NS = "https://trends.google.com/trending/rss"


def _get_niche_fallback_topics(count: int) -> list[dict]:
    """Returneaza subiecte de rezerva din nisa canalului, rotind aleator prin categorii."""
    fallback_by_category = CONFIG.get("content_strategy", {}).get("fallback_topics", {})

    if not fallback_by_category:
        return [
            {"topic": "Secretele istoriei antice pe care nimeni nu ti le spune", "context": ""},
            {"topic": "Cele mai incredibile fapte despre fotbal", "context": ""},
            {"topic": "Fenomene inexplicabile filmate pe camera", "context": ""},
            {"topic": "Fapte uimitoare despre corpul uman", "context": ""},
            {"topic": "Descoperiri stiintifice care schimba tot ce stiam", "context": ""},
        ][:count]

    categories = list(fallback_by_category.keys())
    random.shuffle(categories)

    result = []
    while len(result) < count:
        for cat in categories:
            topics_in_cat = fallback_by_category[cat]
            topic = random.choice(topics_in_cat)
            result.append({"topic": topic, "context": cat})
            if len(result) >= count:
                break

    return result


def _filter_excluded(topics: list[dict]) -> list[dict]:
    """Elimina subiectele care contin cuvinte cheie excluse (ex: vreme, meteo)."""
    excluded = [
        kw.lower()
        for kw in CONFIG.get("content_strategy", {}).get("excluded_keywords", [])
    ]
    if not excluded:
        return topics

    return [
        item for item in topics
        if not any(kw in item["topic"].lower() for kw in excluded)
    ]


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
    """Returneaza subiecte cautate/vizionate de oameni acum, filtrate dupa nisa canalului.

    Sursa primara: YouTube Data API. Fallback: Google Trends RSS.
    Subiectele excluse (vreme, meteo etc.) sunt filtrate automat.
    Daca dupa filtrare nu raman suficiente subiecte, completeaza cu subiecte
    din nisa canalului (fotbal, istorie, secrete, curiozitati, stiinta, tehnologie).
    """
    count = CONFIG["trending"]["topics_count"]

    youtube_results = _get_youtube_trending(count)
    if youtube_results:
        raw = youtube_results + _get_google_trends(count)
    else:
        raw = _get_google_trends(count)

    filtered = _filter_excluded(raw)

    seen = set()
    deduped = []
    for item in filtered:
        key = item["topic"].strip().lower()
        if key in seen:
            continue
        seen.add(key)
        deduped.append(item)

    if len(deduped) >= count:
        return deduped[:count * 2]

    niche_extras = _get_niche_fallback_topics(count - len(deduped))
    return deduped + niche_extras


if __name__ == "__main__":
    for item in get_trending_topics_with_context():
        print(item["topic"])
        if item["context"]:
            print(f"  -> {item['context']}")

"""Identifica subiecte trending pentru continut video (Romania)."""

from __future__ import annotations

import xml.etree.ElementTree as ET

import requests

from src.config import CONFIG

RSS_URL = "https://trends.google.com/trends/trendingsearches/daily/rss"

FALLBACK_TOPICS = [
    "Curiozitati despre spatiu",
    "Fapte interesante din istorie",
    "Trucuri de productivitate",
    "Mituri si adevaruri din stiinta",
    "Locuri uimitoare din Romania",
]


NEWS_ITEM_NS = "https://trends.google.com/trends/trendingsearches/daily"


def get_trending_topics() -> list[str]:
    """Returneaza o lista de subiecte trending pentru Romania.

    Foloseste RSS-ul oficial Google Trends (gratuit, fara API key).
    Daca feed-ul nu este disponibil, cade pe o lista de subiecte generice.
    """
    return [item["topic"] for item in get_trending_topics_with_context()]


def get_trending_topics_with_context() -> list[dict]:
    """Returneaza subiecte trending impreuna cu context (stiri asociate).

    Fiecare element are cheile: topic, context (text descriptiv preluat din
    snippet-urile de stiri asociate subiectului, util pentru generarea scriptului).
    Daca feed-ul nu este disponibil, cade pe o lista de subiecte generice fara context.
    """
    geo = CONFIG["trending"]["geo"]
    count = CONFIG["trending"]["topics_count"]

    try:
        response = requests.get(RSS_URL, params={"geo": geo}, timeout=30)
        response.raise_for_status()

        root = ET.fromstring(response.content)
        results = []

        for item in root.iter("item"):
            title = item.findtext("title")
            if not title:
                continue

            snippets = [
                snippet.text.strip()
                for snippet in item.iter(f"{{{NEWS_ITEM_NS}}}news_item_snippet")
                if snippet.text
            ]

            results.append({"topic": title, "context": " ".join(snippets[:3])})

            if len(results) >= count:
                break

        if results:
            return results
    except (requests.RequestException, ET.ParseError):
        pass

    return [{"topic": topic, "context": ""} for topic in FALLBACK_TOPICS[:count]]


if __name__ == "__main__":
    for item in get_trending_topics_with_context():
        print(item["topic"])
        if item["context"]:
            print(f"  -> {item['context']}")

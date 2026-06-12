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


def get_trending_topics() -> list[str]:
    """Returneaza o lista de subiecte trending pentru Romania.

    Foloseste RSS-ul oficial Google Trends (gratuit, fara API key).
    Daca feed-ul nu este disponibil, cade pe o lista de subiecte generice.
    """
    geo = CONFIG["trending"]["geo"]
    count = CONFIG["trending"]["topics_count"]

    try:
        response = requests.get(RSS_URL, params={"geo": geo}, timeout=30)
        response.raise_for_status()

        root = ET.fromstring(response.content)
        topics = [item.findtext("title") for item in root.iter("item")]
        topics = [t for t in topics if t][:count]

        if topics:
            return topics
    except (requests.RequestException, ET.ParseError):
        pass

    return FALLBACK_TOPICS[:count]


if __name__ == "__main__":
    for topic in get_trending_topics():
        print(topic)

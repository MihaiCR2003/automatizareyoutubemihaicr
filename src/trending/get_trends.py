"""Identifica subiecte trending pentru continut video (Romania)."""

from __future__ import annotations

from pytrends.request import TrendReq

from src.config import CONFIG


def get_trending_topics() -> list[str]:
    """Returneaza o lista de subiecte trending pentru Romania.

    Foloseste Google Trends (pytrends, gratuit, fara API key).
    """
    geo = CONFIG["trending"]["geo"]
    count = CONFIG["trending"]["topics_count"]

    pytrends = TrendReq(hl="ro-RO", tz=120)
    trending_df = pytrends.trending_searches(pn="romania" if geo == "RO" else "united_states")

    topics = trending_df[0].tolist()[:count]
    return topics


if __name__ == "__main__":
    for topic in get_trending_topics():
        print(topic)

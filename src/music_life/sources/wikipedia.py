"""Wikipedia: article text and the places an article links to that have coordinates.

Article text is CC BY-SA 4.0: keep only short context sentences, always with attribution.
"""
from __future__ import annotations

import re
from typing import Any

from .http import CachedClient

BASE_URL = "https://en.wikipedia.org"
SENTENCE_BREAK = re.compile(r"(?<=[.!?])\s+|\n+")


def client() -> CachedClient:
    return CachedClient("wikipedia", BASE_URL, min_interval=1.0)


def _slug(title: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-")


def article_url(title: str) -> str:
    return f"{BASE_URL}/wiki/{title.replace(' ', '_')}"


def _query(c: CachedClient, cache_key: str, params: dict[str, Any]) -> dict[str, Any]:
    return c.get_json(
        "w/api.php", cache_key,
        {"action": "query", "format": "json", "formatversion": 2, "redirects": 1, **params},
    )


def article_text(title: str, c: CachedClient) -> str:
    data = _query(c, f"extract-{_slug(title)}", {"prop": "extracts", "explaintext": 1, "titles": title})
    return data["query"]["pages"][0].get("extract", "")


def linked_places(title: str, c: CachedClient) -> list[dict[str, Any]]:
    """Pages linked from the article that have coordinates: towns, venues, hospitals and so on."""
    data = _query(c, f"linked-places-{_slug(title)}", {
        "generator": "links", "titles": title, "gpllimit": "max", "gplnamespace": 0,
        "prop": "coordinates|pageprops", "ppprop": "wikibase_item", "colimit": "max",
    })
    return [
        {
            "title": page["title"],
            "qid": page.get("pageprops", {}).get("wikibase_item"),
            "latitude": page["coordinates"][0]["lat"],
            "longitude": page["coordinates"][0]["lon"],
        }
        for page in data["query"]["pages"]
        if page.get("coordinates")
    ]


def sentences(text: str) -> list[str]:
    body = "\n".join(line for line in text.splitlines() if not line.strip().startswith("=="))
    return [s.strip() for s in SENTENCE_BREAK.split(body) if s.strip()]


def context_sentence(article_sentences: list[str], title: str) -> str | None:
    """First sentence naming the place ("Paisley, Renfrewshire" is searched for as "Paisley")."""
    name = re.sub(r"\s*\(.*\)$", "", title).split(",")[0].strip()
    pattern = re.compile(rf"\b{re.escape(name)}\b")
    return next((s for s in article_sentences if pattern.search(s)), None)


def place_rows(title: str, c: CachedClient, skip_qids: set[str]) -> list[dict[str, Any]]:
    """Linked places that the article text actually mentions, with the sentence as context."""
    article = sentences(article_text(title, c))
    rows = []
    for place in linked_places(title, c):
        if place["qid"] in skip_qids:
            continue
        context = context_sentence(article, place["title"])
        if context:
            rows.append({
                "role": "mentioned", "qid": place["qid"], "title": place["title"], "label_is": None, "country": None,
                "latitude": place["latitude"], "longitude": place["longitude"],
                "context": context[:400], "source_key": "wikipedia-article",
            })
    return rows


def source_row(c: CachedClient, title: str) -> dict[str, Any]:
    return {
        "source_key": "wikipedia-article",
        "source_name": "Wikipedia",
        "source_type": "encyclopedia",
        "source_url": article_url(title),
        "retrieved_at": c.retrieved_at(f"extract-{_slug(title)}"),
        "citation_text": f"English Wikipedia: {title} (CC BY-SA 4.0)",
    }

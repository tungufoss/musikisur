"""Wikidata: structured identifiers and dates, read from Special:EntityData JSON.

Used for an album's exact publication date when MusicBrainz only knows the year.
Wikidata content is CC0: https://www.wikidata.org/wiki/Wikidata:Licensing
"""
from __future__ import annotations

from typing import Any

from .http import CachedClient

BASE_URL = "https://www.wikidata.org"
DAY_PRECISION = 11


def client() -> CachedClient:
    return CachedClient("wikidata", BASE_URL, min_interval=1.0)


def fetch_entity(qid: str, c: CachedClient) -> dict[str, Any]:
    entities = c.get_json(f"wiki/Special:EntityData/{qid}.json", f"entity-{qid}")["entities"]
    # A merged item redirects, so the returned key can differ from the requested one.
    return entities.get(qid) or next(iter(entities.values()))


def publication_date(entity: dict[str, Any]) -> str | None:
    """Earliest publication date (P577) given to the day, as YYYY-MM-DD."""
    dates = []
    for claim in entity.get("claims", {}).get("P577", []):
        value = claim["mainsnak"].get("datavalue", {}).get("value", {})
        if value.get("precision") == DAY_PRECISION:
            dates.append(value["time"][1:11])
    return min(dates) if dates else None


def source_row(c: CachedClient, qid: str, label: str) -> dict[str, Any]:
    return {
        "source_key": "wikidata-album",
        "source_name": "Wikidata",
        "source_type": "database",
        "source_url": f"https://www.wikidata.org/wiki/{qid}",
        "retrieved_at": c.retrieved_at(f"entity-{qid}"),
        "citation_text": f"Wikidata {qid}: publication date (P577) of {label}",
    }

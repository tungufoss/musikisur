"""Wikidata: structured identifiers, dates, places and tags, read from the entity JSON.

Used for an album's exact publication date when MusicBrainz only knows the year, and for an
artist's birth and death (dates and places), active years, genres, instruments and occupations.
Wikidata content is CC0: https://www.wikidata.org/wiki/Wikidata:Licensing
"""
from __future__ import annotations

import hashlib
from typing import Any

from .http import CachedClient

BASE_URL = "https://www.wikidata.org"
YEAR_PRECISION, MONTH_PRECISION, DAY_PRECISION = 9, 10, 11
TAG_PROPERTIES = {"genre": "P136", "instrument": "P1303", "occupation": "P106"}
PLACE_PROPERTIES = {"birth": "P19", "death": "P20", "residence": "P551"}
EVENT_PROPERTIES = {"birth": "P569", "death": "P570", "career_start": "P2031", "career_end": "P2032"}


def client() -> CachedClient:
    return CachedClient("wikidata", BASE_URL, min_interval=1.0)


def fetch_entity(qid: str, c: CachedClient) -> dict[str, Any]:
    entities = c.get_json(f"wiki/Special:EntityData/{qid}.json", f"entity-{qid}")["entities"]
    # A merged item redirects, so the returned key can differ from the requested one.
    return entities.get(qid) or next(iter(entities.values()))


def fetch_entities(qids: list[str], c: CachedClient) -> dict[str, dict[str, Any]]:
    """Labels (Icelandic and English) and claims for many items, 50 per request."""
    result: dict[str, dict[str, Any]] = {}
    ids = sorted(set(qids))
    for start in range(0, len(ids), 50):
        chunk = ids[start:start + 50]
        key = "entities-" + hashlib.sha1("|".join(chunk).encode()).hexdigest()[:12]
        data = c.get_json("w/api.php", key, {
            "action": "wbgetentities", "ids": "|".join(chunk),
            "props": "labels|claims", "languages": "is|en", "format": "json",
        })
        result.update(data["entities"])
    return result


def _values(entity: dict[str, Any], prop: str) -> list[Any]:
    return [
        claim["mainsnak"]["datavalue"]["value"]
        for claim in entity.get("claims", {}).get(prop, [])
        if claim["mainsnak"].get("datavalue")
    ]


def claim_ids(entity: dict[str, Any], prop: str) -> list[str]:
    return [v["id"] for v in _values(entity, prop) if isinstance(v, dict) and "id" in v]


def claim_strings(entity: dict[str, Any], prop: str) -> list[str]:
    """String values, such as the Commons file name of an image (P18)."""
    return [v for v in _values(entity, prop) if isinstance(v, str)]


def claim_time(entity: dict[str, Any], prop: str) -> tuple[str, int] | None:
    """First time value as (YYYY-MM-DD, precision); unknown month or day is padded with 01."""
    for value in _values(entity, prop):
        if isinstance(value, dict) and "time" in value:
            precision = min(value["precision"], DAY_PRECISION)
            year, month, day = value["time"][1:11].split("-")
            month = month if precision >= MONTH_PRECISION and month != "00" else "01"
            day = day if precision >= DAY_PRECISION and day != "00" else "01"
            return f"{year}-{month}-{day}", precision
    return None


def label(entity: dict[str, Any] | None, language: str) -> str | None:
    return ((entity or {}).get("labels", {}).get(language) or {}).get("value")


def coordinates(entity: dict[str, Any] | None) -> tuple[float, float] | None:
    value = next((v for v in _values(entity or {}, "P625") if isinstance(v, dict)), None)
    return (value["latitude"], value["longitude"]) if value else None


def enwiki_title(entity: dict[str, Any]) -> str | None:
    return entity.get("sitelinks", {}).get("enwiki", {}).get("title")


def publication_date(entity: dict[str, Any]) -> str | None:
    """Earliest publication date (P577) given to the day, as YYYY-MM-DD."""
    dates = []
    for claim in entity.get("claims", {}).get("P577", []):
        value = claim["mainsnak"].get("datavalue", {}).get("value", {})
        if value.get("precision") == DAY_PRECISION:
            dates.append(value["time"][1:11])
    return min(dates) if dates else None


def person_rows(person: dict[str, Any], c: CachedClient) -> dict[str, list[dict[str, Any]]]:
    """Bundle rows for a person: tags, places with coordinates, and life/career events."""
    wanted = [q for prop in (*TAG_PROPERTIES.values(), *PLACE_PROPERTIES.values()) for q in claim_ids(person, prop)]
    related = fetch_entities(wanted, c)
    source = "wikidata-artist"

    tags = [
        {"kind": kind, "qid": q, "label_is": label(related.get(q), "is"),
         "label_en": label(related.get(q), "en"), "source_key": source}
        for kind, prop in TAG_PROPERTIES.items()
        for q in claim_ids(person, prop)
    ]
    places = []
    for role, prop in PLACE_PROPERTIES.items():
        for q in claim_ids(person, prop):
            point = coordinates(related.get(q))
            if point:
                places.append({
                    "role": role, "qid": q, "title": label(related.get(q), "en") or q,
                    "label_is": label(related.get(q), "is"), "latitude": point[0], "longitude": point[1],
                    "context": None, "source_key": source,
                })
    events = []
    for kind, prop in EVENT_PROPERTIES.items():
        when = claim_time(person, prop)
        if when:
            events.append({
                "event_date": when[0], "date_precision": when[1], "kind": kind,
                "label": kind, "detail": None, "url": None, "source_key": source,
            })
    return {"artist_tags": tags, "places": places, "events": events}


def source_row(c: CachedClient, qid: str, what: str, key: str = "wikidata-album") -> dict[str, Any]:
    return {
        "source_key": key,
        "source_name": "Wikidata",
        "source_type": "database",
        "source_url": f"https://www.wikidata.org/wiki/{qid}",
        "retrieved_at": c.retrieved_at(f"entity-{qid}"),
        "citation_text": f"Wikidata {qid}: {what}",
    }

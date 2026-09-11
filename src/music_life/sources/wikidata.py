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
# Types that end the "located in" (P131) walk: country, sovereign state, country of the United Kingdom.
COUNTRY_TYPES = {"Q6256", "Q3624078", "Q3336843"}
DIVORCE = "Q93190"


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


def _time(value: Any) -> tuple[str, int] | None:
    """A Wikidata time value as (YYYY-MM-DD, precision); unknown month or day is padded with 01."""
    if not (isinstance(value, dict) and "time" in value):
        return None
    precision = min(value["precision"], DAY_PRECISION)
    year, month, day = value["time"][1:11].split("-")
    month = month if precision >= MONTH_PRECISION and month != "00" else "01"
    day = day if precision >= DAY_PRECISION and day != "00" else "01"
    return f"{year}-{month}-{day}", precision


def claim_time(entity: dict[str, Any], prop: str) -> tuple[str, int] | None:
    return next((t for t in map(_time, _values(entity, prop)) if t), None)


def _qualifiers(claim: dict[str, Any], prop: str) -> list[Any]:
    return [q["datavalue"]["value"] for q in claim.get("qualifiers", {}).get(prop, []) if q.get("datavalue")]


def _entity(qid: str, c: CachedClient) -> dict[str, Any] | None:
    entities = fetch_entities([qid], c)
    return entities.get(qid) or next(iter(entities.values()), None)


def country_of(qid: str, c: CachedClient, max_steps: int = 10) -> dict[str, Any] | None:
    """The country (or UK constituent country) a place lies in, following "located in" (P131).
    Returns None when the place is itself a country."""
    current = qid
    for step in range(max_steps):
        entity = _entity(current, c)
        if entity is None:
            return None
        if set(claim_ids(entity, "P31")) & COUNTRY_TYPES:
            return entity if step else None
        parents = claim_ids(entity, "P131")
        if not parents:
            countries = claim_ids(entity, "P17")
            return _entity(countries[0], c) if countries else None
        current = parents[0]
    return None


def best_label(entity: dict[str, Any] | None) -> str | None:
    return label(entity, "is") or label(entity, "en")


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
    """Bundle rows for a person: tags (including sex), places with their country, and life,
    family and career events. The cause of death goes in the death event's detail."""
    props = (*TAG_PROPERTIES.values(), *PLACE_PROPERTIES.values(), "P21", "P26", "P40", "P509")
    related = fetch_entities([q for prop in props for q in claim_ids(person, prop)], c)
    source = "wikidata-artist"

    def event(when: tuple[str, int], kind: str, text: str, detail: str | None = None) -> dict[str, Any]:
        return {"event_date": when[0], "date_precision": when[1], "kind": kind, "label": text,
                "detail": detail, "url": None, "source_key": source}

    tags = [
        {"kind": kind, "qid": q, "label_is": label(related.get(q), "is"),
         "label_en": label(related.get(q), "en"), "source_key": source}
        for kind, prop in (*TAG_PROPERTIES.items(), ("sex", "P21"))
        for q in claim_ids(person, prop)
    ]
    places = []
    for role, prop in PLACE_PROPERTIES.items():
        for q in claim_ids(person, prop):
            point = coordinates(related.get(q))
            if point:
                places.append({
                    "role": role, "qid": q, "title": label(related.get(q), "en") or q,
                    "label_is": label(related.get(q), "is"), "country": best_label(country_of(q, c)),
                    "latitude": point[0], "longitude": point[1], "context": None, "source_key": source,
                })

    causes = ", ".join(filter(None, (best_label(related.get(q)) for q in claim_ids(person, "P509")))) or None
    events = []
    for kind, prop in EVENT_PROPERTIES.items():
        when = claim_time(person, prop)
        if when:
            events.append(event(when, kind, kind, causes if kind == "death" else None))
    for claim in person.get("claims", {}).get("P26", []):
        spouse = (claim["mainsnak"].get("datavalue") or {}).get("value", {}).get("id")
        name = best_label(related.get(spouse)) or spouse
        start = next(filter(None, map(_time, _qualifiers(claim, "P580"))), None)
        if start:
            events.append(event(start, "marriage", name))
        ended_by_divorce = DIVORCE in {v.get("id") for v in _qualifiers(claim, "P1534") if isinstance(v, dict)}
        end = next(filter(None, map(_time, _qualifiers(claim, "P582"))), None)
        if end and ended_by_divorce:
            events.append(event(end, "divorce", name))
    for q in claim_ids(person, "P40"):
        when = claim_time(related.get(q) or {}, "P569")
        if when:
            events.append(event(when, "child", best_label(related.get(q)) or q))
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

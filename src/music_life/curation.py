"""Hand-curated additions to a bundle, kept in data/curated/<artist>/<album>/manual.yml.

Every entry needs a ``source`` URL. Places are given as Wikidata items; their coordinates and
labels come from Wikidata when the bundle is collected. Example:

    places:
      - qid: Q27
        role: residence
        context: "In 2008, Rafferty moved away from California and briefly rented a home in Ireland."
        source: https://en.wikipedia.org/wiki/Gerry_Rafferty
    events:
      - date: 1992-09-18        # or 1998, or 1998-01
        kind: cover
        label: "Undercover – Baker Street"
        url: https://open.spotify.com/track/2DTQUOfYJAjdo7utgjnU4u
        source: https://en.wikipedia.org/wiki/Baker_Street_(song)
"""
from __future__ import annotations

from datetime import date
from pathlib import Path
from typing import Any

import yaml

from .sources import wikidata
from .sources.http import CachedClient


def parse_date(value: Any) -> tuple[str, int]:
    """A YAML date, year or year-month as (YYYY-MM-DD, Wikidata-style precision)."""
    if isinstance(value, date):
        return value.isoformat(), wikidata.DAY_PRECISION
    parts = str(value).split("-")
    precision = {1: wikidata.YEAR_PRECISION, 2: wikidata.MONTH_PRECISION, 3: wikidata.DAY_PRECISION}[len(parts)]
    return "-".join(parts + ["01"] * (3 - len(parts))), precision


def load_manual(path: Path, wd: CachedClient) -> dict[str, list[dict[str, Any]]]:
    """Bundle rows (places, events, samples, sources) from a manual.yml; empty when it is missing."""
    empty: dict[str, list[dict[str, Any]]] = {"places": [], "events": [], "samples": [], "sources": []}
    if not path.exists():
        return empty
    spec = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    urls: list[str] = []

    def source_key(url: str) -> str:
        if url not in urls:
            urls.append(url)
        return f"manual-{urls.index(url) + 1}"

    samples = [
        {"disc": entry.get("disc", 1), "track": entry["track"], "url": entry["url"],
         "page": entry["source"], "source_key": source_key(entry["source"])}
        for entry in spec.get("samples", [])
    ]

    events = []
    for entry in spec.get("events", []):
        when, precision = parse_date(entry["date"])
        events.append({
            "event_date": when, "date_precision": precision, "kind": entry["kind"],
            "label": entry["label"], "detail": entry.get("detail"), "url": entry.get("url"),
            "source_key": source_key(entry["source"]),
        })

    entries = spec.get("places", [])
    items = wikidata.fetch_entities([p["qid"] for p in entries], wd) if entries else {}
    places = []
    for entry in entries:
        item = items.get(entry["qid"])
        point = wikidata.coordinates(item)
        if point is None:
            raise ValueError(f"{path}: Wikidata item {entry['qid']} has no coordinates")
        places.append({
            "role": entry.get("role", "mentioned"), "qid": entry["qid"],
            "title": wikidata.label(item, "en") or entry["qid"], "label_is": wikidata.label(item, "is"),
            "country": wikidata.best_label(wikidata.country_of(entry["qid"], wd)),
            "latitude": point[0], "longitude": point[1], "context": entry.get("context"),
            "source_key": source_key(entry["source"]),
        })

    # No retrieval time: it would change whenever git touches the file.
    sources = [
        {"source_key": f"manual-{i}", "source_name": "Manual curation", "source_type": "manual",
         "source_url": url, "retrieved_at": None, "citation_text": f"Curated in {path.name}"}
        for i, url in enumerate(urls, start=1)
    ]
    return {"places": places, "events": events, "samples": samples, "sources": sources}

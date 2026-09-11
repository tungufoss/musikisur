"""MusicBrainz: canonical artists, release groups, releases, recordings, works and credits.

The album is a release group; its track list comes from one chosen release (edition), set as
``musicbrainz_release`` in config/focus-albums.yml. Recordings and works stay distinct:
performance and production credits attach to recordings, songwriting credits to works.
API rules: https://musicbrainz.org/doc/MusicBrainz_API (one request per second).
"""
from __future__ import annotations

import re
from collections.abc import Iterator
from typing import Any

import pandas as pd

from ..bundles import TABLES
from .http import CachedClient

BASE_URL = "https://musicbrainz.org/ws/2"
RELEASE_INC = (
    "recordings+artist-credits+labels+isrcs"
    "+recording-level-rels+work-rels+artist-rels+work-level-rels"
)
FULL_DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
# Relationship types whose attributes name an instrument or voice (played, sung or arranged)
# rather than qualify the role, as "co" does in "co producer".
INSTRUMENT_TYPES = {"instrument", "vocal", "instrument arranger", "vocal arranger"}


def client() -> CachedClient:
    return CachedClient("musicbrainz", BASE_URL, min_interval=1.1)


def _get(c: CachedClient, entity: str, mbid: str, inc: str) -> dict[str, Any]:
    return c.get_json(f"{entity}/{mbid}", f"{entity}-{mbid}", {"inc": inc, "fmt": "json"})


def fetch_artist(mbid: str, c: CachedClient) -> dict[str, Any]:
    return _get(c, "artist", mbid, "url-rels+aliases")


def fetch_release_group(mbid: str, c: CachedClient) -> dict[str, Any]:
    return _get(c, "release-group", mbid, "url-rels+artist-credits")


def fetch_release(mbid: str, c: CachedClient) -> dict[str, Any]:
    return _get(c, "release", mbid, RELEASE_INC)


def source_row(c: CachedClient, entity: str, mbid: str, citation: str) -> dict[str, Any]:
    return {
        "source_key": f"musicbrainz-{entity}",
        "source_name": "MusicBrainz",
        "source_type": "database",
        "source_url": f"https://musicbrainz.org/{entity}/{mbid}",
        "retrieved_at": c.retrieved_at(f"{entity}-{mbid}"),
        "citation_text": citation,
    }


def full_date(value: Any) -> str | None:
    """MusicBrainz dates may be partial ("1978"); only full dates fit a DATE column."""
    return value if isinstance(value, str) and FULL_DATE.match(value) else None


def _url_id(relations: list[dict[str, Any]] | None, fragment: str) -> str | None:
    for rel in relations or []:
        url = (rel.get("url") or {}).get("resource", "")
        if fragment in url:
            return url.rstrip("/").rsplit("/", 1)[-1]
    return None


def wikidata_id(entity: dict[str, Any]) -> str | None:
    """The Wikidata item linked from a MusicBrainz artist, release group or release."""
    return _url_id(entity.get("relations"), "wikidata.org")


def _frame(table: str, rows: list[dict[str, Any]]) -> pd.DataFrame:
    """Rows in the bundle's column order; unfilled columns hold None so later steps can fill them."""
    frame = pd.DataFrame(rows).reindex(columns=list(TABLES[table].columns)).astype(object)
    return frame.where(frame.notna(), None)


def _tracks(release: dict[str, Any]) -> Iterator[tuple[int, int, dict[str, Any]]]:
    for medium in release.get("media", []):
        for track in medium.get("tracks", []):
            yield int(medium["position"]), int(track["position"]), track


def _work(recording: dict[str, Any]) -> dict[str, Any] | None:
    return next(
        (rel["work"] for rel in recording.get("relations", []) if rel.get("target-type") == "work"),
        None,
    )


def artist_frame(artist: dict[str, Any], slug: str) -> pd.DataFrame:
    relations = artist.get("relations", [])
    life = artist.get("life-span") or {}
    return _frame("artist", [{
        "slug": slug,
        "name": artist["name"],
        "sort_name": artist.get("sort-name"),
        "birth_date": full_date(life.get("begin")),
        "death_date": full_date(life.get("end")),
        "birth_place": (artist.get("begin-area") or {}).get("name"),
        "musicbrainz_id": artist["id"],
        "wikidata_id": _url_id(relations, "wikidata.org"),
        "discogs_id": _url_id(relations, "discogs.com/artist"),
        "spotify_id": _url_id(relations, "open.spotify.com/artist"),
        "source_key": "musicbrainz-artist",
    }])


def album_frame(release_group: dict[str, Any], slug: str) -> pd.DataFrame:
    return _frame("album", [{
        "slug": slug,
        "title": release_group["title"],
        "original_release_date": full_date(release_group.get("first-release-date")),
        "album_type": (release_group.get("primary-type") or "").lower() or None,
        "musicbrainz_release_group_id": release_group["id"],
        "discogs_master_id": _url_id(release_group.get("relations"), "discogs.com/master"),
        "source_key": "musicbrainz-release-group",
    }])


def track_isrcs(release: dict[str, Any]) -> dict[tuple[int, int], list[str]]:
    return {
        (disc, number): sorted(track["recording"].get("isrcs", []))
        for disc, number, track in _tracks(release)
    }


def tracks_frame(release: dict[str, Any]) -> pd.DataFrame:
    rows = []
    for disc, number, track in _tracks(release):
        recording = track["recording"]
        work = _work(recording)
        isrcs = sorted(recording.get("isrcs", []))
        rows.append({
            "disc_number": disc,
            "track_number": number,
            "track_title": track["title"],
            "recording_title": recording["title"],
            "duration_ms": track.get("length") or recording.get("length"),
            "isrc": isrcs[0] if isrcs else None,
            "musicbrainz_recording_id": recording["id"],
            "musicbrainz_work_id": work["id"] if work else None,
            "source_key": "musicbrainz-release",
        })
    return _frame("tracks", rows)


def _credit(rel: dict[str, Any], disc: int | None, number: int | None, applies_to: str) -> dict[str, Any]:
    attributes = list(rel.get("attributes", []))
    is_instrument = rel["type"] in INSTRUMENT_TYPES
    return {
        "disc_number": disc,
        "track_number": number,
        "applies_to": applies_to,
        "person_name": rel["artist"]["name"],
        "role": rel["type"] if is_instrument else " ".join([*attributes, rel["type"]]),
        "instrument": ", ".join(attributes) if is_instrument and attributes else None,
        "credited_as": rel.get("target-credit") or None,
        "musicbrainz_artist_id": rel["artist"]["id"],
        "source_key": "musicbrainz-release",
    }


def credits_frame(release: dict[str, Any]) -> pd.DataFrame:
    def artist_rels(entity: dict[str, Any]) -> list[dict[str, Any]]:
        return [rel for rel in entity.get("relations", []) if rel.get("target-type") == "artist"]

    rows = [_credit(rel, None, None, "album") for rel in artist_rels(release)]
    for disc, number, track in _tracks(release):
        recording = track["recording"]
        rows += [_credit(rel, disc, number, "recording") for rel in artist_rels(recording)]
        work = _work(recording)
        if work:
            rows += [_credit(rel, disc, number, "work") for rel in artist_rels(work)]
    return _frame("credits", rows).drop_duplicates(ignore_index=True)

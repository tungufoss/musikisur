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
from ..normalize import normalize_text
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


def fetch_release_groups(artist_mbid: str, c: CachedClient) -> dict[str, Any]:
    """The artist's album release groups (up to 100; enough for one artist's albums)."""
    return c.get_json(
        "release-group", f"release-groups-{artist_mbid}",
        {"artist": artist_mbid, "type": "album", "fmt": "json", "limit": 100},
    )


def fetch_release_groups_of_type(artist_mbid: str, types: str, c: CachedClient) -> dict[str, Any]:
    """Release groups of the given type(s), e.g. "single" or "album|single"."""
    return c.get_json(
        "release-group", f"release-groups-{types.replace('|', '-')}-{artist_mbid}",
        {"artist": artist_mbid, "type": types, "fmt": "json", "limit": 100},
    )


def fetch_artist_relations(artist_mbid: str, c: CachedClient) -> dict[str, Any]:
    return c.get_json(
        f"artist/{artist_mbid}", f"artist-rels-{artist_mbid}",
        {"inc": "release-group-rels+release-rels+recording-rels+artist-rels", "fmt": "json"},
    )


def fetch_recording(mbid: str, c: CachedClient) -> dict[str, Any]:
    return c.get_json(f"recording/{mbid}", f"recording-{mbid}", {"inc": "artist-credits+releases", "fmt": "json"})


def _dated(value: str) -> tuple[str, int] | None:
    """A MusicBrainz date ("1978", "1978-01", "1978-01-20") as (YYYY-MM-DD, precision)."""
    if not value:
        return None
    parts = value.split("-")
    return "-".join(parts + ["01"] * (3 - len(parts))), {1: 9, 2: 10, 3: 11}[len(parts)]


def release_events(
    release_groups: dict[str, Any], kind: str, source_key: str, detail: str | None = None
) -> list[dict[str, Any]]:
    """Dated release groups without a secondary type (compilation, live ...) as timeline events."""
    rows = []
    for group in release_groups.get("release-groups", []):
        when = _dated(group.get("first-release-date") or "")
        if group.get("secondary-types") or when is None:
            continue
        rows.append({
            "event_date": when[0], "date_precision": when[1], "kind": kind, "label": group["title"],
            "detail": detail or group["id"], "url": f"https://musicbrainz.org/release-group/{group['id']}",
            "source_key": source_key,
        })
    return rows


def album_events(release_groups: dict[str, Any]) -> list[dict[str, Any]]:
    """Studio albums as timeline events; detail holds the release group ID."""
    return release_events(release_groups, "album", "musicbrainz-release-groups")


def bands(relations: dict[str, Any]) -> list[dict[str, Any]]:
    """Groups the artist was a member of."""
    found = {}
    for rel in relations.get("relations", []):
        if rel["type"] == "member of band" and rel.get("target-type") == "artist" and rel.get("direction") == "forward":
            found[rel["artist"]["id"]] = rel["artist"]
    return list(found.values())


# Parenthetical notes that mark another take of the same song, e.g. "(original demo)".
VERSION_NOTE = re.compile(
    r"\s*[(\[][^)\]]*\b(demo|live|remaster\w*|mix|version|edit|mono|stereo|take|instrumental)\b[^)\]]*[)\]]",
    re.IGNORECASE,
)


def fetch_recordings(artist_mbid: str, c: CachedClient) -> list[dict[str, Any]]:
    """Every recording credited to the artist, 100 per page."""
    recordings: list[dict[str, Any]] = []
    offset = 0
    while True:
        page = c.get_json(
            "recording", f"recordings-{artist_mbid}-{offset}",
            {"artist": artist_mbid, "limit": 100, "offset": offset, "fmt": "json"},
        )
        recordings += page.get("recordings", [])
        offset += 100
        if offset >= page.get("recording-count", 0):
            return recordings


def song_events(recordings: list[dict[str, Any]], group: str, source_key: str) -> list[dict[str, Any]]:
    """One event per distinct song, dated by its earliest released recording, so live takes,
    demos, remasters and compilation reissues of the same song count once."""
    first: dict[str, tuple[str, dict[str, Any]]] = {}
    for recording in recordings:
        date = recording.get("first-release-date") or ""
        if not date or recording.get("video"):
            continue
        key = normalize_text(VERSION_NOTE.sub("", recording["title"]))
        if key and (key not in first or date < first[key][0]):
            first[key] = (date, recording)
    rows = []
    for date, recording in first.values():
        when = _dated(date)
        rows.append({
            "event_date": when[0], "date_precision": when[1], "kind": "song",
            "label": VERSION_NOTE.sub("", recording["title"]).strip(), "detail": group,
            "url": f"https://musicbrainz.org/recording/{recording['id']}", "source_key": source_key,
        })
    return rows


# Recording relationships that put the artist behind or beside someone else's record.
OTHERS_KINDS = {
    "producer": "production", "mix": "production", "arranger": "production", "instrument arranger": "production",
    "vocal": "guest", "instrument": "guest", "performer": "guest",
}


def credits_for_others(relations: dict[str, Any], own_ids: set[str], c: CachedClient) -> list[dict[str, Any]]:
    """Recordings by other artists that credit this artist, dated by their first release."""
    rows = []
    for rel in relations.get("relations", []):
        kind = OTHERS_KINDS.get(rel["type"])
        if rel.get("target-type") != "recording" or kind is None:
            continue
        recording = fetch_recording(rel["recording"]["id"], c)
        credited = {credit["artist"]["id"] for credit in recording.get("artist-credit", [])}
        dates = sorted(r["date"] for r in recording.get("releases", []) if r.get("date"))
        when = _dated(dates[0]) if dates else None
        if credited & own_ids or when is None:
            continue
        who = "".join(credit["name"] + credit.get("joinphrase", "") for credit in recording["artist-credit"])
        rows.append({
            "event_date": when[0], "date_precision": when[1], "kind": kind,
            "label": f"{who} – {recording['title']}", "detail": rel["type"],
            "url": f"https://musicbrainz.org/recording/{recording['id']}",
            "source_key": "musicbrainz-artist-relations",
        })
    return rows


def cached_source_row(c: CachedClient, cache_key: str, source_key: str, url: str, citation: str) -> dict[str, Any]:
    return {
        "source_key": source_key,
        "source_name": "MusicBrainz",
        "source_type": "database",
        "source_url": url,
        "retrieved_at": c.retrieved_at(cache_key),
        "citation_text": citation,
    }


def release_groups_source_row(c: CachedClient, artist_mbid: str, name: str) -> dict[str, Any]:
    return cached_source_row(
        c, f"release-groups-{artist_mbid}", "musicbrainz-release-groups",
        f"https://musicbrainz.org/artist/{artist_mbid}/releases", f"MusicBrainz albums by {name}",
    )


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

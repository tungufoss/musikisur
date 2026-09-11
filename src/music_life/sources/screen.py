"""Film and TV uses of an artist's songs: IMDb soundtrack credits, ranked with TMDB.

IMDb has no open API and does not allow automated collection, so the credits come from a
hand export (see scripts/screen_credits.py). TMDB adds what the export lacks for ranking:
how many people rated each title (vote_count), found by its IMDb id.
"""
from __future__ import annotations

import re
from collections.abc import Callable
from typing import Any

from .http import CachedClient, require_env
from .musicbrainz import song_key

TV_TYPES = {"TV Series", "TV Mini Series"}
MOVIE_TYPES = {"Movie", "TV Movie"}


def tmdb_client() -> CachedClient:
    return CachedClient(
        "tmdb", "https://api.themoviedb.org/3",
        headers_factory=lambda: {"Authorization": f"Bearer {require_env('TMDB_API_TOKEN')}"},
        min_interval=0.05,
    )


def find_by_imdb_id(imdb_id: str, c: CachedClient) -> dict[str, Any] | None:
    """TMDB's movie or TV entry for an IMDb id as {"type", "id", "votes"}, or None."""
    found = c.get_json(f"find/{imdb_id}", f"find-{imdb_id}", {"external_source": "imdb_id"})
    for key, kind in (("movie_results", "movie"), ("tv_results", "tv")):
        if found.get(key):
            hit = found[key][0]
            return {"type": kind, "id": hit["id"], "votes": hit.get("vote_count") or 0}
    return None


def kind_of(imdb_type: str) -> str:
    """tv (series, mini-series), movie (incl. TV movies) or other (shorts, videos, podcasts)."""
    return "tv" if imdb_type in TV_TYPES else "movie" if imdb_type in MOVIE_TYPES else "other"


def year_span(years: str) -> tuple[int, int]:
    """'1995–2026' -> (1995, 2026); '2011' -> (2011, 2011)."""
    found = [int(y) for y in re.findall(r"\d{4}", years)]
    return found[0], found[-1]


def canonical_song(title: str, known: list[str]) -> str:
    """The artist's own spelling of a song IMDb names; IMDb often shortens titles
    ("Stuck in the Middle" for "Stuck in the Middle With You")."""
    keys = {song_key(k): k for k in known}
    key = song_key(title)
    if key in keys:
        return keys[key]
    longer = sorted(k for k in keys if k.startswith(key + " "))
    return keys[longer[0]] if longer else title


def song_links(
    songs: list[str], performers: list[str],
    search: Callable[[str, str], tuple[dict[str, Any] | None, str]],
    owners: dict[str, str] | None = None,
) -> list[dict[str, Any]]:
    """A Spotify link per song, from the first performer with a match. ``owners`` (song -> who
    released it first) puts that performer first, so a band's original beats a later solo
    re-recording; otherwise the order of ``performers``. ``search(performer, song)`` returns
    (match, cache key), like spotify.search."""
    owner_of = {song_key(song): who for song, who in (owners or {}).items()}
    rows = []
    for song in songs:
        first = owner_of.get(song_key(song))
        for performer in [first, *(p for p in performers if p != first)] if first else performers:
            match, key = search(performer, song)
            if match:
                artists = ", ".join(a["name"] for a in match["artists"])
                released = (match.get("album") or match)["release_date"]
                rows.append({"song": song, "spotify_url": match["external_urls"]["spotify"],
                             "spotify_name": f"{artists} – {match['name']} ({released})", "cache_key": key})
                break
    return rows


def credit_rows(
    export: dict[str, Any], known_songs: list[str], lookup: Callable[[str], dict[str, Any] | None]
) -> list[dict[str, Any]]:
    """One row per title: the IMDb credit plus TMDB's vote count (``lookup`` maps an IMDb id to
    find_by_imdb_id's result)."""
    rows = []
    for credit in export["credits"]:
        first, last = year_span(credit["years"])
        songs = {song_key(s): s for s in (canonical_song(t, known_songs) for t in credit["songs"])}
        tmdb = lookup(credit["id"])
        rows.append({
            "imdb_id": credit["id"], "title": credit["title"], "kind": kind_of(credit["type"]),
            "imdb_type": credit["type"], "first_year": first, "last_year": last,
            "episodes": credit.get("episodes"), "songs": "; ".join(sorted(songs.values(), key=str.lower)),
            "imdb_rating": credit.get("rating"),
            "tmdb_votes": tmdb["votes"] if tmdb else None,
            "tmdb_url": f"https://www.themoviedb.org/{tmdb['type']}/{tmdb['id']}" if tmdb else None,
            "retrieved_at": export.get("retrieved_at"),
        })
    return rows

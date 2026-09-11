"""Spotify enrichment: current album and track links, matched to MusicBrainz recordings.

Spotify is not a historical authority. A track counts as verified only when its Spotify ISRC
equals one of the MusicBrainz recording's ISRCs. A same-position, same-title match is kept but
left unverified, because Spotify often serves a later remaster or re-recording.
"""
from __future__ import annotations

import re
from typing import Any

import httpx
import pandas as pd

from ..normalize import normalize_text
from .http import CachedClient, require_env

TOKEN_URL = "https://accounts.spotify.com/api/token"
BASE_URL = "https://api.spotify.com/v1"
VERSION_SUFFIX = re.compile(r"\s+-\s+.*\b(remaster\w*|live|version|edit|mono|stereo|mix)\b.*$", re.IGNORECASE)


def _auth_headers() -> dict[str, str]:
    response = httpx.post(
        TOKEN_URL,
        data={"grant_type": "client_credentials"},
        auth=(require_env("SPOTIFY_CLIENT_ID"), require_env("SPOTIFY_CLIENT_SECRET")),
        timeout=30.0,
    )
    response.raise_for_status()
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def client() -> CachedClient:
    return CachedClient("spotify", BASE_URL, headers_factory=_auth_headers, min_interval=0.2)


def fetch_album(album_id: str, c: CachedClient) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    """The album plus full track objects (album track listings omit ISRCs)."""
    album = c.get_json(f"albums/{album_id}", f"album-{album_id}")
    tracks = [c.get_json(f"tracks/{item['id']}", f"track-{item['id']}") for item in album["tracks"]["items"]]
    return album, tracks


def source_row(c: CachedClient, album: dict[str, Any]) -> dict[str, Any]:
    return {
        "source_key": "spotify-album",
        "source_name": "Spotify",
        "source_type": "streaming",
        "source_url": album["external_urls"]["spotify"],
        "retrieved_at": c.retrieved_at(f"album-{album['id']}"),
        "citation_text": f"Spotify Web API album: {album['name']}",
    }


def clean_title(title: str) -> str:
    return normalize_text(VERSION_SUFFIX.sub("", title))


BRACKETS = re.compile(r"\s*[\(\[][^\)\]]*[\)\]]")
ARTIST_SEPARATORS = re.compile(r"\s+(?:featuring|feat\.|with|&|and|x)\s+", re.IGNORECASE)
# Chart performers that name no artist; any Spotify artist is accepted for them.
COMPILATION_ARTISTS = {"soundtrack", "original soundtrack", "original cast", "original cast recording", "various artists"}


def core_title(title: str) -> str:
    """Title without version notes: 'Some Girls (Remastered 2009)' and 'Some Girls' agree."""
    return clean_title(BRACKETS.sub("", title))


def best_match(items: list[dict[str, Any] | None], artist: str, title: str) -> dict[str, Any] | None:
    """The earliest Spotify album or track whose title and artist match a chart entry, or None.

    Chart performers often add a band ("Bob Seger & The Silver Bullet Band"), so an artist
    matches when either name contains the other.
    """
    wanted = core_title(title)
    performer = normalize_text(artist)

    def artist_matches(item: dict[str, Any]) -> bool:
        if performer in COMPILATION_ARTISTS:
            # Any artist, but the release must present itself as a soundtrack or compilation,
            # otherwise a cover album with the same title wins.
            name = normalize_text(item["name"])
            return item.get("album_type") == "compilation" or any(
                word in name for word in ("soundtrack", "sound track", "motion picture", "original cast")
            )
        names = (normalize_text(a["name"]) for a in item["artists"])
        return any(name and (name in performer or performer in name) for name in names)

    matches = [item for item in items if item and core_title(item["name"]) == wanted and artist_matches(item)]
    return min(matches, key=lambda item: (item.get("album") or item)["release_date"], default=None)


def search(c: CachedClient, artist: str, title: str, kind: str) -> tuple[dict[str, Any] | None, str]:
    """Search Spotify for a chart entry (kind 'album' or 'track'); returns the match and its cache key."""
    query = f'{kind}:"{title}"'
    if normalize_text(artist) not in COMPILATION_ARTISTS:
        query += f' artist:"{ARTIST_SEPARATORS.split(artist)[0]}"'
    key = f"search-{kind}-" + re.sub(r"[^a-z0-9]+", "-", f"{artist} {title}".lower()).strip("-")
    result = c.get_json("search", key, {"q": query, "type": kind, "limit": 10})
    return best_match(result[f"{kind}s"]["items"], artist, title), key


def enrich(
    tables: dict[str, pd.DataFrame],
    album: dict[str, Any],
    tracks: list[dict[str, Any]],
    isrcs: dict[tuple[int, int], list[str]],
) -> int:
    """Add Spotify links to the album, artist and track tables in place.

    Returns the number of tracks verified by ISRC.
    """
    tables["album"].loc[0, ["spotify_album_id", "spotify_url", "spotify_uri"]] = [
        album["id"], album["external_urls"]["spotify"], album["uri"],
    ]
    artist = tables["artist"]
    if pd.isna(artist.loc[0, "spotify_id"]) and album.get("artists"):
        first = album["artists"][0]
        if normalize_text(first["name"]) == normalize_text(artist.loc[0, "name"]):
            artist.loc[0, "spotify_id"] = first["id"]

    by_isrc = {
        t["external_ids"]["isrc"].upper(): t for t in tracks if t.get("external_ids", {}).get("isrc")
    }
    by_position = {(t["disc_number"], t["track_number"]): t for t in tracks}
    frame = tables["tracks"]
    verified = 0
    for i, row in frame.iterrows():
        key = (int(row["disc_number"]), int(row["track_number"]))
        match = next((by_isrc[code.upper()] for code in isrcs.get(key, []) if code.upper() in by_isrc), None)
        is_verified = match is not None
        if match is None:
            candidate = by_position.get(key)
            if candidate and clean_title(candidate["name"]) == clean_title(row["track_title"]):
                match = candidate
        if match is None:
            continue
        frame.loc[i, ["spotify_track_id", "spotify_url", "spotify_verified"]] = [
            match["id"], match["external_urls"]["spotify"], is_verified,
        ]
        if is_verified:
            frame.loc[i, "isrc"] = match["external_ids"]["isrc"]
            verified += 1
    return verified

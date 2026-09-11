"""Collect one focus album's data bundle from MusicBrainz, Discogs, Spotify and Cover Art Archive.

    python scripts/collect_album.py gerry-rafferty city-to-city

Identifiers come from config/artists.yml and config/focus-albums.yml. Raw API responses are
cached in data/raw/<source>/, so a re-run works offline and writes an identical bundle.
"""
import argparse
from typing import Any

import pandas as pd
import yaml

from music_life.bundles import write_bundle
from music_life.dashboard import CONFIG_DIR, COVERS_DIR
from music_life.sources import coverart, discogs, musicbrainz, spotify, wikidata


def config_entry(filename: str, key: str, slug: str) -> dict[str, Any]:
    entries = yaml.safe_load((CONFIG_DIR / filename).read_text(encoding="utf-8")).get(key) or []
    for entry in entries:
        if entry["slug"] == slug:
            return entry
    raise SystemExit(f"{slug!r} not found in config/{filename}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("artist", help="artist slug from config/artists.yml")
    parser.add_argument("album", help="album slug from config/focus-albums.yml")
    args = parser.parse_args()

    artist_config = config_entry("artists.yml", "artists", args.artist)
    album_config = config_entry("focus-albums.yml", "focus_albums", args.album)
    if album_config["artist"] != args.artist:
        raise SystemExit(f"{args.album!r} belongs to {album_config['artist']!r}, not {args.artist!r}")
    ids = album_config["identifiers"]

    mb = musicbrainz.client()
    artist = musicbrainz.fetch_artist(artist_config["identifiers"]["musicbrainz"], mb)
    release_group = musicbrainz.fetch_release_group(ids["musicbrainz_release_group"], mb)
    release = musicbrainz.fetch_release(ids["musicbrainz_release"], mb)
    tables = {
        "artist": musicbrainz.artist_frame(artist, args.artist),
        "album": musicbrainz.album_frame(release_group, args.album),
        "tracks": musicbrainz.tracks_frame(release),
        "credits": musicbrainz.credits_frame(release),
    }
    sources = [
        musicbrainz.source_row(mb, "artist", artist["id"], f"MusicBrainz artist: {artist['name']}"),
        musicbrainz.source_row(
            mb, "release-group", release_group["id"], f"MusicBrainz release group: {release_group['title']}"
        ),
        musicbrainz.source_row(
            mb, "release", release["id"],
            f"MusicBrainz release: {release['title']} ({release.get('country')}, {release.get('date')})",
        ),
    ]

    album_qid = musicbrainz.wikidata_id(release_group)
    if album_qid and tables["album"].loc[0, "original_release_date"] is None:
        wd = wikidata.client()
        published = wikidata.publication_date(wikidata.fetch_entity(album_qid, wd))
        if published:
            tables["album"].loc[0, "original_release_date"] = published
            sources.append(wikidata.source_row(wd, album_qid, release_group["title"]))

    if ids.get("discogs_master"):
        dc = discogs.client()
        master = discogs.fetch_master(ids["discogs_master"], dc)
        tables["album"].loc[0, "discogs_master_id"] = str(master["id"])
        sources.append(discogs.source_row(dc, master))

    verified = None
    if ids.get("spotify_album"):
        sp = spotify.client()
        album, tracks = spotify.fetch_album(ids["spotify_album"], sp)
        verified = spotify.enrich(tables, album, tracks, musicbrainz.track_isrcs(release))
        sources.append(spotify.source_row(sp, album))

    cover_path = COVERS_DIR / f"{args.album}.jpg"
    cover = coverart.download_front(cover_path, release["id"], release_group["id"])
    if cover:
        sources.append(coverart.source_row(cover_path, cover))

    tables["sources"] = pd.DataFrame(sources)
    path = write_bundle(args.artist, args.album, tables)

    track_count = len(tables["tracks"])
    minutes = tables["tracks"]["duration_ms"].sum() / 60000
    print(f"bundle: {path.relative_to(CONFIG_DIR.parent).as_posix()}")
    print(f"released: {tables['album'].loc[0, 'original_release_date'] or 'year only'}")
    print(f"tracks: {track_count} ({minutes:.0f} min), credits: {len(tables['credits'])}")
    if verified is not None:
        linked = tables["tracks"]["spotify_url"].notna().sum()
        print(f"spotify: {linked}/{track_count} linked, {verified} verified by ISRC")
    print(f"cover: {cover['bytes'] // 1024} KB from {cover['url']}" if cover else "cover: none found")


if __name__ == "__main__":
    main()

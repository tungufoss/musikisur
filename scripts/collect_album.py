"""Collect one focus album's data bundle from MusicBrainz, Wikidata, Wikipedia, Discogs, Spotify
and the Cover Art Archive, plus hand-curated entries from the bundle's manual.yml.

    python scripts/collect_album.py gerry-rafferty city-to-city

Identifiers come from config/artists.yml and config/focus-albums.yml. Raw API responses are
cached in data/raw/<source>/, so a re-run works offline and writes an identical bundle.
"""
import argparse
from typing import Any

import pandas as pd
import yaml

from music_life import curation
from music_life.bundles import bundle_dir, write_bundle
from music_life.dashboard import ARTISTS_DIR, CONFIG_DIR, COVERS_DIR
from music_life.sources import commons, coverart, discogs, musicbrainz, spotify, wikidata, wikipedia


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

    # The album: artist, release group, the chosen edition's tracks and credits.
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

    wd = wikidata.client()
    album_qid = musicbrainz.wikidata_id(release_group)
    if album_qid and tables["album"].loc[0, "original_release_date"] is None:
        published = wikidata.publication_date(wikidata.fetch_entity(album_qid, wd))
        if published:
            tables["album"].loc[0, "original_release_date"] = published
            sources.append(wikidata.source_row(wd, album_qid, f"publication date (P577) of {release_group['title']}"))

    # The artist: Wikidata facts, studio albums, places named in Wikipedia, manual.yml.
    context: dict[str, list[dict[str, Any]]] = {"artist_tags": [], "places": [], "events": []}
    artist_qid = artist_config["identifiers"].get("wikidata") or musicbrainz.wikidata_id(artist)
    if artist_qid:
        person = wikidata.fetch_entity(artist_qid, wd)
        for name, rows in wikidata.person_rows(person, wd).items():
            context[name] += rows
        sources.append(wikidata.source_row(wd, artist_qid, artist["name"], key="wikidata-artist"))
        title = wikidata.enwiki_title(person)
        if title:
            wp = wikipedia.client()
            context["places"] += wikipedia.place_rows(title, wp, {p["qid"] for p in context["places"]})
            sources.append(wikipedia.source_row(wp, title))
        photos = wikidata.claim_strings(person, "P18")
        if photos:
            cm = commons.client()
            info = commons.image_info(photos[0], cm)
            commons.download(info, ARTISTS_DIR / f"{args.artist}.jpg")
            sources.append(commons.source_row(cm, photos[0], info))

    # Output over time: studio albums, singles, band releases and credits on others' records.
    context["events"] += musicbrainz.album_events(musicbrainz.fetch_release_groups(artist["id"], mb))
    sources.append(musicbrainz.release_groups_source_row(mb, artist["id"], artist["name"]))
    singles = musicbrainz.fetch_release_groups_of_type(artist["id"], "single", mb)
    context["events"] += musicbrainz.release_events(singles, "single", "musicbrainz-singles")
    sources.append(musicbrainz.cached_source_row(
        mb, f"release-groups-single-{artist['id']}", "musicbrainz-singles",
        f"https://musicbrainz.org/artist/{artist['id']}/releases", f"MusicBrainz singles by {artist['name']}",
    ))
    relations = musicbrainz.fetch_artist_relations(artist["id"], mb)
    own_ids = {artist["id"]}
    for band in musicbrainz.bands(relations):
        own_ids.add(band["id"])
        key = f"musicbrainz-band-{band['id'][:8]}"
        groups = musicbrainz.fetch_release_groups_of_type(band["id"], "album|single", mb)
        context["events"] += musicbrainz.release_events(groups, "band_release", key, detail=band["name"])
        context["events"] += musicbrainz.song_events(musicbrainz.fetch_recordings(band["id"], mb), band["name"], key)
        sources.append(musicbrainz.cached_source_row(
            mb, f"release-groups-album-single-{band['id']}", key,
            f"https://musicbrainz.org/artist/{band['id']}", f"MusicBrainz releases by {band['name']}",
        ))
    context["events"] += musicbrainz.song_events(
        musicbrainz.fetch_recordings(artist["id"], mb), "solo", "musicbrainz-recordings"
    )
    sources.append(musicbrainz.cached_source_row(
        mb, f"recordings-{artist['id']}-0", "musicbrainz-recordings",
        f"https://musicbrainz.org/artist/{artist['id']}/recordings", f"MusicBrainz recordings by {artist['name']}",
    ))
    context["events"] += musicbrainz.credits_for_others(relations, own_ids, mb)
    sources.append(musicbrainz.cached_source_row(
        mb, f"artist-rels-{artist['id']}", "musicbrainz-artist-relations",
        f"https://musicbrainz.org/artist/{artist['id']}/relationships", f"MusicBrainz relationships of {artist['name']}",
    ))
    manual = curation.load_manual(bundle_dir(args.artist, args.album) / "manual.yml", wd)
    context["places"] += manual["places"]
    context["events"] += manual["events"]
    sources += manual["sources"]
    tracks = tables["tracks"]
    for sample in manual["samples"]:
        hit = (tracks["disc_number"] == sample["disc"]) & (tracks["track_number"] == sample["track"])
        tracks.loc[hit, ["sample_url", "sample_page"]] = [sample["url"], sample["page"]]
    for name, rows in context.items():
        if rows:
            tables[name] = pd.DataFrame(rows)
    if "events" in tables:
        # One recording can credit the artist twice (vocals and guitar): keep one event.
        tables["events"] = tables["events"].drop_duplicates(["event_date", "kind", "label"], ignore_index=True)

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
    kinds = tables["events"]["kind"].value_counts().to_dict() if "events" in tables else {}
    print(
        f"artist: {len(context['artist_tags'])} tags, {len(context['places'])} places, "
        f"{len(tables.get('events', []))} timeline events {kinds} "
        f"({len(manual['events']) + len(manual['places'])} from manual.yml)"
    )


if __name__ == "__main__":
    main()

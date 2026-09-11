"""Offline tests for source normalisation, using small hand-written API responses."""
import pandas as pd

from music_life.bundles import write_bundle
from music_life.sources import musicbrainz, spotify, wikidata


def artist_rel(kind, name, attributes=()):
    return {"target-type": "artist", "type": kind, "attributes": list(attributes),
            "artist": {"id": f"mb-{name}", "name": name}}


RELEASE = {
    "id": "release-1",
    "relations": [],
    "media": [{
        "position": 1,
        "tracks": [
            {"position": 1, "title": "First Song", "length": 200_000, "recording": {
                "id": "rec-1", "title": "First Song", "isrcs": ["GBAAA7800002", "GBAAA1100001"],
                "relations": [
                    artist_rel("instrument", "Pianist", ["piano"]),
                    artist_rel("producer", "Producer", ["co"]),
                    {"target-type": "work", "work": {
                        "id": "work-1", "title": "First Song",
                        "relations": [artist_rel("composer", "Writer")],
                    }},
                ],
            }},
            {"position": 2, "title": "Second Song", "length": 100_000, "recording": {
                "id": "rec-2", "title": "Second Song", "isrcs": [], "relations": [],
            }},
        ],
    }],
}
ARTIST = {
    "id": "mb-artist", "name": "Test Artist", "sort-name": "Artist, Test",
    "life-span": {"begin": "1947", "end": "2011-01-04"}, "begin-area": {"name": "Paisley"},
    "relations": [{"url": {"resource": "https://www.wikidata.org/wiki/Q1"}}],
}
RELEASE_GROUP = {
    "id": "rg-1", "title": "Test Album", "first-release-date": "1978", "primary-type": "Album",
    "relations": [{"url": {"resource": "https://www.discogs.com/master/54"}}],
}


def spotify_track(track_id, number, name, isrc):
    return {"id": track_id, "disc_number": 1, "track_number": number, "name": name,
            "external_ids": {"isrc": isrc}, "external_urls": {"spotify": f"https://open.spotify.com/track/{track_id}"}}


SPOTIFY_ALBUM = {
    "id": "sp-album", "uri": "spotify:album:sp-album", "name": "Test Album",
    "external_urls": {"spotify": "https://open.spotify.com/album/sp-album"},
    "artists": [{"id": "sp-artist", "name": "Test Artist"}],
}
SPOTIFY_TRACKS = [
    spotify_track("sp-1", 1, "First Song - 2011 Remaster", "GBAAA1100001"),
    spotify_track("sp-2", 2, "Second Song - Remastered", "USXXX0000009"),
]


def tables():
    return {
        "artist": musicbrainz.artist_frame(ARTIST, "test-artist"),
        "album": musicbrainz.album_frame(RELEASE_GROUP, "test-album"),
        "tracks": musicbrainz.tracks_frame(RELEASE),
        "credits": musicbrainz.credits_frame(RELEASE),
    }


def test_musicbrainz_frames_keep_partial_dates_out_and_separate_works():
    t = tables()
    artist = t["artist"].iloc[0]
    assert artist["birth_date"] is None and artist["death_date"] == "2011-01-04"
    assert artist["wikidata_id"] == "Q1"
    album = t["album"].iloc[0]
    assert album["original_release_date"] is None and album["discogs_master_id"] == "54"

    tracks = t["tracks"]
    assert list(tracks["track_title"]) == ["First Song", "Second Song"]
    assert tracks.loc[0, "musicbrainz_work_id"] == "work-1" and pd.isna(tracks.loc[1, "musicbrainz_work_id"])

    credits = t["credits"][["applies_to", "person_name", "role", "instrument"]].values.tolist()
    assert credits == [
        ["recording", "Pianist", "instrument", "piano"],
        ["recording", "Producer", "co producer", None],
        ["work", "Writer", "composer", None],
    ]


def test_spotify_verifies_by_isrc_and_keeps_title_matches_unverified():
    t = tables()
    verified = spotify.enrich(t, SPOTIFY_ALBUM, SPOTIFY_TRACKS, musicbrainz.track_isrcs(RELEASE))
    assert verified == 1
    tracks = t["tracks"]
    assert tracks["spotify_track_id"].tolist() == ["sp-1", "sp-2"]
    assert tracks["spotify_verified"].tolist() == [True, False]
    assert tracks.loc[0, "isrc"] == "GBAAA1100001"
    assert t["album"].loc[0, "spotify_album_id"] == "sp-album"
    assert t["artist"].loc[0, "spotify_id"] == "sp-artist"


def test_wikidata_publication_date_uses_earliest_full_date():
    def claim(time, precision):
        return {"mainsnak": {"datavalue": {"value": {"time": time, "precision": precision}}}}

    entity = {"claims": {"P577": [
        claim("+1978-00-00T00:00:00Z", 9),
        claim("+1978-03-01T00:00:00Z", 11),
        claim("+1978-01-20T00:00:00Z", 11),
    ]}}
    assert wikidata.publication_date(entity) == "1978-01-20"
    assert wikidata.publication_date({"claims": {"P577": [claim("+1978-00-00T00:00:00Z", 9)]}}) is None


def test_collected_tables_form_a_valid_bundle(tmp_path):
    t = tables()
    t["sources"] = pd.DataFrame([{
        "source_key": key, "source_name": "test", "source_type": "test",
        "source_url": None, "retrieved_at": "2026-01-01", "citation_text": None,
    } for key in ["musicbrainz-artist", "musicbrainz-release-group", "musicbrainz-release"]])
    write_bundle("test-artist", "test-album", t, root=tmp_path)

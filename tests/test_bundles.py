import duckdb
import pandas as pd
import pytest

from music_life.bundles import TABLES, iter_bundles, load_bundle, write_bundle
from music_life.db import init_db

ARTIST, ALBUM = "test-artist", "test-album"


def frame(table: str, *rows: dict) -> pd.DataFrame:
    return pd.DataFrame(list(rows)).reindex(columns=list(TABLES[table].columns))


def fixture_tables() -> dict[str, pd.DataFrame]:
    return {
        "sources": frame("sources", {
            "source_key": "fixture", "source_name": "fixture", "source_type": "test",
            "retrieved_at": "2026-01-01 00:00:00",
        }),
        "artist": frame("artist", {"slug": ARTIST, "name": "Test Artist", "source_key": "fixture"}),
        "album": frame("album", {
            "slug": ALBUM, "title": "Test Album", "original_release_date": "1977-05-01",
            "source_key": "fixture",
        }),
        "tracks": frame(
            "tracks",
            {"disc_number": 1, "track_number": 2, "track_title": "Second", "duration_ms": 200_000,
             "musicbrainz_recording_id": "rec-2", "source_key": "fixture"},
            {"disc_number": 1, "track_number": 1, "track_title": "First", "duration_ms": 180_000,
             "musicbrainz_recording_id": "rec-1", "musicbrainz_work_id": "work-1",
             "source_key": "fixture"},
        ),
        "credits": frame(
            "credits",
            {"person_name": "A Producer", "role": "producer", "source_key": "fixture"},
            {"disc_number": 1, "track_number": 1, "person_name": "A Singer", "role": "performer",
             "instrument": "vocals", "source_key": "fixture"},
        ),
    }


def test_bundle_loads_into_duckdb(tmp_path):
    path = write_bundle(ARTIST, ALBUM, fixture_tables(), root=tmp_path / "curated")
    assert list(iter_bundles(tmp_path / "curated")) == [path]

    db = tmp_path / "test.duckdb"
    init_db(db)
    con = duckdb.connect(str(db))
    load_bundle(con, path)

    tracks = con.execute(
        """
        SELECT t.track_number, r.title, r.duration_ms, r.release_year, t.work_id IS NOT NULL
        FROM album_tracks t JOIN recordings r USING (recording_id)
        JOIN albums a USING (album_id)
        WHERE a.slug = ? AND a.is_focus_album
        ORDER BY t.track_number
        """,
        [ALBUM],
    ).fetchall()
    assert tracks == [(1, "First", 180_000, 1977, True), (2, "Second", 200_000, 1977, False)]
    credits = con.execute(
        "SELECT entity_type, role FROM credits ORDER BY entity_type"
    ).fetchall()
    assert credits == [("album", "producer"), ("recording", "performer")]
    assert con.execute("SELECT raw_reference FROM sources").fetchone()[0] == f"{ARTIST}/{ALBUM}:fixture"
    con.close()


def test_rewriting_unchanged_data_gives_identical_files(tmp_path):
    first = write_bundle(ARTIST, ALBUM, fixture_tables(), root=tmp_path / "a")
    second = write_bundle(ARTIST, ALBUM, fixture_tables(), root=tmp_path / "b")
    for name in fixture_tables():
        assert (first / f"{name}.parquet").read_bytes() == (second / f"{name}.parquet").read_bytes()


def test_rejects_unexpected_columns(tmp_path):
    tables = fixture_tables()
    tables["artist"]["nickname"] = "x"
    with pytest.raises(ValueError, match="unexpected columns"):
        write_bundle(ARTIST, ALBUM, tables, root=tmp_path)


def test_rejects_credit_for_unknown_track(tmp_path):
    tables = fixture_tables()
    tables["credits"].loc[1, "track_number"] = 9
    with pytest.raises(ValueError, match="unknown tracks"):
        write_bundle(ARTIST, ALBUM, tables, root=tmp_path)

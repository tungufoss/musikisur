"""Per-album data bundles: the curated output of the skills, stored as Parquet.

Each focus album owns one bundle directory, ``data/curated/<artist-slug>/<album-slug>/``,
holding one Parquet file per table in TABLES. Rows use natural keys (slugs, disc/track
numbers, source keys) instead of database IDs, so bundles researched on different branches
never collide; ``load_bundle`` assigns IDs when DuckDB is rebuilt.
"""
from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path

import duckdb
import pandas as pd

CURATED_DIR = Path(__file__).resolve().parents[2] / "data" / "curated"


@dataclass(frozen=True)
class TableSpec:
    columns: dict[str, str]  # column -> DuckDB type
    order_by: tuple[str, ...]
    required: bool = True


TABLES: dict[str, TableSpec] = {
    "sources": TableSpec(
        {
            "source_key": "VARCHAR",
            "source_name": "VARCHAR",
            "source_type": "VARCHAR",
            "source_url": "VARCHAR",
            "retrieved_at": "TIMESTAMP",
            "citation_text": "VARCHAR",
        },
        ("source_key",),
    ),
    "artist": TableSpec(
        {
            "slug": "VARCHAR",
            "name": "VARCHAR",
            "sort_name": "VARCHAR",
            "birth_date": "DATE",
            "death_date": "DATE",
            "birth_place": "VARCHAR",
            "musicbrainz_id": "VARCHAR",
            "wikidata_id": "VARCHAR",
            "discogs_id": "VARCHAR",
            "spotify_id": "VARCHAR",
            "source_key": "VARCHAR",
        },
        ("slug",),
    ),
    "album": TableSpec(
        {
            "slug": "VARCHAR",
            "title": "VARCHAR",
            "original_release_date": "DATE",
            "album_type": "VARCHAR",
            "musicbrainz_release_group_id": "VARCHAR",
            "discogs_master_id": "VARCHAR",
            "spotify_album_id": "VARCHAR",
            "spotify_url": "VARCHAR",
            "spotify_uri": "VARCHAR",
            "source_key": "VARCHAR",
        },
        ("slug",),
    ),
    "tracks": TableSpec(
        {
            "disc_number": "INTEGER",
            "track_number": "INTEGER",
            "track_title": "VARCHAR",
            "recording_title": "VARCHAR",
            "duration_ms": "INTEGER",
            "isrc": "VARCHAR",
            "musicbrainz_recording_id": "VARCHAR",
            "musicbrainz_work_id": "VARCHAR",
            "spotify_track_id": "VARCHAR",
            "spotify_url": "VARCHAR",
            "spotify_verified": "BOOLEAN",
            "sample_url": "VARCHAR",  # short audio sample (manual.yml)
            "sample_page": "VARCHAR",  # page that hosts it and states its licence
            "source_key": "VARCHAR",
        },
        ("disc_number", "track_number"),
    ),
    "credits": TableSpec(
        {
            # NULL disc/track means the credit applies to the whole album.
            "disc_number": "INTEGER",
            "track_number": "INTEGER",
            # album / recording / work; NULL means album without a track, else recording.
            "applies_to": "VARCHAR",
            "person_name": "VARCHAR",
            "role": "VARCHAR",
            "instrument": "VARCHAR",
            "credited_as": "VARCHAR",
            "musicbrainz_artist_id": "VARCHAR",
            "discogs_artist_id": "VARCHAR",
            "source_key": "VARCHAR",
        },
        ("disc_number", "track_number", "role", "person_name", "instrument"),
        required=False,
    ),
    # Artist context for the chapter's "Um flytjandann" section.
    "artist_tags": TableSpec(
        {
            "kind": "VARCHAR",  # genre / instrument / occupation
            "qid": "VARCHAR",
            "label_is": "VARCHAR",
            "label_en": "VARCHAR",
            "source_key": "VARCHAR",
        },
        ("kind", "label_en"),
        required=False,
    ),
    "places": TableSpec(
        {
            "role": "VARCHAR",  # birth / death / residence / mentioned
            "qid": "VARCHAR",
            "title": "VARCHAR",
            "label_is": "VARCHAR",
            "country": "VARCHAR",  # country or UK constituent country, from Wikidata
            "latitude": "DOUBLE",
            "longitude": "DOUBLE",
            "context": "VARCHAR",
            "source_key": "VARCHAR",
        },
        ("role", "title"),
        required=False,
    ),
    "events": TableSpec(
        {
            "event_date": "DATE",  # unknown month/day padded with 01, see date_precision
            "date_precision": "INTEGER",  # Wikidata style: 9 year, 10 month, 11 day
            "kind": "VARCHAR",
            "label": "VARCHAR",
            "detail": "VARCHAR",
            "url": "VARCHAR",
            "source_key": "VARCHAR",
        },
        ("event_date", "kind", "label"),
        required=False,
    ),
    # Soundtrack releases (films, TV, games) that carry the album's songs, from MusicBrainz.
    "soundtracks": TableSpec(
        {
            "song": "VARCHAR",  # the album track's title
            "release": "VARCHAR",  # the soundtrack release group's title
            "year": "INTEGER",
            "url": "VARCHAR",
            "source_key": "VARCHAR",
        },
        ("song", "year", "release"),
        required=False,
    ),
    # Film and TV titles that use the artist's songs: IMDb soundtrack credits (exported by hand)
    # with TMDB's vote count for ranking (scripts/screen_credits.py). Artist-level, like places.
    "screen_credits": TableSpec(
        {
            "imdb_id": "VARCHAR",
            "title": "VARCHAR",
            "kind": "VARCHAR",  # tv / movie / other
            "imdb_type": "VARCHAR",
            "first_year": "INTEGER",
            "last_year": "INTEGER",
            "episodes": "INTEGER",
            "songs": "VARCHAR",  # "; "-separated, in the artist's own spelling
            "imdb_rating": "DOUBLE",
            "tmdb_votes": "INTEGER",
            "tmdb_url": "VARCHAR",
            "retrieved_at": "TIMESTAMP",
        },
        ("first_year", "imdb_id"),
        required=False,
    ),
    # A Spotify link per song named in screen_credits (the artist's or a band's recording).
    "song_links": TableSpec(
        {
            "song": "VARCHAR",
            "spotify_url": "VARCHAR",
            "spotify_name": "VARCHAR",  # what Spotify calls the match, for checking by hand
            "retrieved_at": "TIMESTAMP",
        },
        ("song",),
        required=False,
    ),
    # Spotify links for the other entries on the album's best chart week (scripts/chart_links.py).
    # Each row carries its own provenance, so re-collecting the album leaves them valid.
    "chart_links": TableSpec(
        {
            "chart": "VARCHAR",
            "artist_name": "VARCHAR",  # as printed on the chart
            "title": "VARCHAR",
            "spotify_url": "VARCHAR",
            "spotify_name": "VARCHAR",  # what Spotify calls the match, for checking by hand
            "retrieved_at": "TIMESTAMP",
        },
        ("chart", "artist_name", "title"),
        required=False,
    ),
}
EVENT_KINDS = {
    "birth", "death", "career_start", "career_end", "marriage", "divorce", "relationship", "relationship_end", "child",
    "album", "single", "band_album", "band_join", "band_leave", "song", "production", "guest",
    "cover", "nomination", "award", "event",
}


def bundle_dir(artist_slug: str, album_slug: str, root: Path = CURATED_DIR) -> Path:
    return root / artist_slug / album_slug


def iter_bundles(root: Path = CURATED_DIR) -> Iterator[Path]:
    yield from sorted(p.parent for p in root.glob("*/*/album.parquet"))


def _read(con: duckdb.DuckDBPyConnection, path: Path) -> pd.DataFrame:
    return con.execute("SELECT * FROM read_parquet(?)", [path.as_posix()]).df()


def write_bundle(
    artist_slug: str,
    album_slug: str,
    tables: dict[str, pd.DataFrame],
    root: Path = CURATED_DIR,
) -> Path:
    """Write tables as typed, deterministically ordered Parquet and validate the bundle."""
    target = bundle_dir(artist_slug, album_slug, root)
    target.mkdir(parents=True, exist_ok=True)
    con = duckdb.connect()
    try:
        for name, frame in tables.items():
            spec = TABLES.get(name)
            if spec is None:
                raise ValueError(f"unknown bundle table {name!r}")
            if set(frame.columns) != set(spec.columns):
                missing = sorted(set(spec.columns) - set(frame.columns))
                extra = sorted(set(frame.columns) - set(spec.columns))
                raise ValueError(f"{name}: missing columns {missing}, unexpected columns {extra}")
            frame = frame.astype(object).where(frame.notna(), None)
            con.register("frame", frame)
            select = ", ".join(f'CAST("{c}" AS {t}) AS "{c}"' for c, t in spec.columns.items())
            order = ", ".join(f'"{c}" NULLS FIRST' for c in spec.order_by)
            out = (target / f"{name}.parquet").as_posix()
            con.execute(
                f"COPY (SELECT {select} FROM frame ORDER BY {order}) "
                f"TO '{out}' (FORMAT parquet, COMPRESSION zstd)"
            )
            con.unregister("frame")
    finally:
        con.close()
    errors = validate_bundle(target)
    if errors:
        raise ValueError("invalid bundle:\n" + "\n".join(errors))
    return target


def validate_bundle(path: Path) -> list[str]:
    """Return human-readable problems with a bundle; an empty list means it is valid."""
    errors: list[str] = []
    con = duckdb.connect()
    try:
        frames: dict[str, pd.DataFrame] = {}
        for name, spec in TABLES.items():
            file = path / f"{name}.parquet"
            if not file.exists():
                if spec.required:
                    errors.append(f"{path.name}: missing {name}.parquet")
                continue
            frames[name] = _read(con, file)
            if list(frames[name].columns) != list(spec.columns):
                errors.append(f"{name}.parquet: columns do not match TABLES[{name!r}]")
    finally:
        con.close()
    if errors:
        return errors

    artist, album, tracks = frames["artist"], frames["album"], frames["tracks"]
    if len(artist) != 1 or artist["slug"].iloc[0] != path.parent.name:
        errors.append(f"artist.parquet must hold exactly one row with slug {path.parent.name!r}")
    if len(album) != 1 or album["slug"].iloc[0] != path.name:
        errors.append(f"album.parquet must hold exactly one row with slug {path.name!r}")
    if tracks.duplicated(["disc_number", "track_number"]).any():
        errors.append("tracks.parquet has duplicate disc/track numbers")

    source_keys = set(frames["sources"]["source_key"])
    for name, frame in frames.items():
        if "source_key" in frame.columns and name != "sources":
            unknown = set(frame["source_key"].dropna()) - source_keys
            if unknown:
                errors.append(f"{name}.parquet references unknown source_key {sorted(unknown)}")

    credits = frames.get("credits")
    if credits is not None:
        track_level = credits.dropna(subset=["track_number"])
        known = set(zip(tracks["disc_number"], tracks["track_number"]))
        orphans = [
            (d, t) for d, t in zip(track_level["disc_number"], track_level["track_number"])
            if (d, t) not in known
        ]
        if orphans:
            errors.append(f"credits.parquet references unknown tracks {sorted(set(orphans))}")
        unknown_levels = set(credits["applies_to"].dropna()) - {"album", "recording", "work"}
        if unknown_levels:
            errors.append(f"credits.parquet has unknown applies_to values {sorted(unknown_levels)}")
        with_work = tracks.dropna(subset=["musicbrainz_work_id"])
        work_tracks = set(zip(with_work["disc_number"], with_work["track_number"]))
        work_credits = credits[credits["applies_to"] == "work"]
        workless = [
            (d, t) for d, t in zip(work_credits["disc_number"], work_credits["track_number"])
            if (d, t) not in work_tracks
        ]
        if workless:
            errors.append(f"credits.parquet has work credits for tracks without a work {sorted(set(workless))}")

    events = frames.get("events")
    if events is not None:
        unknown_kinds = set(events["kind"]) - EVENT_KINDS
        if unknown_kinds:
            errors.append(f"events.parquet has unknown kinds {sorted(unknown_kinds)}")
    places = frames.get("places")
    if places is not None and places[["latitude", "longitude"]].isna().any().any():
        errors.append("places.parquet has places without coordinates")
    return errors


def _value(row: pd.Series, column: str) -> object:
    value = row[column]
    return None if pd.isna(value) else value


def _find_or_insert(
    con: duckdb.DuckDBPyConnection,
    table: str,
    id_column: str,
    matches: list[tuple[str, object]],
    values: dict[str, object],
) -> int:
    """Return the id of the first row matching any (column, value) pair, else insert one."""
    for column, value in matches:
        if value is not None:
            row = con.execute(
                f"SELECT {id_column} FROM {table} WHERE {column} = ?", [value]
            ).fetchone()
            if row:
                return row[0]
    columns = ", ".join(values)
    marks = ", ".join("?" for _ in values)
    return con.execute(
        f"INSERT INTO {table} ({columns}) VALUES ({marks}) RETURNING {id_column}",
        list(values.values()),
    ).fetchone()[0]


def load_bundle(con: duckdb.DuckDBPyConnection, path: Path) -> None:
    """Insert one validated bundle into an initialised music_life database."""
    frames = {
        name: _read(con, path / f"{name}.parquet")
        for name in TABLES
        if (path / f"{name}.parquet").exists()
    }
    bundle = f"{path.parent.name}/{path.name}"

    source_ids = {}
    for _, row in frames["sources"].iterrows():
        source_ids[row["source_key"]] = con.execute(
            """
            INSERT INTO sources
            (source_name, source_type, source_url, retrieved_at, citation_text, raw_reference)
            VALUES (?, ?, ?, ?, ?, ?) RETURNING source_id
            """,
            [
                _value(row, "source_name"), _value(row, "source_type"), _value(row, "source_url"),
                _value(row, "retrieved_at"), _value(row, "citation_text"),
                f"{bundle}:{row['source_key']}",
            ],
        ).fetchone()[0]

    artist = frames["artist"].iloc[0]
    artist_columns = [c for c in TABLES["artist"].columns if c not in {"slug", "source_key"}]
    updates = ", ".join(f"{c} = coalesce(artists.{c}, excluded.{c})" for c in artist_columns)
    artist_id = con.execute(
        f"""
        INSERT INTO artists (slug, {", ".join(artist_columns)})
        VALUES (?, {", ".join("?" for _ in artist_columns)})
        ON CONFLICT (slug) DO UPDATE SET {updates}
        RETURNING artist_id
        """,
        [artist["slug"], *(_value(artist, c) for c in artist_columns)],
    ).fetchone()[0]

    album = frames["album"].iloc[0]
    album_columns = [c for c in TABLES["album"].columns if c not in {"slug", "source_key"}]
    album_id = con.execute(
        f"""
        INSERT INTO albums (slug, artist_id, is_focus_album, {", ".join(album_columns)})
        VALUES (?, ?, TRUE, {", ".join("?" for _ in album_columns)})
        RETURNING album_id
        """,
        [album["slug"], artist_id, *(_value(album, c) for c in album_columns)],
    ).fetchone()[0]
    release_year = album["original_release_date"].year if _value(album, "original_release_date") else None

    recording_ids, work_ids = {}, {}
    for _, track in frames["tracks"].iterrows():
        recording_id = _find_or_insert(
            con, "recordings", "recording_id",
            [("musicbrainz_recording_id", _value(track, "musicbrainz_recording_id")),
             ("isrc", _value(track, "isrc"))],
            {
                "title": _value(track, "recording_title") or track["track_title"],
                "primary_artist_name": artist["name"],
                "release_year": release_year,
                "duration_ms": _value(track, "duration_ms"),
                "musicbrainz_recording_id": _value(track, "musicbrainz_recording_id"),
                "isrc": _value(track, "isrc"),
                "spotify_track_id": _value(track, "spotify_track_id"),
                "spotify_url": _value(track, "spotify_url"),
                "spotify_verified": bool(_value(track, "spotify_verified")),
            },
        )
        work_id = None
        if _value(track, "musicbrainz_work_id"):
            work_id = _find_or_insert(
                con, "works", "work_id",
                [("musicbrainz_work_id", track["musicbrainz_work_id"])],
                {"title": _value(track, "recording_title") or track["track_title"],
                 "musicbrainz_work_id": track["musicbrainz_work_id"]},
            )
        key = (int(track["disc_number"]), int(track["track_number"]))
        recording_ids[key] = recording_id
        work_ids[key] = work_id
        con.execute(
            """
            INSERT INTO album_tracks
            (album_id, recording_id, work_id, disc_number, track_number, track_title, sample_url, sample_page)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [album_id, recording_id, work_id, *key, track["track_title"],
             _value(track, "sample_url"), _value(track, "sample_page")],
        )

    if "credits" in frames:
        for _, credit in frames["credits"].iterrows():
            person_id = _find_or_insert(
                con, "people", "person_id",
                [("musicbrainz_id", _value(credit, "musicbrainz_artist_id")),
                 ("discogs_id", _value(credit, "discogs_artist_id")),
                 ("name", credit["person_name"])],
                {"name": credit["person_name"],
                 "musicbrainz_id": _value(credit, "musicbrainz_artist_id"),
                 "discogs_id": _value(credit, "discogs_artist_id")},
            )
            entity_type = _value(credit, "applies_to") or (
                "album" if _value(credit, "track_number") is None else "recording"
            )
            if entity_type == "album":
                entity_id = album_id
            else:
                key = (int(credit["disc_number"]), int(credit["track_number"]))
                entity_id = recording_ids[key] if entity_type == "recording" else work_ids[key]
            con.execute(
                """
                INSERT INTO credits
                (person_id, entity_type, entity_id, role, instrument, credited_as, source_id)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                [person_id, entity_type, entity_id, credit["role"], _value(credit, "instrument"),
                 _value(credit, "credited_as"), source_ids.get(_value(credit, "source_key"))],
            )

    # Artist context; several bundles may carry the same artist, so duplicates are skipped.
    artist_context = {
        "artist_tags": ("artist_tags", ["kind", "qid", "label_is", "label_en"]),
        "places": ("artist_places", ["role", "qid", "title", "label_is", "country", "latitude", "longitude", "context"]),
        "events": ("timeline_events", ["event_date", "date_precision", "kind", "label", "detail", "url"]),
    }
    for name, (table, columns) in artist_context.items():
        if name not in frames:
            continue
        marks = ", ".join("?" for _ in columns)
        for _, row in frames[name].iterrows():
            con.execute(
                f"INSERT INTO {table} (artist_id, {', '.join(columns)}, source_id) "
                f"VALUES (?, {marks}, ?) ON CONFLICT DO NOTHING",
                [artist_id, *(_value(row, c) for c in columns), source_ids.get(_value(row, "source_key"))],
            )

    screen_columns = list(TABLES["screen_credits"].columns)
    for _, row in frames.get("screen_credits", pd.DataFrame()).iterrows():
        con.execute(
            f"INSERT INTO screen_credits (artist_id, {', '.join(screen_columns)}) "
            f"VALUES (?, {', '.join('?' for _ in screen_columns)}) ON CONFLICT DO NOTHING",
            [artist_id, *(_value(row, c) for c in screen_columns)],
        )

    for _, row in frames.get("song_links", pd.DataFrame()).iterrows():
        con.execute(
            "INSERT INTO song_links (artist_id, song, spotify_url, spotify_name, retrieved_at) "
            "VALUES (?, ?, ?, ?, ?) ON CONFLICT DO NOTHING",
            [artist_id, row["song"], row["spotify_url"], _value(row, "spotify_name"), _value(row, "retrieved_at")],
        )

    for _, row in frames.get("soundtracks", pd.DataFrame()).iterrows():
        con.execute(
            "INSERT INTO album_soundtracks (album_id, song, release, year, url, source_id) VALUES (?, ?, ?, ?, ?, ?)",
            [album_id, row["song"], row["release"], _value(row, "year"), row["url"],
             source_ids.get(_value(row, "source_key"))],
        )

    # Skipped when the charts themselves are not loaded (submodule not checked out).
    for _, row in frames.get("chart_links", pd.DataFrame()).iterrows():
        con.execute(
            """
            INSERT INTO chart_links (chart_id, artist_name, title, spotify_url, spotify_name, retrieved_at)
            SELECT chart_id, ?, ?, ?, ?, ? FROM charts WHERE name = ?
            ON CONFLICT DO NOTHING
            """,
            [row["artist_name"], row["title"], row["spotify_url"], _value(row, "spotify_name"),
             _value(row, "retrieved_at"), row["chart"]],
        )

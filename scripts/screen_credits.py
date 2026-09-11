"""Film and TV uses of the artist's songs: an IMDb soundtrack export, ranked with TMDB.

IMDb has no open API and does not allow automated collection, so the credits are exported by
hand: open https://www.imdb.com/name/<nm-id>/?showAllCredits=true in a browser and copy each
soundtrack credit (IMDb id, title, type, years, episodes, rating, songs) into
data/raw/imdb/soundtrack-<nm-id>.json, shaped like the Gerry Rafferty file. data/raw is not
committed; the bundle keeps only titles, years and songs, each linked to its IMDb page.

    python scripts/screen_credits.py gerry-rafferty city-to-city data/raw/imdb/soundtrack-nm1391241.json

Run after scripts/build_db.py (the artist's song names come from the database), then rebuild.
"""
import argparse
import json
from pathlib import Path

import pandas as pd

from music_life.bundles import TABLES, write_bundle
from music_life.dashboard import connect_ro
from music_life.sources import screen, spotify


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("artist", help="artist slug")
    parser.add_argument("album", help="album slug (the bundle to write into)")
    parser.add_argument("export", help="IMDb soundtrack export (JSON)")
    args = parser.parse_args()

    export = json.loads(Path(args.export).read_text(encoding="utf-8"))
    with connect_ro() as con:
        # Each song once, with who released it first ("solo" or a band's name).
        firsts = con.execute(
            """
            SELECT e.label, e.detail FROM timeline_events e JOIN artists a USING (artist_id)
            WHERE a.slug = ? AND e.kind = 'song'
            """,
            [args.artist],
        ).fetchall()
        name = con.execute("SELECT name FROM artists WHERE slug = ?", [args.artist]).fetchone()[0]
        bands = [label for (label,) in con.execute(
            """
            SELECT e.label FROM timeline_events e JOIN artists a USING (artist_id)
            WHERE a.slug = ? AND e.kind = 'band_join' ORDER BY e.event_date
            """,
            [args.artist],
        ).fetchall()]
    known = [label for label, _ in firsts]
    owners = {label: name if detail == "solo" else detail for label, detail in firsts}
    c = screen.tmdb_client()
    rows = screen.credit_rows(export, known, lambda imdb_id: screen.find_by_imdb_id(imdb_id, c))
    frame = pd.DataFrame(rows, columns=list(TABLES["screen_credits"].columns))

    # A Spotify link per song: the artist's recording, else a band's.
    sp = spotify.client()
    songs = sorted({song for row in rows for song in row["songs"].split("; ")}, key=str.lower)
    links = screen.song_links(
        songs, [name, *bands], lambda performer, song: spotify.search(sp, performer, song, "track"), owners
    )
    for link in links:
        link["retrieved_at"] = sp.retrieved_at(link.pop("cache_key"))
    missing = sorted(set(songs) - {link["song"] for link in links})

    path = write_bundle(args.artist, args.album, {
        "screen_credits": frame,
        "song_links": pd.DataFrame(links, columns=list(TABLES["song_links"].columns)),
    })
    kinds = frame["kind"].value_counts().to_dict()
    print(f"wrote {len(frame)} titles {kinds} to {path.as_posix()}/screen_credits.parquet; "
          f"{frame['tmdb_votes'].notna().sum()} found on TMDB")
    for link in links:
        print(f"spotify: {link['song']} -> {link['spotify_name']}")
    print(f"spotify: {len(links)}/{len(songs)} songs linked" + (f"; no match for {missing}" if missing else ""))


if __name__ == "__main__":
    main()

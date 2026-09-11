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
from music_life.sources import screen


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("artist", help="artist slug")
    parser.add_argument("album", help="album slug (the bundle to write into)")
    parser.add_argument("export", help="IMDb soundtrack export (JSON)")
    args = parser.parse_args()

    export = json.loads(Path(args.export).read_text(encoding="utf-8"))
    with connect_ro() as con:
        known = [label for (label,) in con.execute(
            """
            SELECT DISTINCT e.label FROM timeline_events e JOIN artists a USING (artist_id)
            WHERE a.slug = ? AND e.kind = 'song'
            """,
            [args.artist],
        ).fetchall()]
    c = screen.tmdb_client()
    rows = screen.credit_rows(export, known, lambda imdb_id: screen.find_by_imdb_id(imdb_id, c))
    frame = pd.DataFrame(rows, columns=list(TABLES["screen_credits"].columns))
    path = write_bundle(args.artist, args.album, {"screen_credits": frame})
    kinds = frame["kind"].value_counts().to_dict()
    print(f"wrote {len(frame)} titles {kinds} to {path.as_posix()}/screen_credits.parquet; "
          f"{frame['tmdb_votes'].notna().sum()} found on TMDB")


if __name__ == "__main__":
    main()

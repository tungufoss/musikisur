"""Find Spotify links for the other entries on an album's best chart week ("Hvað annað var vinsælt?").

    python scripts/chart_links.py gerry-rafferty city-to-city

Needs the Billboard charts, so run it after scripts/build_db.py, then rebuild the database.
The links are written to the album bundle as chart_links.parquet. Matches must agree on
title and artist; anything unmatched is listed so it can be checked by hand.
"""
import argparse

import pandas as pd

from music_life.bundles import TABLES, write_bundle
from music_life.dashboard import chart_neighbours, connect_ro
from music_life.sources import spotify


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("artist", help="artist slug")
    parser.add_argument("album", help="album slug")
    parser.add_argument("--window", type=int, default=5, help="chart positions above and below the album")
    args = parser.parse_args()

    with connect_ro() as con:
        found = chart_neighbours(con, args.album, args.window)
    if found is None:
        raise SystemExit(f"{args.album}: no chart entries, nothing to link (is the database built?)")
    _, peak, week = found
    kind = "album" if peak["chart_type"] == "albums" else "track"

    c = spotify.client()
    rows = []
    for _, entry in week.iterrows():
        match, key = spotify.search(c, entry["artist_name"], entry["title"], kind)
        if match is None:
            print(f"no match: {entry['position']}. {entry['artist_name']} – {entry['title']}")
            continue
        released = (match.get("album") or match)["release_date"]
        artists = ", ".join(a["name"] for a in match["artists"])
        rows.append({
            "chart": peak["chart"],
            "artist_name": entry["artist_name"],
            "title": entry["title"],
            "spotify_url": match["external_urls"]["spotify"],
            "spotify_name": f"{artists} – {match['name']} ({released})",
            "retrieved_at": c.retrieved_at(key),
        })
        print(f"{entry['position']}. {entry['artist_name']} – {entry['title']} -> {rows[-1]['spotify_name']}")

    links = pd.DataFrame(rows, columns=list(TABLES["chart_links"].columns))
    path = write_bundle(args.artist, args.album, {"chart_links": links})
    print(f"wrote {len(rows)}/{len(week)} links to {path.as_posix()}/chart_links.parquet")


if __name__ == "__main__":
    main()

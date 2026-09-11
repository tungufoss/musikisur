"""Find a song on Spotify and print a ready-to-paste chapter shortcode.

    python scripts/spotify_lookup.py "Steve Marcus" "Half a Heart"

Matches are listed oldest release first, so the original usually beats later compilations.
Results are cached in data/raw/spotify/.
"""
import argparse
import re

from music_life.sources import spotify


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("artist")
    parser.add_argument("title")
    parser.add_argument("--limit", type=int, default=5)
    args = parser.parse_args()

    c = spotify.client()
    key = "search-" + re.sub(r"[^a-z0-9]+", "-", f"{args.artist} {args.title}".lower()).strip("-")
    result = c.get_json(
        "search", key,
        {"q": f'track:"{args.title}" artist:"{args.artist}"', "type": "track", "limit": args.limit},
    )
    tracks = sorted(result["tracks"]["items"], key=lambda t: t["album"]["release_date"])
    if not tracks:
        raise SystemExit(f"No Spotify match for {args.artist} – {args.title}")
    for t in tracks:
        artists = ", ".join(a["name"] for a in t["artists"])
        print(f'{{{{< spotify {t["id"]} >}}}}  {t["name"]} | {artists} | {t["album"]["name"]} ({t["album"]["release_date"]})')


if __name__ == "__main__":
    main()

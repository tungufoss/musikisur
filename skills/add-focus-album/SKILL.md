# Skill: Add a focus album

## Goal

Promote an album to a research focus while retaining its surrounding life, career and chart context.

## Procedure

1. Ensure the artist exists.
2. Add the album to `config/focus-albums.yml`.
3. Resolve MusicBrainz release-group, Discogs master and Spotify album IDs.
4. Preserve original release date separately from later editions.
5. Resolve tracks to recordings and, where available, underlying works.
6. Retrieve album- and recording-level credits.
7. Enrich album/tracks with Spotify URLs.
8. Identify charting singles and album-chart entries.
9. Ingest complete surrounding weekly chart snapshots where possible.
10. Refresh contemporary-context analysis.
11. Add sourced life/career events relevant to the period without implying causation.
11a. Put the MusicBrainz release group, the chosen `musicbrainz_release` (edition for the track list), Discogs master and Spotify album IDs in config, then run `python scripts/collect_album.py <artist-slug> <album-slug>` to write the bundle.
12. Run `python scripts/build_book.py` to create the chapter (and its decade part if new), then add talking points under "Punktar fyrir þáttinn" in `dashboard/albums/<slug>.qmd`.
13. Validate and render Quarto.

## Spotify matching

Prefer exact ISRC, then cross-source IDs, then artist/title/year candidates. Fuzzy candidates require review. Avoid accidental live/remaster/re-recording substitution.

## Checklist

- [ ] Historical album concept distinguished from editions
- [ ] Track order present
- [ ] Works vs recordings separated
- [ ] Personnel/production linked
- [ ] Spotify album URL matched where possible
- [ ] Track Spotify URLs matched confidently
- [ ] Chart windows/context present
- [ ] Claims/provenance intact

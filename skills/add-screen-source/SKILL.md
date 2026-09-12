# Skill: Add film and TV uses of an artist's songs

## Goal

List the films, series and other titles that use an artist's songs, with the song, the years of
use and a link to each title, and rank the titles by popularity.

## Sources

- **IMDb soundtrack credits** say which titles use which songs. IMDb has no open API and does not
  allow automated collection: never script requests to imdb.com. Export the credits by hand.
- **TMDB** finds each title by its IMDb id and gives its vote count, used to rank titles by
  popularity. TMDB's own cast and crew credits do not list licensed songs, so it cannot replace IMDb.

## Procedure

1. Open `https://www.imdb.com/name/<nm-id>/?showAllCredits=true` in a browser and read the
   Soundtrack credits.
2. Save them as `data/raw/imdb/soundtrack-<nm-id>.json`, shaped like the Gerry Rafferty file:
   IMDb id, title, type, years, episodes, rating and the songs named in the credit.
   `data/raw` is not committed; do not redistribute IMDb data.
3. Run `python scripts/build_db.py` (song names and bands come from the database).
4. Run `python scripts/screen_credits.py <artist> <album> data/raw/imdb/soundtrack-<nm-id>.json`.
   It maps IMDb's song titles to the artist's own spelling, adds TMDB vote counts, finds a Spotify
   link per song (starting with whoever released it first), and writes `screen_credits.parquet`
   and `song_links.parquet` into the album bundle.
5. Check the printed Spotify matches and any song without a match.
6. Rebuild the database and render the artist page and the chapter.

## Checklist

- [ ] Credits read by hand, not scraped
- [ ] Every title links to its IMDb page
- [ ] Song titles mapped to the artist's own songs (unmatched ones kept as IMDb names them)
- [ ] Spotify links checked against the original recording
- [ ] Book renders; the timeline shows the film and TV lane

# Skill: Add an artist

## Goal

Add a new artist without schema changes or artist-specific dashboard code.

## Procedure

1. Add an entry to `config/artists.yml`.
2. Use a stable lowercase hyphenated slug.
3. Resolve MusicBrainz, Wikidata, Discogs and Spotify IDs where possible.
4. Use `primary` for a biography/dashboard lens; `context` for supporting artists.
5. Decide whether to include groups, external credits and biography.
6. Run `python scripts/init_db.py`.
7. Run/implement source adapters.
8. Review fuzzy entity matches.
9. Run `python scripts/validate.py`.
10. Render Quarto.

## External-credit rule

Do not restrict retrieval to releases primarily billed to the artist. Capture supported roles including songwriting, production, performance, guest work, instruments and arrangement.

## Checklist

- [ ] Stable IDs recorded
- [ ] Aliases considered
- [ ] Groups linked rather than copied into solo discography
- [ ] External credits included
- [ ] Biography claims sourced
- [ ] No inferred causality represented as fact
- [ ] Dashboard renders

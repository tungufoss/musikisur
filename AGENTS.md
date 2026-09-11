# AGENTS.md

## Mission

Maintain a reproducible, source-aware music biography and historical-context dataset.

Gerry Rafferty / *City to City* is the pilot only. New artists and focus albums must use the same schema and pipeline.

## Architecture

- DuckDB is the analytical datastore.
- Python handles ingestion, raw caching, normalization, entity resolution and enrichment.
- Quarto is the dashboard/report layer.
- GitHub Actions renders and deploys the site.
- Quarto documents should not perform live API calls.
- Raw/source-specific observations must remain traceable to provenance.

## Non-negotiable modelling rules

1. Never collapse `work`, `recording`, `album/release_group`, and `release`.
2. Model credits as relationships/rows; one person may have multiple roles.
3. Historical chart rows preserve the source's artist/title text even after canonical matching.
4. Spotify is enrichment, not canonical historical identity.
5. Biographical/personal claims require a source and review state.
6. Derived metrics and interpretations must be labelled as derived.
7. LLM output is a candidate claim unless independently reviewed.
8. Shared themes or dates do not establish causality.
9. Prefer stable external identifiers to fuzzy names.
10. Ingestion must be idempotent.

## Source roles

- **MusicBrainz**: artists, groups, release groups, releases, recordings, works, relationships.
- **Wikidata**: structured person/family/place/date identifiers.
- **Discogs**: edition-level releases, printed personnel and production credits.
- **Spotify**: current track/album IDs, URIs and external URLs.
- **Billboard / Official Charts / archives**: historical chart observations.
- **TMDB**: canonical movie/TV/episode identity and metadata; not assumed to be a complete soundtrack source.
- **Screen-music evidence sources**: recording/work appearances in films and TV episodes.
- **Biographies/interviews/obituaries/liner notes/journalism**: narrative life events and claims.
- **Manual/LLM analysis**: candidate themes, links and research notes.

Do not silently flatten conflicts between sources.

## Standard refresh

1. Read `config/artists.yml`, `config/focus-albums.yml`, `config/sources.yml`.
2. Fetch/cache raw source material.
3. Normalize.
4. Resolve entities across sources.
5. Write provenance.
6. Validate.
7. Build dashboard-facing outputs.
8. Render Quarto.

## Artist additions

Follow `skills/add-artist/SKILL.md`.

Never add artist-specific columns or one-off tables.

## Focus-album additions

Follow `skills/add-focus-album/SKILL.md`.

Focus status is data/configuration, not schema.

## New source additions

Follow `skills/add-data-source/SKILL.md`.

Every source adapter must document:
- access/licensing constraints;
- credentials and rate limits;
- cache behavior;
- stable IDs;
- target tables;
- provenance;
- limitations.

## Code rules

- Python 3.12+.
- Public functions use type hints.
- Source adapters contain no dashboard formatting.
- Schema changes live in `src/music_life/schema.sql`.
- Keep secrets out of git.
- Tests/validation should use local fixtures/demo data, not live APIs.
- Prefer DuckDB SQL for analytical joins/aggregations.

## Dashboard must eventually answer

- Who is this artist?
- What happened across their life/career?
- What is the focus album and who made it?
- What did this artist contribute to outside their own billing?
- How did focus albums/tracks chart?
- What else was popular in the same chart windows?
- Which recordings/works have documented film or TV appearances, including exact episodes where possible?
- What Spotify album/track corresponds to the historical entity?
- What is sourced fact vs published interpretation vs project-derived analysis?

## Data bundles and branches

- Curated data produced by the skills is stored as Parquet, one bundle per focus album: `data/curated/<artist-slug>/<album-slug>/`. A Parquet file holds one table, so a bundle is a folder with one file per table (`sources`, `artist`, `album`, `tracks`, optional `credits`).
- Table specs live in `src/music_life/bundles.py`. Write bundles only through `write_bundle()`, which fixes column types and row order so re-running a skill on unchanged data produces identical files.
- Bundle rows use natural keys (slugs, disc/track numbers, `source_key`), never database IDs. `scripts/build_db.py` rebuilds DuckDB from scratch and assigns IDs.
- Research each focus album on its own branch named `<artist-slug>/<album-slug>` (for example `gerry-rafferty/city-to-city`). Commit that album's bundle, chapter and config entries there.
- Merge data branches into `main` with **squash merge only**, then delete the branch, so each bundle lands on `main` as one version instead of every intermediate re-write from the data digging.
- Never commit bundle Parquet files directly on `main`.

## Dashboard (Quarto book)

- The site accompanies the podcast *Tónlistararfurinn: Plötuklúbbur Inga*; visible text is Icelandic, code and docs are English.
- Parts are decades and chapters are focus albums. `scripts/build_book.py` generates both from `config/focus-albums.yml` and rewrites the marked chapter block in `dashboard/_quarto.yml`; never edit that block by hand.
- Decade and chapter files are created once and then hand-edited (talking points live in `dashboard/albums/<slug>.qmd`). The script never overwrites them.
- Chapter data blocks come from `dashboard/_chapter.qmd` and `music_life.dashboard`; keep queries there, not in chapter files.
- The intro placeholder about the origin of the album list is Birna's to write. Do not write, infer or research anything about her family's personal circumstances anywhere in this repo.

## Before committing

```bash
pytest -m "not live"
python scripts/build_db.py
python scripts/validate.py
python scripts/build_book.py
quarto render dashboard
```

Do not commit credentials, `.env`, large raw caches or local DuckDB files.

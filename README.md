# Music Life Dashboard

Reusable research repo for artist- and album-centred music biographies.

**Pilot:** Gerry Rafferty  
**First focus album:** *City to City* (1978)

The design supports additional artists and focus albums without schema changes.

## Stack

- **DuckDB** — analytical datastore
- **Python** — ingestion, caching, normalization, entity resolution, enrichment
- **Quarto** — dashboard/site
- **GitHub Actions** — validation, rendering and GitHub Pages deployment

## Research layers

1. **Music graph** — artists, groups, release groups/albums, releases, recordings, works, credits, collaborators.
2. **Biography** — sourced life events, family, places, career events and documented personal history.
3. **Historical charts** — full weekly chart snapshots where possible, so a focus track can be placed among everything else popular at the time.
4. **Spotify enrichment** — current album/track URLs for focus material and confidently matched chart songs.
5. **Screen use** — source-backed film/TV/episode appearances, with TMDB/IMDb identity separated from soundtrack evidence.
6. **Analysis** — themes, networks, contextual comparisons and candidate claims, always distinguished from source-backed facts.

## Layout

```text
.
├── AGENTS.md
├── config/
│   ├── artists.yml
│   ├── focus-albums.yml
│   └── sources.yml
├── data/
│   ├── raw/
│   ├── curated/
│   └── processed/
├── dashboard/
├── scripts/
├── skills/
│   ├── add-artist/
│   ├── add-focus-album/
│   └── add-data-source/
├── src/music_life/
└── .github/workflows/
```

## Local setup

Requires Python 3.12+ and Quarto.

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e .
python scripts/init_db.py
python scripts/build_demo_data.py
python scripts/validate.py
quarto preview dashboard
```

Windows PowerShell activation:

```powershell
.venv\Scripts\Activate.ps1
```

## API keys

Copy `.env.example` to `.env` and fill in the keys. `.env` is git-ignored and must never be committed.

| Variable | Where to get it |
|---|---|
| `DISCOGS_TOKEN` | discogs.com → Settings → Developers → Generate new token |
| `SPOTIFY_CLIENT_ID` / `SPOTIFY_CLIENT_SECRET` | developer.spotify.com → Dashboard → your app → Settings |
| `TMDB_API_TOKEN` | themoviedb.org → Settings → API → **API Read Access Token** |

### Syncing `.env` to GitHub Actions secrets

`.env` is the source of truth. To push its values to the repository's Actions secrets:

```bash
gh secret set -f .env -R tungufoss/musikisur
```

This is **one-way** (`.env` → GitHub) and overwrites existing secrets with the same names, so only run it when `.env` is filled in. GitHub secrets are write-only: they cannot be read back, so they cannot be used to recreate a lost `.env` — get the values from the providers again instead.

## GitHub Pages

The workflow in `.github/workflows/quarto-pages.yml` installs Python and Quarto, builds the DuckDB file, renders `dashboard/`, uploads `_site`, and deploys to GitHub Pages.

In GitHub, set:

**Settings → Pages → Source → GitHub Actions**

## Pilot questions

For Gerry Rafferty / *City to City*:

- Who wrote, performed on and produced the album?
- What other recordings did Rafferty write, produce or perform on that were not primarily "his" releases?
- How did the album and singles move through historical charts?
- What else was popular during those same weeks?
- How did US and UK chart context differ?
- Which songs later appeared in movies or specific TV episodes?
- What major documented life/career events overlap the period?
- Which interpretations are source-backed, and which are project-derived?
- Can the historical album/recording be linked to the best current Spotify representation?

## Data principles

- MusicBrainz is the canonical music-identity backbone where possible.
- Spotify is a listening/navigation enrichment, not the historical authority.
- Keep **work**, **recording**, **album/release group**, and **release/edition** distinct.
- Credits are relationships/rows, not fixed producer/songwriter columns.
- Preserve full chart weeks where possible rather than only the focus artist.
- Personal-life claims require provenance.
- LLM/ad-hoc extraction creates candidate claims unless reviewed.
- Do not infer causality from thematic or temporal overlap.

See `AGENTS.md` and the `skills/` directory for extension instructions.


For screen-use extensions, see `skills/add-screen-source/SKILL.md`.

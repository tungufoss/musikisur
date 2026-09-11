"""Helpers for the Quarto book.

The chapter list comes from config (decades become parts, focus albums become chapters).
Data blocks are read from DuckDB and returned as Markdown, so pages can print them from
an ``output: asis`` cell. Visible text is Icelandic because the site is.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import duckdb
import pandas as pd
import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
DB_PATH = REPO_ROOT / "data" / "processed" / "music_life.duckdb"
CONFIG_DIR = REPO_ROOT / "config"

DECADE_NAMES = {
    1950: "Sjötti áratugurinn",
    1960: "Sjöundi áratugurinn",
    1970: "Áttundi áratugurinn",
    1980: "Níundi áratugurinn",
    1990: "Tíundi áratugurinn",
}
MONTHS = [
    "janúar", "febrúar", "mars", "apríl", "maí", "júní",
    "júlí", "ágúst", "september", "október", "nóvember", "desember",
]


@dataclass(frozen=True)
class Chapter:
    slug: str
    title: str
    year: int
    artist_slug: str
    artist_name: str

    @property
    def decade(self) -> int:
        return self.year // 10 * 10

    @property
    def path(self) -> str:
        return f"albums/{self.slug}.qmd"

    @property
    def heading(self) -> str:
        return f"{self.artist_name} – *{self.title}* ({self.year})"


def _read_yaml(name: str) -> dict[str, Any]:
    return yaml.safe_load((CONFIG_DIR / name).read_text(encoding="utf-8")) or {}


def load_chapters() -> list[Chapter]:
    """Focus albums from config, ordered by release year."""
    artists = {a["slug"]: a["name"] for a in _read_yaml("artists.yml").get("artists", [])}
    chapters = [
        Chapter(
            slug=album["slug"],
            title=album["title"],
            year=int(album["original_year"]),
            artist_slug=album["artist"],
            artist_name=artists.get(album["artist"], album["artist"]),
        )
        for album in _read_yaml("focus-albums.yml").get("focus_albums", [])
    ]
    return sorted(chapters, key=lambda c: (c.year, c.artist_name, c.title))


def decade_label(decade: int) -> str:
    years = f"{decade}–{decade + 9}"
    name = DECADE_NAMES.get(decade)
    return f"{years} · {name}" if name else years


def this_year() -> int:
    return datetime.now(UTC).year


def format_date(value: Any) -> str:
    return f"{value.day}. {MONTHS[value.month - 1]} {value.year}"


def connect_ro() -> duckdb.DuckDBPyConnection:
    return duckdb.connect(str(DB_PATH), read_only=True)


def _cell(value: Any) -> str:
    try:
        missing = pd.isna(value)
    except (TypeError, ValueError):
        missing = False
    if missing is True or value is None:
        return "—"
    return str(value).replace("|", "\\|")


def md_table(rows: pd.DataFrame, headers: dict[str, str]) -> str:
    """Render the given columns as a Markdown table; ``headers`` maps column -> label."""
    lines = [
        "| " + " | ".join(headers.values()) + " |",
        "|" + "---|" * len(headers),
    ]
    for _, row in rows.iterrows():
        lines.append("| " + " | ".join(_cell(row[col]) for col in headers) + " |")
    return "\n".join(lines) + "\n"


def demo_notice() -> str:
    """Warn while the database holds only build-test rows (no provenance recorded yet)."""
    with connect_ro() as con:
        sourced = con.execute("SELECT count(*) FROM sources").fetchone()[0]
    if sourced:
        return ""
    return (
        "::: {.callout-warning}\n"
        "## Prufugögn\n"
        "Gögnin hér eru prufugögn til að prófa uppsetninguna, ekki staðfestar heimildir.\n"
        ":::\n"
    )


def list_overview() -> str:
    chapters = load_chapters()
    if not chapters:
        return "*Listinn er tómur enn.*\n"
    decades = sorted({c.decade for c in chapters})
    oldest, newest = chapters[0], chapters[-1]
    average_age = this_year() - sum(c.year for c in chapters) / len(chapters)
    lines = [
        f"- **Plötur:** {len(chapters)}",
        f"- **Flytjendur:** {len({c.artist_slug for c in chapters})}",
        f"- **Áratugir:** {len(decades)} ({decades[0]}–{decades[-1] + 9})",
        f"- **Elsta plata:** {oldest.heading}",
        f"- **Nýjasta plata:** {newest.heading}",
        f"- **Meðalaldur platnanna í dag:** {average_age:.0f} ár",
    ]
    return "\n".join(lines) + "\n\n*Tölurnar uppfærast sjálfkrafa þegar plötum er bætt á listann.*\n"


def decade_overview(decade: int) -> str:
    chapters = [c for c in load_chapters() if c.decade == decade]
    if not chapters:
        return "*Engar plötur af listanum frá þessum áratug.*\n"
    lines = [f"Plötur af listanum frá þessum áratug: **{len(chapters)}**", ""]
    lines += [f"- [{c.artist_name} – *{c.title}*](../{c.path}) ({c.year})" for c in chapters]
    return "\n".join(lines) + "\n"


def album_facts(slug: str) -> str:
    with connect_ro() as con:
        row = con.execute(
            """
            SELECT a.title, ar.name, a.original_release_date, a.spotify_url,
                   (SELECT count(*) FROM album_tracks t WHERE t.album_id = a.album_id)
            FROM albums a
            LEFT JOIN artists ar USING (artist_id)
            WHERE a.slug = ?
            """,
            [slug],
        ).fetchone()
    if row is None:
        return "*Platan er ekki enn komin í gagnagrunninn.*\n"
    title, artist, released, spotify_url, track_count = row
    lines = [f"- **Flytjandi:** {artist or '—'}"]
    if released:
        lines.append(f"- **Útgáfuár:** {released.year}")
        lines.append(f"- **Aldur í dag:** {this_year() - released.year} ár")
    lines.append(f"- **Lög skráð:** {track_count}")
    if spotify_url:
        lines.append(f"- **Spotify:** [{title}]({spotify_url})")
    return "\n".join(lines) + "\n"


def tracklist(slug: str) -> str:
    with connect_ro() as con:
        tracks = con.execute(
            """
            SELECT t.disc_number, t.track_number, t.track_title, r.spotify_url
            FROM album_tracks t
            JOIN albums a USING (album_id)
            LEFT JOIN recordings r USING (recording_id)
            WHERE a.slug = ?
            ORDER BY t.disc_number, t.track_number
            """,
            [slug],
        ).df()
    if tracks.empty:
        return "*Lagalisti ekki kominn enn.*\n"
    multi_disc = tracks["disc_number"].nunique() > 1
    tracks["nr"] = [
        f"{d}.{t}" if multi_disc else str(t)
        for d, t in zip(tracks["disc_number"], tracks["track_number"])
    ]
    tracks["spotify"] = [f"[▶]({url})" if isinstance(url, str) else None for url in tracks["spotify_url"]]
    return md_table(tracks, {"nr": "Nr.", "track_title": "Lag", "spotify": "Spotify"})


def chart_context(slug: str, window: int = 5) -> str:
    """Chart runs for the album's tracks plus the full chart around their best week."""
    with connect_ro() as con:
        hits = con.execute(
            """
            WITH album AS (
                SELECT a.album_id, a.title, ar.name AS artist
                FROM albums a LEFT JOIN artists ar USING (artist_id)
                WHERE a.slug = $slug
            ), tracks AS (
                SELECT t.recording_id, lower(t.track_title) AS title
                FROM album_tracks t JOIN album USING (album_id)
            )
            SELECT ce.chart_id, c.name AS chart, ce.chart_date, ce.position, ce.title,
                   ce.album_id IS NULL AND ce.recording_id IS NULL AS text_match
            FROM chart_entries ce
            JOIN charts c USING (chart_id)
            CROSS JOIN album
            WHERE ce.album_id = album.album_id
               OR ce.recording_id IN (SELECT recording_id FROM tracks)
               OR (lower(ce.artist_name) = lower(album.artist)
                   AND (lower(ce.title) IN (SELECT title FROM tracks)
                        OR (c.chart_type = 'albums' AND lower(ce.title) = lower(album.title))))
            """,
            {"slug": slug},
        ).df()
        if hits.empty:
            return "*Engar færslur á vinsældalistum enn.*\n"

        peak = hits.sort_values(["position", "chart_date"]).iloc[0]
        week = con.execute(
            """
            SELECT position, artist_name, title
            FROM chart_entries
            WHERE chart_id = ? AND chart_date = ? AND position BETWEEN ? AND ?
            ORDER BY position
            """,
            [
                int(peak["chart_id"]),
                peak["chart_date"].date(),
                max(1, int(peak["position"]) - window),
                int(peak["position"]) + window,
            ],
        ).df()

    runs = (
        hits.groupby(["chart", "title"])
        .agg(best=("position", "min"), weeks=("chart_date", "nunique"), first=("chart_date", "min"))
        .reset_index()
        .sort_values(["best", "first"])
    )
    runs["first"] = runs["first"].map(format_date)

    own = set(
        hits.loc[
            (hits["chart_id"] == peak["chart_id"]) & (hits["chart_date"] == peak["chart_date"]),
            "position",
        ]
    )
    for col in ["position", "artist_name", "title"]:
        week[col] = [
            f"**{value}**" if pos in own else value
            for pos, value in zip(week["position"], week[col])
        ]

    parts = [
        "### Gengi á listum\n",
        md_table(runs, {"chart": "Listi", "title": "Lag", "best": "Besta sæti",
                        "weeks": "Vikur", "first": "Fyrsta vika"}),
        "\n*Vikur = vikur sem eru skráðar í gagnagrunninn, ekki endilega allur ferillinn.*\n",
        "\n### Hvað annað var vinsælt?\n",
        (
            f"{peak['chart']}, vikuna {format_date(peak['chart_date'])}, þegar "
            f"*{peak['title']}* var í {int(peak['position'])}. sæti:\n\n"
        ),
        md_table(week, {"position": "Sæti", "artist_name": "Flytjandi", "title": "Lag"}),
    ]
    if hits["text_match"].any():
        parts.append(
            "\n*Sumar færslur eru paraðar við plötuna eftir nafni flytjanda og lags, "
            "þar sem auðkenni vantar.*\n"
        )
    return "".join(parts)


def screen_use(slug: str) -> str:
    with connect_ro() as con:
        usage = con.execute(
            """
            SELECT s.recording_title, s.appearances, s.movies, s.tv_episodes,
                   year(s.earliest_screen_date) AS first_year,
                   year(s.latest_screen_date) AS last_year
            FROM screen_usage_summary s
            JOIN album_tracks t USING (recording_id)
            JOIN albums a USING (album_id)
            WHERE a.slug = ? AND s.appearances > 0
            ORDER BY s.appearances DESC, s.recording_title
            """,
            [slug],
        ).df()
    if usage.empty:
        return "*Engin skráð notkun í kvikmyndum eða sjónvarpi enn.*\n"
    return md_table(usage, {
        "recording_title": "Lag", "appearances": "Skipti", "movies": "Kvikmyndir",
        "tv_episodes": "Sjónvarpsþættir", "first_year": "Fyrst", "last_year": "Síðast",
    })

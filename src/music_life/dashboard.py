"""Helpers for the Quarto book.

The chapter list comes from config (decades become parts, focus albums become chapters).
Data blocks are read from DuckDB and returned as Markdown, so pages can print them from
an ``output: asis`` cell. Visible text is Icelandic because the site is.
"""
from __future__ import annotations

import html
from dataclasses import dataclass
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

import duckdb
import pandas as pd
import yaml

from .sources.musicbrainz import song_key

REPO_ROOT = Path(__file__).resolve().parents[2]
DB_PATH = REPO_ROOT / "data" / "processed" / "music_life.duckdb"
CONFIG_DIR = REPO_ROOT / "config"
COVERS_DIR = REPO_ROOT / "dashboard" / "assets" / "covers"
ARTISTS_DIR = REPO_ROOT / "dashboard" / "assets" / "artists"

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
    ages = release_ages()
    if ages:
        average = f"{sum(ages) / len(ages):.1f}".replace(".", ",")
        albums = "1 plata" if len(ages) == 1 else f"{len(ages)} plötur"
        lines.append(
            f"- **Meðalaldur flytjenda við útgáfu:** {average} ár "
            f"(reiknað úr fæðingardegi og útgáfudegi, {albums})"
        )
    return "\n".join(lines) + "\n\n*Tölurnar uppfærast sjálfkrafa þegar plötum er bætt á listann.*\n"


def decade_overview(decade: int) -> str:
    chapters = [c for c in load_chapters() if c.decade == decade]
    if not chapters:
        return "*Engar plötur af listanum frá þessum áratug.*\n"
    lines = [f"Plötur af listanum frá þessum áratug: **{len(chapters)}**", ""]
    lines += [f"- [{c.artist_name} – *{c.title}*](../{c.path}) ({c.year})" for c in chapters]
    return "\n".join(lines) + "\n"


def spotify_link(url: str, text: str = "") -> str:
    """Spotify icon (Bootstrap Icons, bundled with Quarto) linking to ``url``, optionally with text.

    On the site a click opens Spotify's compact player on the page instead of leaving it
    (dashboard/_spotify-inline.html); without JavaScript it stays a plain link.
    """
    icon = '<i class="bi bi-spotify spotify-icon" aria-hidden="true"></i>'
    label = text or "Hlusta á Spotify"
    embed = ""
    if "open.spotify.com/" in url and "/embed/" not in url:
        embed = f' data-spotify-embed="{url.replace("open.spotify.com/", "open.spotify.com/embed/", 1)}" aria-expanded="false"'
    return (
        f'<a href="{url}" class="spotify-link"{embed} title="Hlusta á Spotify" aria-label="{label}">'
        f'{icon}{" " + text if text else ""}</a>'
    )


def age_at_release(born: date, released: date | None, year: int) -> int:
    """Age on the release date; when only the year is known, on the first day of that year."""
    when = released or date(year, 1, 1)
    return when.year - born.year - ((when.month, when.day) < (born.month, born.day))


def release_ages() -> list[float]:
    """Artist age at release for every focus album whose artist has a known birth date."""
    years = {c.slug: c.year for c in load_chapters()}
    with connect_ro() as con:
        rows = con.execute(
            """
            SELECT a.slug, a.original_release_date, ar.birth_date
            FROM albums a JOIN artists ar USING (artist_id)
            WHERE a.is_focus_album AND ar.birth_date IS NOT NULL
            """
        ).fetchall()
    return [
        age_at_release(born, released, released.year if released else years[slug])
        for slug, released, born in rows
        if released or slug in years
    ]


def _weeks(count: int) -> str:
    """Icelandic agreement: singular after numbers ending in 1 (but not 11), e.g. 1 vika, 21 vika."""
    return f"{count} {'vika' if count % 10 == 1 and count % 100 != 11 else 'vikur'}"


def _songs(count: int, total: int | None = None) -> str:
    if total and count == total:
        return "öll lögin"
    return "1 lag" if count == 1 else f"{count} lög"


def album_facts(slug: str) -> str:
    with connect_ro() as con:
        row = con.execute(
            """
            SELECT a.title, ar.name, a.original_release_date, a.spotify_url,
                   count(t.track_number), sum(r.duration_ms), ar.birth_date, ar.slug
            FROM albums a
            LEFT JOIN artists ar USING (artist_id)
            LEFT JOIN album_tracks t USING (album_id)
            LEFT JOIN recordings r ON r.recording_id = t.recording_id
            WHERE a.slug = ?
            GROUP BY ALL
            """,
            [slug],
        ).fetchone()
    if row is None:
        return "*Platan er ekki enn komin í gagnagrunninn.*\n"
    title, artist, released, spotify_url, track_count, duration_ms, born, artist_slug = row
    # MusicBrainz often only knows the year; fall back to the year in config.
    year = released.year if released else next((c.year for c in load_chapters() if c.slug == slug), None)
    # Chapters live in albums/, so the artist page is one directory up.
    artist_link = f'<a href="../artists/{artist_slug}.html">{html.escape(artist)}</a>' if artist else ""
    boxes = [_fact_box("Flytjandi", artist or "—", value_html=artist_link)]
    if year:
        age = this_year() - year
        ago = f"fyrir {age} {'ári' if age % 10 == 1 and age % 100 != 11 else 'árum'}"
        boxes.append(_fact_box("Útgáfudagur", format_date(released), ago) if released
                     else _fact_box("Útgáfuár", year, ago))
    if born and year:
        boxes.append(_fact_box("Aldur flytjanda", f"{age_at_release(born, released, year)} ára", "við útgáfu"))
    boxes.append(_fact_box("Lög", track_count))
    if duration_ms:
        boxes.append(_fact_box("Lengd", f"{duration_ms / 60000:.0f} mín.", "lágmarkshlustun fyrir virkan klúbbmeðlim"))
    if spotify_url:
        boxes.append(_fact_box("Hlusta", title, "smelltu til að spila hér", "fact-spotify",
                               value_html=spotify_link(spotify_url, html.escape(title))))
    return '```{=html}\n<div class="fact-boxes">' + "".join(boxes) + "</div>\n```\n"


def album_cover(slug: str) -> str:
    """The album cover with its credit, floated right so the chapter's opening text wraps around it."""
    if not (COVERS_DIR / f"{slug}.jpg").exists():
        return ""
    with connect_ro() as con:
        found = con.execute("SELECT title FROM albums WHERE slug = ?", [slug]).fetchone()
        source = _image_source(con, slug, "coverart-front")
    title = found[0] if found else slug
    credit = (f'Umslag: <a href="{html.escape(source[0])}">Cover Art Archive</a>; höfundarréttur hjá rétthöfum'
              if source else "Umslag")
    # Chapters live in albums/, so the cover is one directory up.
    return ("```{=html}\n"
            f'<figure class="album-cover"><img src="../assets/covers/{slug}.jpg" '
            f'alt="Umslag plötunnar {html.escape(title)}"><figcaption>{credit}</figcaption></figure>\n'
            "```\n")


def _image_source(con: duckdb.DuckDBPyConnection, slug: str, source_key: str) -> tuple[str, str] | None:
    """URL and citation of an image source recorded in the album's bundle."""
    return con.execute(
        """
        SELECT s.source_url, s.citation_text
        FROM albums a JOIN artists ar USING (artist_id)
        JOIN sources s ON s.raw_reference = ar.slug || '/' || a.slug || ':' || ?
        WHERE a.slug = ?
        """,
        [source_key, slug],
    ).fetchone()


TAG_TITLES = {"genre": "Stefna", "instrument": "Hljóðfæri", "occupation": "Störf"}
# Icelandic for common Wikidata labels that lack an Icelandic label.
LABEL_FALLBACK_IS = {"voice": "rödd", "recording artist": "hljóðritunarlistamaður", "liver failure": "lifrarbilun"}
AGE_WORD = {"Q6581097": "gamall", "Q6581072": "gömul"}  # Wikidata sex: male, female
PLACE_STYLES = {  # role: (marker colour, Font Awesome icon, description); egg and dove as on the timeline
    "birth": ("green", "egg", "Fæðingarstaður"),
    "death": ("black", "dove", "Dánarstaður"),
    "residence": ("orange", "home", "Búseta"),
    "mentioned": ("#2780e3", None, "Nefndur í Wikipedia-greininni"),
}
TIMELINE_LANES = {  # px from top
    "life": 18, "career": 46, "album": 76, "chart": 106, "cover": 136, "hist": 191, "screen": 250,
}
LANE_TITLES = {
    "life": "Ævi", "career": "Ferill", "album": "Plötur", "chart": "Billboard",
    "cover": "Ábreiður", "hist": "Ný lög á ári", "screen": "Myndir og þættir",
}
SCREEN_HEIGHT = 36  # the film and TV lane: a cumulative line
HIST_BOTTOM, HIST_HEIGHT = 216, 50
# The yearly columns count songs: new songs in the artist's own name or a band's, and
# recordings for other artists.
HIST_GROUPS = {"song": "song", "production": "others", "guest": "others"}
HIST_COLORS = {"solo": "#2780e3", "others": "#fd7e14"}
# Billboard year cells: one blue hue, light to dark by the year's best position.
CHART_SHADES = [(10, "#1b4f9c"), (40, "#4a86d0"), (100, "#9dc0ea"), (200, "#d6e6f8")]
# One colour per band, in order of the band's first release.
BAND_PALETTE = ["#6f42c1", "#198754", "#d63384", "#0dcaf0", "#795548", "#6c757d"]


def _artist(con: duckdb.DuckDBPyConnection, artist_slug: str) -> tuple[int, str, str] | None:
    """(artist_id, name, slug)."""
    return con.execute("SELECT artist_id, name, slug FROM artists WHERE slug = ?", [artist_slug]).fetchone()


def _focus_groups(con: duckdb.DuckDBPyConnection, artist_id: int) -> dict[str, str]:
    """Release group ID -> album slug for the artist's albums that have a chapter."""
    return dict(con.execute(
        """
        SELECT musicbrainz_release_group_id, slug FROM albums
        WHERE artist_id = ? AND is_focus_album AND musicbrainz_release_group_id IS NOT NULL
        """,
        [artist_id],
    ).fetchall())


def _chart_runs(con: duckdb.DuckDBPyConnection, performers: list[str]) -> list[tuple]:
    """(chart, chart type, performer, title, first week, last week, best position, weeks, run number)
    for every song or album credited to one of the performers (exact chart credit, case-insensitive).
    A new run starts after more than four weeks off the chart, so re-entries are runs of their own
    (run number 0 is the first run)."""
    if not performers:
        return []
    marks = ", ".join("?" for _ in performers)
    return con.execute(
        f"""
        WITH weeks AS (
            SELECT c.name AS chart, c.chart_type, ce.artist_name, ce.title, ce.chart_date, ce.position,
                   CASE WHEN ce.chart_date - lag(ce.chart_date) OVER w > 28 THEN 1 ELSE 0 END AS new_run
            FROM chart_entries ce JOIN charts c USING (chart_id)
            WHERE lower(ce.artist_name) IN ({marks})
            WINDOW w AS (PARTITION BY c.name, ce.artist_name, ce.title ORDER BY ce.chart_date)
        ), runs AS (
            SELECT *, sum(new_run) OVER (
                PARTITION BY chart, artist_name, title ORDER BY chart_date
            ) AS run_number FROM weeks
        )
        SELECT chart, chart_type, artist_name, title, min(chart_date), max(chart_date),
               min(position), count(DISTINCT chart_date), run_number
        FROM runs
        GROUP BY chart, chart_type, artist_name, title, run_number
        ORDER BY min(chart_date)
        """,
        [p.lower() for p in performers],
    ).fetchall()


def _chart_weeks(con: duckdb.DuckDBPyConnection, performers: list[str]) -> pd.DataFrame:
    """Every charting week for the performers: chart, performer, title, date, position, run number
    (a new run after more than four weeks off the chart) and week number within the run."""
    if not performers:
        return pd.DataFrame()
    marks = ", ".join("?" for _ in performers)
    return con.execute(
        f"""
        WITH weeks AS (
            SELECT c.name AS chart, c.chart_type, ce.artist_name AS performer, ce.title,
                   ce.chart_date, ce.position,
                   CASE WHEN ce.chart_date - lag(ce.chart_date) OVER w > 28 THEN 1 ELSE 0 END AS new_run
            FROM chart_entries ce JOIN charts c USING (chart_id)
            WHERE lower(ce.artist_name) IN ({marks})
            WINDOW w AS (PARTITION BY c.name, ce.artist_name, ce.title ORDER BY ce.chart_date)
        ), runs AS (
            SELECT *, sum(new_run) OVER (PARTITION BY chart, performer, title ORDER BY chart_date) AS run
            FROM weeks
        )
        SELECT chart, chart_type, performer, title, chart_date, position, run,
               row_number() OVER (PARTITION BY chart, performer, title, run ORDER BY chart_date) AS week
        FROM runs ORDER BY chart_date
        """,
        [p.lower() for p in performers],
    ).df()


def _performers(name: str, events: list[tuple]) -> list[str]:
    """The artist's own name plus every band they joined."""
    return [name, *sorted({label for kind, _, _, label, *_ in events if kind == "band_join"})]


def _artist_photo(con: duckdb.DuckDBPyConnection, artist_slug: str) -> tuple[str, str] | None:
    """URL and citation of the artist photo recorded in any of the artist's bundles."""
    return con.execute(
        "SELECT source_url, citation_text FROM sources WHERE raw_reference LIKE ? ORDER BY source_id LIMIT 1",
        [f"{artist_slug}/%:commons-artist-photo"],
    ).fetchone()


def _events(con: duckdb.DuckDBPyConnection, artist_id: int) -> list[tuple]:
    return con.execute(
        """
        SELECT kind, event_date, coalesce(date_precision, 11), label, detail, url
        FROM timeline_events WHERE artist_id = ? ORDER BY event_date, label
        """,
        [artist_id],
    ).fetchall()


def _when(value: date, precision: int) -> str:
    if precision >= 11:
        return format_date(value)
    return f"{MONTHS[value.month - 1]} {value.year}" if precision == 10 else str(value.year)


def _years_between(start: date, end: date) -> int:
    return end.year - start.year - ((end.month, end.day) < (start.month, start.day))


def _gap(previous: tuple[date, int] | None, current: tuple[date, int]) -> str:
    """Time since the previous release, from (date, precision) pairs: months when both dates
    know the month (whole years from two years on), otherwise whole years marked with "~"."""
    if previous is None:
        return "—"
    (before, before_precision), (after, after_precision) = previous, current
    if min(before_precision, after_precision) < 10:
        years = after.year - before.year
        return "sama ár" if years == 0 else f"~{years} ár"
    months = (after.year - before.year) * 12 + after.month - before.month
    if months == 0:
        return "sama mánuð"
    return f"{months} mán." if months < 24 else f"{round(months / 12)} ár"


def _age_text(born: date, value: date) -> str:
    """Age on a stored date; dates known only to the year or month are stored as their first day."""
    return str(age_at_release(born, value, value.year))


def artist_photo(artist_slug: str) -> str:
    """The artist's photo with its credit, floated to the right of the page's opening summary."""
    with connect_ro() as con:
        found = _artist(con, artist_slug)
        photo = _artist_photo(con, artist_slug) if found else None
    if not photo or not (ARTISTS_DIR / f"{artist_slug}.jpg").exists():
        return ""
    # Artist pages live in artists/, so assets are one directory up.
    return ("```{=html}\n"
            f'<figure class="artist-photo"><img src="../assets/artists/{artist_slug}.jpg" alt="{html.escape(found[1])}">'
            f'<figcaption>Mynd: <a href="{html.escape(photo[0])}">{html.escape(photo[1])}</a>, '
            "Wikimedia Commons</figcaption></figure>\n```\n")


def _fact_box(
    label: str, value: object, sub: str = "", css: str = "", title: str = "", value_html: str = ""
) -> str:
    """One dashboard box; ``value_html`` (trusted markup such as a link) replaces the escaped value."""
    tip = f' title="{html.escape(title)}"' if title else ""
    return (f'<div class="fact-box {css}"{tip}><div class="fact-label">{label}</div>'
            f'<div class="fact-value">{value_html or html.escape(str(value))}</div>'
            f'<div class="fact-sub">{html.escape(sub)}</div></div>')


def artist_facts(artist_slug: str) -> str:
    """Birth, death, career, albums, songs and nominations as dashboard-style boxes."""
    with connect_ro() as con:
        found = _artist(con, artist_slug)
        if not found:
            return ""
        places = {
            role: ", ".join(filter(None, (name, country)))
            for role, name, country in con.execute(
                """
                SELECT role, coalesce(label_is, title), country FROM artist_places
                WHERE artist_id = ? AND role IN ('birth', 'death')
                """,
                [found[0]],
            ).fetchall()
        }
        events = _events(con, found[0])
        chart_runs = _chart_runs(con, _performers(found[1], events))
        sex = con.execute(
            "SELECT qid FROM artist_tags WHERE artist_id = ? AND kind = 'sex'", [found[0]]
        ).fetchone()
    first = {}
    for kind, when, precision, _, detail, _ in events:
        first.setdefault(kind, (when, precision, detail))
    born = first.get("birth", (None,))[0]
    died = first.get("death", (None,))[0]

    boxes = []
    if born:
        boxes.append(_fact_box("Fæðing", format_date(born), places.get("birth", "")))
    if died:
        age = f"{age_at_release(born, died, died.year)} ára {AGE_WORD.get(sex[0] if sex else '', '')}".strip() if born else ""
        cause = first["death"][2]
        cause = LABEL_FALLBACK_IS.get(cause, cause) if cause else ""
        details = ", ".join(filter(None, (age, cause)))
        sub = " · ".join(filter(None, (places.get("death", ""), details)))
        boxes.append(_fact_box("Andlát", format_date(died), sub, "fact-death"))
    if "career_start" in first:
        start = first["career_start"][0]
        end = first["career_end"][0] if "career_end" in first else None
        ages = ""
        if born:
            # A career that ends in the year of death ends at the age of death.
            last = (died if died and end and died.year == end.year else end)
            ages = f"frá {_age_text(born, start)} ára" + (f" til {_age_text(born, last)} ára" if last else "")
        boxes.append(_fact_box("Ferill", f"{start.year}–{end.year if end else ''}", ages))
    albums = [when for kind, when, *_ in events if kind == "album"]
    if albums:
        posthumous = sum(1 for when in albums if died and when > died)
        sub = f"{albums[0].year}–{albums[-1].year}" + (f", {posthumous} eftir andlát" if posthumous else "")
        boxes.append(_fact_box("Sólóplötur", len(albums), sub))
    solo = sum(1 for kind, _, _, _, detail, _ in events if kind == "song" and detail == "solo")
    in_bands = sum(1 for kind, _, _, _, detail, _ in events if kind == "song" and detail != "solo")
    for_others = sum(1 for kind, *_ in events if kind in ("production", "guest"))
    if solo or in_bands or for_others:
        split = ", ".join(f"{n} {what}" for n, what in (
            (solo, "í eigin nafni"), (in_bands, "með hljómsveitum"), (for_others, "fyrir aðra")) if n)
        boxes.append(_fact_box("Lög sem hann kom að", solo + in_bands + for_others, split, "fact-songs",
                               "Hvert lag talið einu sinni, árið sem það kom fyrst út (MusicBrainz)"))
    # One box per chart: distinct songs/albums (re-entries merged), best position, weeks in the tooltip.
    for chart, one, many in (("Billboard Hot 100", "lag", "lög"), ("Billboard 200", "plata", "plötur")):
        titles: dict[str, list[int]] = {}
        for run in chart_runs:
            if run[0] == chart:
                best = titles.setdefault(run[3], [run[6], 0])
                best[0], best[1] = min(best[0], run[6]), best[1] + run[7]
        if titles:
            top = min(titles, key=lambda title: titles[title][0])
            count = f"{len(titles)} {one if len(titles) == 1 else many}"
            boxes.append(_fact_box(chart, count, f"besta sæti {titles[top][0]} ({top})", "fact-chart",
                                   "; ".join(f"{t}: {p}. sæti, {_weeks(w)}" for t, (p, w) in titles.items())))
    nominations = [(when, label) for kind, when, _, label, *_ in events if kind == "nomination"]
    if nominations:
        years = ", ".join(str(y) for y in sorted({when.year for when, _ in nominations}))
        awards = ", ".join(sorted({label.split(":")[0] for _, label in nominations}))
        boxes.append(_fact_box("Tilnefningar", len(nominations), f"{awards} {years}", "fact-award",
                               "; ".join(label for _, label in nominations)))
    return '```{=html}\n<div class="fact-boxes">' + "".join(boxes) + "</div>\n```\n" if boxes else ""


def artist_pills(artist_slug: str) -> str:
    """Genres, instruments and occupations from Wikidata as Bootstrap pill badges."""
    with connect_ro() as con:
        found = _artist(con, artist_slug)
        rows = con.execute(
            "SELECT kind, label_is, label_en FROM artist_tags WHERE artist_id = ? ORDER BY kind, label_en",
            [found[0]],
        ).fetchall() if found else []
    groups: dict[str, list[str]] = {}
    for kind, label_is, label_en in rows:
        text = label_is or LABEL_FALLBACK_IS.get(label_en or "", label_en) or ""
        groups.setdefault(kind, []).append(text.lower())
    lines = [
        f'<div class="artist-tags"><span class="tag-title">{TAG_TITLES[kind]}:</span> '
        + " ".join(f'<span class="badge rounded-pill tag-{kind}">{html.escape(t)}</span>' for t in groups[kind])
        + "</div>"
        for kind in TAG_TITLES if kind in groups
    ]
    return "```{=html}\n" + "\n".join(lines) + "\n```\n" if lines else ""


def artist_map(artist_slug: str) -> Any:
    """Leaflet map (folium) of the artist's birth, death and residence places and the places
    Wikipedia mentions, each with its context sentence in the popup."""
    import folium

    with connect_ro() as con:
        places = con.execute(
            """
            SELECT p.role, concat_ws(', ', coalesce(p.label_is, p.title), p.country),
                   p.latitude, p.longitude, p.context
            FROM artist_places p JOIN artists ar USING (artist_id)
            WHERE ar.slug = ? ORDER BY p.role, p.title
            """,
            [artist_slug],
        ).fetchall()
    if not places:
        return None
    # OpenStreetMap tiles need no key; CARTO basemaps now watermark tiles without one (see the API issue).
    fmap = folium.Map(tiles="OpenStreetMap", control_scale=True)
    for role, name, lat, lon, context in places:
        color, icon, what = PLACE_STYLES.get(role, PLACE_STYLES["mentioned"])
        popup = folium.Popup(
            f"<b>{html.escape(name)}</b><br><i>{what}</i>"
            + (f"<br>{html.escape(context)}" if context else ""),
            max_width=300,
        )
        if icon:
            folium.Marker([lat, lon], popup=popup, tooltip=name,
                          icon=folium.Icon(color=color, icon=icon, prefix="fa")).add_to(fmap)
        else:
            folium.CircleMarker([lat, lon], radius=6, color=color, fill=True, fill_opacity=0.7,
                                popup=popup, tooltip=name).add_to(fmap)
    # Frame birth and death: centred between them with both in view. Homes and the places
    # Wikipedia mentions stay reachable by zooming out.
    framed = (
        [(lat, lon) for role, _, lat, lon, _ in places if role in ("birth", "death")]
        or [(lat, lon) for role, _, lat, lon, _ in places if role != "mentioned"]
        or [(lat, lon) for _, _, lat, lon, _ in places]
    )
    lats, lons = [p[0] for p in framed], [p[1] for p in framed]
    # max_zoom keeps one place, or two close together, from filling the map with a few streets.
    fmap.fit_bounds([[min(lats), min(lons)], [max(lats), max(lons)]], padding=(40, 40), max_zoom=8)
    return fmap


def _position(value: date, precision: int) -> float:
    """Position in years; dates known only to the year or month sit mid-period."""
    if precision >= 11:
        return value.year + (value.timetuple().tm_yday - 0.5) / 366
    if precision == 10:
        return value.year + (value.month - 0.5) / 12
    return value.year + 0.5


def artist_timeline(artist_slug: str) -> str:
    """Life, career, releases, work for others and covers on one axis, gridlines every ten years of age."""
    with connect_ro() as con:
        found = _artist(con, artist_slug)
        events = _events(con, found[0]) if found else []
        focus = _focus_groups(con, found[0]) if found else {}
        chart_weeks = _chart_weeks(con, _performers(found[1], events)) if found else pd.DataFrame()
        screen = _screen_credits(con, found[0]) if found else pd.DataFrame()
    by_kind: dict[str, list[tuple]] = {}
    for kind, when, precision, label, detail, url in events:
        by_kind.setdefault(kind, []).append((when, precision, label, detail, url))
    if "birth" not in by_kind:
        return ""
    born = by_kind["birth"][0][0]
    died = by_kind["death"][0][0] if "death" in by_kind else None
    born_at = _position(born, 11)
    start = born_at - 1
    end = max([_position(w, p) for items in by_kind.values() for w, p, *_ in items] + [born_at]) + 2

    def pct(value: float) -> float:
        return (value - start) / (end - start) * 100

    def bar(css: str, lane: str, begin: float, finish: float, title: str) -> str:
        return (f'<div class="tl-bar {css}" style="top:{TIMELINE_LANES[lane]}px;left:{pct(begin):.2f}%;'
                f'width:{pct(finish) - pct(begin):.2f}%" title="{html.escape(title)}"></div>')

    def icon(css: str, lane: str, at: float, title: str, url: str | None = None, offset: int = 0,
             color: str | None = None) -> str:
        colour = f";color:{color}" if color else ""
        tag = (f'<i class="fa-solid {css} tl-icon" style="left:{pct(at):.2f}%;top:{TIMELINE_LANES[lane] + offset}px{colour}" '
               f'title="{html.escape(title)}"></i>')
        return f'<a href="{html.escape(url)}" target="_blank" rel="noopener">{tag}</a>' if url else tag

    parts = []
    for age in range(0, int(end - born_at) + 1, 10):
        parts.append(f'<div class="tl-grid" style="left:{pct(born_at + age):.2f}%">'
                     f'<span>{born.year + age}<br>{age} ára</span></div>')
    lanes = ["life"]
    life_end = _position(died, 11) if died else end - 2
    parts.append(bar("tl-life", "life", born_at, life_end, "Ævi"))
    parts.append(icon("fa-egg", "life", born_at, f"Fæðing {format_date(born)}"))
    if died:
        cause = by_kind["death"][0][3]
        cause = f", {LABEL_FALLBACK_IS.get(cause, cause)}" if cause else ""
        parts.append(icon("fa-dove", "life", life_end,
                          f"Andlát {format_date(died)}, {age_at_release(born, died, died.year)} ára{cause}"))
    # Family on the life line: marriages (pink) and later relationships (light pink) lie over it.
    for start_kind, end_kind, css, what in (("marriage", "divorce", "tl-marriage", "Hjónaband"),
                                            ("relationship", "relationship_end", "tl-partner", "Samband")):
        ends = {name: (when, precision) for when, precision, name, _, _ in by_kind.get(end_kind, [])}
        for when, precision, name, _, _ in by_kind.get(start_kind, []):
            ended = ends.get(name)
            # Without a recorded end it lasts until death (or today).
            last = ended[0].year if ended else died.year if died else ""
            parts.append(bar(css, "life", _position(when, precision), _position(*ended) if ended else life_end,
                             f"{what}: {name}, {when.year}–{last}"))
    for when, precision, child, detail, _ in by_kind.get("child", []):
        # A detail (such as "áætlað: fædd 1970–1977") marks an estimated date: paler icon, range in the tooltip.
        css = "fa-baby tl-child" + (" tl-approx" if detail else "")
        parts.append(icon(css, "life", _position(when, precision),
                          f"{child} fæðist ({detail or _when(when, precision)})", offset=-13))
    if "career_start" in by_kind:
        lanes.append("career")
        first_year = by_kind["career_start"][0][0].year
        last_year = by_kind["career_end"][0][0].year if "career_end" in by_kind else int(end - 2)
        parts.append(bar("tl-career", "career", first_year, last_year + 1, f"Ferill: {first_year}–{last_year}"))
    # Bands: membership periods (join/leave events) and one colour per band, in order of joining.
    joins = {band: when for when, _, band, _, _ in by_kind.get("band_join", [])}
    leaves = {band: when for when, _, band, _, _ in by_kind.get("band_leave", [])}
    band_colors: dict[str, str] = {}
    for band in [*sorted(joins, key=joins.get), *(item[3] for item in by_kind.get("band_album", [])),
                 *(item[3] for item in by_kind.get("song", []) if item[3] != "solo")]:
        band_colors.setdefault(band, BAND_PALETTE[len(band_colors) % len(BAND_PALETTE)])
    # Band albums released while he was in the band sit with his own albums, in the band's colour.
    band_albums = [
        ("band", item) for item in by_kind.get("band_album", [])
        if (item[3] not in joins or item[0] >= joins[item[3]])
        and (item[3] not in leaves or item[0].year <= leaves[item[3]].year)
    ]

    albums = by_kind.get("album", [])
    if albums or band_albums:
        lanes.append("album")
        previous, flip = None, False
        for source, (when, precision, label, detail, url) in sorted(
            [("solo", item) for item in albums] + band_albums, key=lambda pair: pair[1][0]
        ):
            at = _position(when, precision)
            flip = (not flip) if previous is not None and pct(at) - pct(previous) < 2.5 else False
            previous = at
            if source == "band":
                parts.append(icon("fa-compact-disc", "album", at,
                                  f"{_when(when, precision)}: {detail} – {label} ({_age_text(born, when)} ára)",
                                  url, -10 if flip else 0, color=band_colors[detail]))
                continue
            posthumous = died is not None and when > died
            # Albums after death need no colour of their own: the dove already marks the death.
            css = "fa-compact-disc " + ("tl-focus" if detail in focus else "tl-album")
            age = f"{_years_between(died, when)} ár eftir andlát" if posthumous else f"{_age_text(born, when)} ára"
            # Albums with a chapter link to it; the others to MusicBrainz.
            link = f"../albums/{focus[detail]}.html" if detail in focus else url
            parts.append(icon(css, "album", at, f"{_when(when, precision)}: {label} ({age})", link, -10 if flip else 0))
    # Billboard, merged per year: one cell per year on a list, shaded by the best position that
    # year (one hue, darker = higher); the tooltip lists what charted. Details: the Billboard section.
    if not chart_weeks.empty:
        lanes.append("chart")
        per_year = (chart_weeks.assign(year=chart_weeks["chart_date"].dt.year)
                    .groupby(["year", "chart", "title"])
                    .agg(best=("position", "min"), weeks=("chart_date", "nunique"))
                    .reset_index())
        for year, rows in per_year.groupby("year"):
            best = int(rows["best"].min())
            shade = next(colour for limit, colour in CHART_SHADES if best <= limit)
            lines = "; ".join(
                f"{r.title} ({r.chart.replace('Billboard ', '')}, {r.best}. sæti, {_weeks(r.weeks)})"
                for r in rows.sort_values("best").itertuples()
            )
            parts.append(
                f'<div class="tl-bar tl-chart-year" style="top:{TIMELINE_LANES["chart"]}px;left:{pct(year):.2f}%;'
                f'width:{max(pct(year + 1) - pct(year) - 0.15, 0.3):.2f}%;background:{shade}" '
                f'title="{html.escape(f"{year}: {lines}")}"></div>'
            )

    covers = by_kind.get("cover", [])
    if covers:
        lanes.append("cover")
        for when, precision, label, _, url in covers:
            parts.append(icon("fa-rug tl-cover", "cover", _position(when, precision), f"{_when(when, precision)}: {label}", url))

    # Band periods lie over the career bar, in each band's colour.
    if joins:
        for band, joined in joins.items():
            last = leaves[band].year if band in leaves else (died.year if died else joined.year)
            parts.append(
                f'<div class="tl-bar tl-band-period" style="top:{TIMELINE_LANES["career"]}px;left:{pct(joined.year):.2f}%;'
                f'width:{pct(last + 1) - pct(joined.year):.2f}%;background:{band_colors[band]}" '
                f'title="{html.escape(band)}: {joined.year}–{last}"></div>'
            )
    band_legend = "".join(
        f'<span class="tl-key" style="background:{c}"></span> {html.escape(b)} · ' for b, c in band_colors.items()
    )
    band_keys = "".join(
        f'<span class="tl-key" style="background:{c}"></span> með {html.escape(b)}, ' for b, c in band_colors.items()
    )
    for when, precision, label, _, url in by_kind.get("nomination", []) + by_kind.get("award", []):
        parts.append(icon("fa-award tl-award", "career", _position(when, precision),
                          f"{_when(when, precision)}: {label}", url, -14))

    # Songs per year, stacked: new songs in his own name, each band in its colour, for others.
    counts: dict[int, dict[str, int]] = {}
    for kind, base in HIST_GROUPS.items():
        for when, _, _, detail, _ in by_kind.get(kind, []):
            group = ("solo" if detail == "solo" else f"band:{detail}") if base == "song" else base
            counts.setdefault(when.year, {})
            counts[when.year][group] = counts[when.year].get(group, 0) + 1
    stack = ["solo", *(f"band:{b}" for b in band_colors), "others"]
    colors = {**HIST_COLORS, **{f"band:{b}": c for b, c in band_colors.items()}}
    titles = {"solo": "ný lög í eigin nafni", "others": "lög fyrir aðra",
              **{f"band:{b}": f"ný lög með {b}" for b in band_colors}}
    if counts:
        lanes.append("hist")
        peak = max(sum(per.values()) for per in counts.values())
        for year, per_group in sorted(counts.items()):
            top = HIST_BOTTOM
            for group in stack:
                n = per_group.get(group, 0)
                if n:
                    height = n / peak * HIST_HEIGHT
                    top -= height
                    width = max(pct(year + 1) - pct(year) - 0.15, 0.3)
                    parts.append(
                        f'<div class="tl-hist" style="left:{pct(year):.2f}%;width:{width:.2f}%;top:{top:.1f}px;'
                        f'height:{height:.1f}px;background:{colors[group]}" '
                        f'title="{year}: {n} {html.escape(titles[group])}"></div>'
                    )

    # Film and TV: a cumulative line of titles that use the songs (IMDb), each title counted
    # at the first year it used one of them; hover a year for the new titles.
    screen_legend = ""
    if not screen.empty:
        lanes.append("screen")
        top = TIMELINE_LANES["screen"] - SCREEN_HEIGHT / 2
        per_year = screen.groupby("first_year")["title"].apply(list)
        total = sum(len(names) for names in per_year)
        screen_from, screen_to = int(per_year.index.min()), min(this_year(), int(end))

        def height_at(count: int) -> float:
            return SCREEN_HEIGHT - count / total * SCREEN_HEIGHT

        running, points = 0, [(pct(screen_from), height_at(0))]
        for year in range(screen_from, screen_to + 1):
            new = per_year.get(year, [])
            if not new:
                continue
            points.append((pct(year), height_at(running)))
            running += len(new)
            points.append((pct(year), height_at(running)))
            word = "nýr titill" if len(new) % 10 == 1 and len(new) % 100 != 11 else "nýir titlar"
            names = ", ".join(new[:5]) + (" …" if len(new) > 5 else "")
            parts.append(
                f'<div class="tl-screen-hit" style="top:{top}px;height:{SCREEN_HEIGHT}px;left:{pct(year):.2f}%;'
                f'width:{pct(year + 1) - pct(year):.2f}%" '
                f'title="{html.escape(f"{year}: {len(new)} {word} ({names}), alls {running}")}"></div>'
            )
        points.append((pct(screen_to + 1), height_at(running)))
        line = " ".join(f"{x:.2f},{y:.1f}" for x, y in points)
        area = f"{points[0][0]:.2f},{SCREEN_HEIGHT} {line} {points[-1][0]:.2f},{SCREEN_HEIGHT}"
        parts.append(
            f'<svg class="tl-screen" style="top:{top}px;height:{SCREEN_HEIGHT}px" viewBox="0 0 100 {SCREEN_HEIGHT}" '
            f'preserveAspectRatio="none" aria-hidden="true"><polygon class="tl-screen-area" points="{area}"/>'
            f'<polyline class="tl-screen-line" points="{line}" vector-effect="non-scaling-stroke"/></svg>'
            f'<span class="tl-screen-total" style="left:{pct(screen_to + 1):.2f}%;top:{top + height_at(running):.1f}px">'
            f"{total}</span>"
        )
        screen_legend = ('<span class="tl-key tl-screen-key"></span> myndir og þættir sem nota lögin, uppsafnað '
                         "(IMDb; hver titill talinn árið sem hann notaði lag fyrst). ")

    labels = "".join(f'<div style="top:{TIMELINE_LANES[lane]}px">{LANE_TITLES[lane]}</div>' for lane in lanes)
    legend = (
        '<p class="tl-legend"><i class="fa-solid fa-egg"></i> fæðing · <i class="fa-solid fa-dove"></i> andlát · '
        '<span class="tl-key tl-marriage"></span> hjónaband · <span class="tl-key tl-partner"></span> samband · '
        '<i class="fa-solid fa-baby tl-child"></i> barn fæðist · '
        '<span class="tl-key tl-career"></span> ferill · '
        'Billboard: <span class="tl-key" style="background:#d6e6f8"></span><span class="tl-key" style="background:#9dc0ea"></span>'
        '<span class="tl-key" style="background:#4a86d0"></span><span class="tl-key" style="background:#1b4f9c"></span> '
        'besta sæti ársins (dekkra = ofar; nánar í Billboard-hlutanum) · '
        '<i class="fa-solid fa-compact-disc tl-album"></i> hljóðversplata · '
        '<i class="fa-solid fa-compact-disc tl-focus"></i> fókusplata · '
        '<i class="fa-solid fa-rug tl-cover"></i> ábreiða · '
        f"{band_legend}"
        '<i class="fa-solid fa-award tl-award"></i> tilnefning. '
        'Súlurnar neðst sýna ný lög á ári (hvert lag talið einu sinni, árið sem það kom fyrst út): '
        '<span class="tl-key tl-hist-solo"></span> í eigin nafni, '
        f"{band_keys}"
        '<span class="tl-key tl-hist-others"></span> fyrir aðra. '
        f"{screen_legend}"
        "Bentu á tákn til að sjá nánar.</p>"
    )
    # The film and TV lane makes the track taller than the stylesheet's default.
    height = f' style="height:{TIMELINE_LANES["screen"] + SCREEN_HEIGHT}px"' if "screen" in lanes else ""
    # Copy or download the timeline with its legend as a PNG (_timeline-export.html); the title
    # only shows in the image, so a shared picture says whose timeline it is.
    tools = (f'<div class="tl-tools" data-target="tl-{artist_slug}" data-file="{artist_slug}-timalina">'
             '<button type="button" class="tl-copy"><i class="fa-solid fa-copy"></i> Afrita mynd</button>'
             '<button type="button" class="tl-download"><i class="fa-solid fa-download"></i> Sækja PNG</button>'
             '<span class="tl-tools-status" aria-live="polite"></span></div>')
    timeline = (f'{tools}<div class="tl-figure" id="tl-{artist_slug}">'
                f'<div class="tl-export-title">{html.escape(found[1])} · tímalína · MÚSÍKISUR</div>'
                f'<div class="timeline"><div class="tl-labels"{height}>{labels}</div>'
                f'<div class="tl-track"{height}>{"".join(parts)}</div></div>{legend}</div>')

    table = ""
    if albums or band_albums:
        rows, previous = [], None
        for source, (when, precision, label, detail, _) in sorted(
            [("solo", item) for item in albums] + band_albums, key=lambda pair: pair[1][0]
        ):
            rows.append({
                "year": when.year,
                "performer": "Sóló" if source == "solo" else detail,
                "title": f"**[{label}](../albums/{focus[detail]}.qmd)**" if source == "solo" and detail in focus else label,
                "age": f"{_years_between(died, when)} ár eftir andlát" if died and when > died else _age_text(born, when),
                "gap": _gap(previous, (when, precision)),
            })
            previous = (when, precision)
        table = "\n**Plötur og aldur við útgáfu**\n\n" + md_table(pd.DataFrame(rows), {
            "year": "Útgáfuár", "performer": "Flytjandi", "title": "Plata", "age": "Aldur", "gap": "Frá síðustu plötu",
        }) + "\n*Bil í mánuðum þar sem útgáfumánuður er þekktur; ~ merkir að aðeins árið er þekkt.*\n"
    return "```{=html}\n" + timeline + "\n```\n" + table


def _performer_colours(artist_name: str, events: list[tuple]) -> dict[str, str]:
    """Lower-case performer name -> colour: the artist in the solo blue, bands as on the timeline."""
    joins = sorted((when, label) for kind, when, _, label, *_ in events if kind == "band_join")
    colours = {artist_name.lower(): HIST_COLORS["solo"]}
    for i, (_, band) in enumerate(joins):
        colours[band.lower()] = BAND_PALETTE[i % len(BAND_PALETTE)]
    return colours


def chart_table(artist_slug: str, chart: str | None = None) -> str:
    """Raw Billboard data per song and album: first and last week, weeks, best position, re-entries.
    With ``chart`` (e.g. "Billboard Hot 100") only that list, without the list and type columns."""
    with connect_ro() as con:
        found = _artist(con, artist_slug)
        runs = _chart_runs(con, _performers(found[1], _events(con, found[0]))) if found else []
    runs = [run for run in runs if chart is None or run[0] == chart]
    if not runs:
        return "*Engar færslur á þessum lista.*\n" if chart else "*Engar færslur á Billboard-listum.*\n"
    frame = pd.DataFrame(runs, columns=["chart", "type", "performer", "title", "first", "last", "best", "weeks", "run"])
    table = (frame.groupby(["chart", "type", "performer", "title"])
             .agg(first=("first", "min"), last=("last", "max"), weeks=("weeks", "sum"),
                  best=("best", "min"), reentries=("run", "max"))
             .reset_index().sort_values("first"))
    table["kind"] = table["type"].map({"singles": "lag", "albums": "plata"})
    table["first_text"] = table["first"].map(format_date)
    table["last_text"] = table["last"].map(format_date)
    headers = {"chart": "Listi", "performer": "Flytjandi", "title": "Titill", "kind": "Tegund",
               "first_text": "Fyrsta vika", "last_text": "Síðasta vika", "weeks": "Vikur",
               "best": "Besta sæti", "reentries": "Endurkomur"}
    if chart:
        headers = {key: label for key, label in headers.items() if key not in ("chart", "kind")}
    return interactive_table(table, headers, paging=len(table) > 25)


def chart_plot(artist_slug: str, chart: str | None = None) -> Any:
    """Position week by week while on each list (1 at the top), runs aligned at their first week;
    one panel per chart (only ``chart`` when given), lines coloured by performer, song or album in
    the legend and tooltip."""
    import plotly.graph_objects as go
    import plotly.io as pio
    from plotly.subplots import make_subplots

    pio.renderers.default = "notebook_connected"
    with connect_ro() as con:
        found = _artist(con, artist_slug)
        events = _events(con, found[0]) if found else []
        weeks = _chart_weeks(con, _performers(found[1], events)) if found else pd.DataFrame()
    if weeks.empty:
        return None
    colours = _performer_colours(found[1], events)
    charts = [c for c in ("Billboard Hot 100", "Billboard 200")
              if c in set(weeks["chart"]) and (chart is None or c == chart)]
    if not charts:
        return None
    fig = make_subplots(rows=1, cols=len(charts), subplot_titles=charts, horizontal_spacing=0.08)
    for col, panel in enumerate(charts, start=1):
        for (performer, title, run), trace in weeks[weeks["chart"] == panel].groupby(["performer", "title", "run"], sort=False):
            name = f"{title} ({trace['chart_date'].min().year})" + (" – endurkoma" if run else "")
            fig.add_trace(go.Scatter(
                x=trace["week"], y=trace["position"], mode="lines+markers", name=name,
                line={"width": 2, "color": colours.get(performer.lower(), "#6c757d")},
                marker={"size": 6}, legendgroup=panel, legendgrouptitle_text=panel,
                customdata=list(zip(trace["chart_date"].map(format_date), [performer] * len(trace))),
                hovertemplate=f"<b>{html.escape(title)}</b> (%{{customdata[1]}})<br>%{{customdata[0]}}: "
                              "%{y}. sæti, vika %{x}<extra></extra>",
            ), row=1, col=col)
        limit = 100 if panel == "Billboard Hot 100" else 200
        fig.update_yaxes(range=[limit + 2, 0], title_text="Sæti" if col == 1 else None,
                         gridcolor="#e9ecef", zeroline=False, row=1, col=col)
        fig.update_xaxes(title_text="Vika á lista", gridcolor="#f1f3f5", zeroline=False, row=1, col=col)
    fig.update_layout(template="plotly_white", height=480, margin={"l": 50, "r": 20, "t": 40, "b": 40},
                      hovermode="closest", legend={"groupclick": "toggleitem", "font": {"size": 11}},
                      font={"family": "system-ui, -apple-system, Segoe UI, sans-serif", "color": "#343a40"})
    return fig


ROLE_LABELS = {
    "producer": "upptökustjórn",
    "mix": "hljóðblöndun",
    "recording": "hljóðritun",
    "engineer": "hljóðvinnsla",
    "composer": "lög",
    "lyricist": "textar",
    "writer": "lög og textar",
    "arranger": "útsetningar",
    "instrument arranger": "útsetningar",
    "vocal arranger": "raddútsetningar",
    "vocal": "söngur",
    "instrument": "hljóðfæraleikur",
    "performer": "flytjandi",
}


def credits_summary(slug: str) -> str:
    """Songwriters, then everyone who played on or produced the album (instruments as in the source)."""
    with connect_ro() as con:
        rows = con.execute(
            """
            WITH album AS (SELECT album_id FROM albums WHERE slug = ?),
            tr AS (
                SELECT t.recording_id, t.work_id, t.disc_number, t.track_number
                FROM album_tracks t JOIN album USING (album_id)
            )
            SELECT p.name, c.entity_type, c.role, c.instrument, tr.disc_number, tr.track_number
            FROM credits c
            JOIN people p USING (person_id)
            LEFT JOIN tr ON (c.entity_type = 'recording' AND c.entity_id = tr.recording_id)
                         OR (c.entity_type = 'work' AND c.entity_id = tr.work_id)
            WHERE (c.entity_type = 'album' AND c.entity_id = (SELECT album_id FROM album))
               OR tr.track_number IS NOT NULL
            """,
            [slug],
        ).df()
        total = con.execute(
            "SELECT count(*) FROM album_tracks JOIN albums USING (album_id) WHERE slug = ?", [slug]
        ).fetchone()[0]
    if rows.empty:
        return "*Engar heimildir um flytjendur enn.*\n"

    rows["track"] = [
        None if pd.isna(t) else (int(d), int(t)) for d, t in zip(rows["disc_number"], rows["track_number"])
    ]
    def labels(role: str, instrument: Any) -> list[str]:
        instruments = [p.strip() for p in instrument.split(",")] if isinstance(instrument, str) else []
        label = ROLE_LABELS.get(role, role)
        if role in {"instrument", "vocal"}:
            return instruments or [label]
        return [f"{label} ({', '.join(instruments)})"] if instruments else [label]

    rows["label"] = [labels(role, inst) for role, inst in zip(rows["role"], rows["instrument"])]
    rows = rows.explode("label")

    parts = []
    writing = rows[rows["entity_type"] == "work"]
    if not writing.empty:
        lines = []
        for role, group in writing.groupby("role"):
            people = group.groupby("name")["track"].nunique().sort_values(ascending=False)
            names = ", ".join(f"{name} ({_songs(int(n), total)})" for name, n in people.items())
            lines.append(f"- **{ROLE_LABELS.get(role, role).capitalize()}:** {names}")
        parts.append("### Lagahöfundar\n\n" + "\n".join(lines) + "\n")

    playing = rows[rows["entity_type"] != "work"]
    if not playing.empty:
        people = (
            playing.groupby("name")
            .agg(
                roles=("label", lambda s: ", ".join(sorted(set(s)))),
                tracks=("track", lambda s: len({t for t in s if t is not None})),
            )
            .reset_index()
            .sort_values(["tracks", "name"], ascending=[False, True])
        )
        parts.append(
            f"\n### Hver spilaði?\n\n{len(people)} manns koma við sögu, á {total} lögum.\n\n"
            + interactive_table(people, {"name": "Nafn", "roles": "Hlutverk", "tracks": "Fjöldi laga"},
                                order=[[2, "desc"], [0, "asc"]])
            + "\n*Hljóðfæri eru skráð eins og í heimildinni (MusicBrainz); 0 lög þýðir framlag til plötunnar í heild.*\n"
        )
    return "".join(parts)


DATATABLES_IS = {
    "search": "Leita:",
    "lengthMenu": "Sýna _MENU_ línur",
    "info": "Sýni _START_–_END_ af _TOTAL_",
    "infoEmpty": "Engar línur",
    "zeroRecords": "Ekkert fannst",
    "paginate": {"first": "Fyrsta", "last": "Síðasta", "next": "Næsta", "previous": "Fyrri"},
}
FAIR_USE_NOTE = "Hljóðbrot af Wikipediu, notað sem sanngjörn not (fair use)"


def interactive_table(frame: pd.DataFrame, headers: dict[str, str], **options: Any) -> str:
    """Sortable, searchable table (itables / DataTables, loaded from a CDN) as a raw HTML block."""
    from itables import to_html_datatable

    table = frame[list(headers)].rename(columns=headers)
    settings = {
        "allow_html": True, "connected": True, "showIndex": False, "classes": "display compact",
        "language": DATATABLES_IS, "pageLength": 10, "lengthMenu": [10, 25, 50],
        **options,
    }
    return "```{=html}\n" + to_html_datatable(table, **settings) + "\n```\n"


def _sample_player(url: Any, page: Any) -> str:
    if not isinstance(url, str):
        return ""
    info = f' <a href="{html.escape(page)}" title="{FAIR_USE_NOTE}"><i class="bi bi-info-circle"></i></a>' if isinstance(page, str) else ""
    return (f'<audio controls preload="none" class="track-sample" src="{html.escape(url)}" '
            f'title="{FAIR_USE_NOTE}"></audio>{info}')


def tracklist(slug: str) -> str:
    """Tracks with Spotify links, length, audio samples and Billboard Hot 100 runs, sortable."""
    with connect_ro() as con:
        tracks = con.execute(
            """
            WITH album AS (
                SELECT a.album_id, ar.name AS artist
                FROM albums a JOIN artists ar USING (artist_id) WHERE a.slug = ?
            ), hot100 AS (
                SELECT lower(ce.title) AS title, count(DISTINCT ce.chart_date) AS weeks, min(ce.position) AS peak
                FROM chart_entries ce JOIN charts c USING (chart_id) CROSS JOIN album
                WHERE c.name = 'Billboard Hot 100' AND lower(ce.artist_name) = lower(album.artist)
                GROUP BY 1
            )
            SELECT t.disc_number, t.track_number, t.track_title, r.spotify_url, r.duration_ms,
                   t.sample_url, t.sample_page, h.weeks, h.peak
            FROM album_tracks t JOIN album USING (album_id)
            LEFT JOIN recordings r USING (recording_id)
            LEFT JOIN hot100 h ON h.title = lower(t.track_title)
            ORDER BY t.disc_number, t.track_number
            """,
            [slug],
        ).df()
    if tracks.empty:
        return "*Lagalisti ekki kominn enn.*\n"
    multi_disc = tracks["disc_number"].nunique() > 1
    tracks["nr"] = [
        f"{d}.{t}" if multi_disc else int(t)
        for d, t in zip(tracks["disc_number"], tracks["track_number"])
    ]
    tracks["song"] = [
        f"{title} {spotify_link(url)}" if isinstance(url, str) else title
        for title, url in zip(tracks["track_title"], tracks["spotify_url"])
    ]
    tracks["length"] = [
        f"{int(ms) // 60000}:{int(ms) // 1000 % 60:02d}" if pd.notna(ms) else "" for ms in tracks["duration_ms"]
    ]
    tracks["sample"] = [_sample_player(u, p) for u, p in zip(tracks["sample_url"], tracks["sample_page"])]
    headers = {"nr": "Nr.", "song": "Lag", "length": "Lengd", "sample": "Hljóðbrot",
               "weeks": "Vikur á Hot 100", "peak": "Besta sæti"}
    note = "" if tracks["weeks"].notna().any() else "\n*Billboard-dálkarnir fyllast þegar vinsældalistarnir eru komnir í gagnagrunninn.*\n"
    return interactive_table(tracks, headers, paging=len(tracks) > 25, order=[[0, "asc"]]) + note


def chart_neighbours(
    con: duckdb.DuckDBPyConnection, slug: str, window: int = 5
) -> tuple[pd.DataFrame, pd.Series, pd.DataFrame] | None:
    """The album's chart entries, its best week, and the chart around it that week (None if uncharted)."""
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
        SELECT ce.chart_id, c.name AS chart, c.chart_type, ce.chart_date, ce.position, ce.title,
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
        return None

    peak = hits.sort_values(["position", "chart_date"]).iloc[0]
    week = con.execute(
        """
        SELECT ce.position, ce.artist_name, ce.title, l.spotify_url
        FROM chart_entries ce
        LEFT JOIN chart_links l USING (chart_id, artist_name, title)
        WHERE ce.chart_id = ? AND ce.chart_date = ? AND ce.position BETWEEN ? AND ?
        ORDER BY ce.position
        """,
        [
            int(peak["chart_id"]),
            peak["chart_date"].date(),
            max(1, int(peak["position"]) - window),
            int(peak["position"]) + window,
        ],
    ).df()
    return hits, peak, week


def chart_context(slug: str, window: int = 5) -> str:
    """Chart runs for the album's tracks plus the full chart around their best week."""
    with connect_ro() as con:
        found = chart_neighbours(con, slug, window)
    if found is None:
        return "*Engar færslur á vinsældalistum enn.*\n"
    hits, peak, week = found

    runs = (
        hits.groupby(["chart", "title"])
        .agg(best=("position", "min"), weeks=("chart_date", "nunique"), first=("chart_date", "min"))
        .reset_index()
        .sort_values(["best", "first"])
    )
    runs["first"] = runs["first"].map(format_date)

    def comebacks(weeks: pd.DataFrame) -> str:
        """Later runs (after more than four weeks off the list): start, length, best position."""
        weeks = weeks.sort_values("chart_date")
        run_number = weeks["chart_date"].diff().dt.days.gt(28).cumsum()
        later = [
            f"{format_date(run['chart_date'].min())} ({_weeks(run['chart_date'].nunique())}, "
            f"besta sæti {int(run['position'].min())})"
            for number, run in weeks.groupby(run_number) if number > 0
        ]
        return "; ".join(later) or "—"

    returns = {key: comebacks(group) for key, group in hits.groupby(["chart", "title"])}
    runs["comeback"] = [returns[(chart, title)] for chart, title in zip(runs["chart"], runs["title"])]

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
    week["title"] = [
        f"{title} {spotify_link(url)}" if isinstance(url, str) else title
        for title, url in zip(week["title"], week["spotify_url"])
    ]

    parts = [
        "### Gengi á listum\n",
        md_table(runs, {"chart": "Listi", "title": "Titill", "best": "Besta sæti",
                        "weeks": "Vikur", "first": "Fyrsta vika", "comeback": "Endurkoma"}),
        "\n*Vikur = vikur sem eru skráðar í gagnagrunninn, ekki endilega allur ferillinn.*\n",
        "\n### Hvað annað var vinsælt?\n",
        (
            f"{peak['chart']}, vikuna {format_date(peak['chart_date'])}, þegar "
            f"*{peak['title']}* var í {int(peak['position'])}. sæti:\n\n"
        ),
        md_table(week, {"position": "Sæti", "artist_name": "Flytjandi", "title": "Titill"}),
    ]
    if hits["text_match"].any():
        parts.append(
            "\n*Sumar færslur eru paraðar við plötuna eftir nafni flytjanda og lags, "
            "þar sem auðkenni vantar.*\n"
        )
    return "".join(parts)


SCREEN_KIND_WORDS = (("tv", "þáttaröðum"), ("movie", "kvikmyndum"), ("other", "öðrum titlum"))
NO_SCREEN_USE = "*Engin skráð notkun í kvikmyndum eða sjónvarpi enn.*\n"


def _screen_credits(con: duckdb.DuckDBPyConnection, artist_id: int) -> pd.DataFrame:
    return con.execute(
        "SELECT * FROM screen_credits WHERE artist_id = ? ORDER BY first_year, title", [artist_id]
    ).df()


def _song_links(con: duckdb.DuckDBPyConnection, artist_id: int) -> dict[str, str]:
    return dict(con.execute("SELECT song, spotify_url FROM song_links WHERE artist_id = ?", [artist_id]).fetchall())


def _song_performers(artist_name: str, events: list[tuple]) -> dict[str, tuple[str, str]]:
    """Song key -> (who released the song first, their timeline colour)."""
    colours = _performer_colours(artist_name, events)
    performers: dict[str, tuple[str, str]] = {}
    for kind, _, _, label, detail, _ in events:
        if kind == "song":
            who = artist_name if detail == "solo" else detail
            performers.setdefault(song_key(label), (who, colours.get(who.lower(), HIST_COLORS["solo"])))
    return performers


def _screen_tables(
    credits: pd.DataFrame, links: dict[str, str], performers: dict[str, tuple[str, str]],
    songs: list[str] | None = None,
) -> str:
    """Film and TV uses (IMDb): a sortable table of titles per song (performer in the timeline
    colour, Spotify link, first and last year of use), then the three most popular series and films.

    ``songs`` limits it to those songs (a chapter's album). Popularity is TMDB's vote count."""
    frame = credits.assign(song=credits["songs"].str.split("; ")).explode("song")
    if songs is not None:
        wanted = {song_key(s) for s in songs}
        frame = frame[frame["song"].map(lambda s: song_key(s) in wanted)]
    if frame.empty:
        return NO_SCREEN_USE
    titles = frame.drop_duplicates("imdb_id")
    kinds = titles["kind"].value_counts()
    parts = [f"{kinds[k]} {word}" for k, word in SCREEN_KIND_WORDS if k in kinds]
    split = " og ".join([", ".join(parts[:-1]), parts[-1]]) if len(parts) > 1 else parts[0]
    counts = (frame.groupby(["song", "kind"])["imdb_id"].nunique().unstack(fill_value=0)
              .reindex(columns=["tv", "movie", "other"], fill_value=0))
    counts["total"] = counts.sum(axis=1)
    counts["first"] = frame.groupby("song")["first_year"].min()
    counts["last"] = frame.groupby("song")["last_year"].max()
    counts = counts.sort_values(["total", "first"], ascending=[False, True]).reset_index()

    def performer(song: str) -> str:
        found = performers.get(song_key(song))
        return (f'<span class="tl-key" style="background:{found[1]}"></span> {html.escape(found[0])}'
                if found else "—")

    counts["performer"] = [performer(s) for s in counts["song"]]
    counts["song"] = [f"{html.escape(s)} {spotify_link(links[s])}" if s in links else html.escape(s)
                      for s in counts["song"]]
    n_songs = len(counts)
    noun = "lag" if n_songs % 10 == 1 and n_songs % 100 != 11 else "lög"
    songs_of = frame.groupby("imdb_id")["song"].agg(lambda s: ", ".join(f"„{x}“" for x in dict.fromkeys(s)))

    def top(kind: str) -> str:
        rows = titles[titles["kind"] == kind].sort_values("tmdb_votes", ascending=False, na_position="last").head(3)
        if rows.empty:
            return "—\n"
        rows = rows.assign(
            link=[f"[{t}](https://www.imdb.com/title/{i}/)" for t, i in zip(rows["title"], rows["imdb_id"])],
            years=[str(a) if a == b else f"{a}–{b}" for a, b in zip(rows["first_year"], rows["last_year"])],
            song=[songs_of[i] for i in rows["imdb_id"]],
            rating=["—" if pd.isna(r) else f"{r:.1f}".replace(".", ",") for r in rows["imdb_rating"]],
        )
        return md_table(rows, {"link": "Titill", "years": "Ár", "song": "Lag", "rating": "Einkunn (IMDb)"})

    retrieved = pd.to_datetime(credits["retrieved_at"]).max()
    read = f", lesin {format_date(retrieved.date())}" if pd.notna(retrieved) else ""
    which = "af plötunni" if songs is not None else ("ólíkt" if noun == "lag" else "ólík")
    headers = {"song": "Lag", "performer": "Flytjandi", "tv": "Þáttaraðir", "movie": "Kvikmyndir",
               "other": "Annað", "total": "Alls", "first": "Fyrst", "last": "Síðast"}
    return (
        (f"IMDb skráir {n_songs} {noun} af plötunni" if songs is not None else f"IMDb skráir {n_songs} {which} {noun}")
        + f" í {len(titles)} myndum og þáttum: {split}.\n\n"
        + interactive_table(counts, headers, paging=len(counts) > 25, searching=False,
                            order=[[list(headers).index("total"), "desc"]])
        + '\n:::: {layout-ncol="2"}\n::: {}\n**Vinsælustu þáttaraðirnar**\n\n' + top("tv")
        + ":::\n\n::: {}\n**Vinsælustu kvikmyndirnar**\n\n" + top("movie") + ":::\n::::\n\n"
        + f"*Heimild: soundtrack-skráning á IMDb{read}; hver titill tengist sinni IMDb-síðu. Raðað eftir "
        "vinsældum (fjölda einkunna á TMDB); einkunnin sýnir gæði (meðaleinkunn á IMDb). Þáttaröð er talin "
        "einu sinni þótt lagið heyrist í fleiri þáttum.*\n"
    )


def screen_summary(artist_slug: str) -> str:
    """The artist page's film and TV section: all songs."""
    with connect_ro() as con:
        found = _artist(con, artist_slug)
        credits = _screen_credits(con, found[0]) if found else pd.DataFrame()
        links = _song_links(con, found[0]) if found else {}
        performers = _song_performers(found[1], _events(con, found[0])) if found else {}
    return _screen_tables(credits, links, performers) if not credits.empty else NO_SCREEN_USE


def screen_use(slug: str) -> str:
    """The chapter's film and TV section: uses of the album's own songs."""
    with connect_ro() as con:
        row = con.execute(
            "SELECT a.artist_id, ar.name FROM albums a JOIN artists ar USING (artist_id) WHERE a.slug = ?", [slug]
        ).fetchone()
        credits = _screen_credits(con, row[0]) if row else pd.DataFrame()
        links = _song_links(con, row[0]) if row else {}
        performers = _song_performers(row[1], _events(con, row[0])) if row else {}
        songs = [title for (title,) in con.execute(
            "SELECT t.track_title FROM album_tracks t JOIN albums a USING (album_id) WHERE a.slug = ?", [slug]
        ).fetchall()]
    return _screen_tables(credits, links, performers, songs) if not credits.empty else NO_SCREEN_USE

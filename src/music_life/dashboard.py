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
    """Spotify icon (Bootstrap Icons, bundled with Quarto) linking to ``url``, optionally with text."""
    icon = '<i class="bi bi-spotify spotify-icon" aria-hidden="true"></i>'
    label = text or "Hlusta á Spotify"
    return f'<a href="{url}" class="spotify-link" title="Hlusta á Spotify" aria-label="{label}">{icon}{" " + text if text else ""}</a>'


def age_at_release(born: date, released: date | None, year: int) -> float:
    """Exact age on the release date; when only the year is known, the midpoint of the two possible ages."""
    if released:
        return released.year - born.year - ((released.month, released.day) < (born.month, born.day))
    return year - born.year - 0.5


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
    lines = [f"- **Flytjandi:** [{artist}](../artists/{artist_slug}.qmd)" if artist else "- **Flytjandi:** —"]
    if released:
        lines.append(f"- **Útgáfudagur:** {format_date(released)}")
    elif year:
        lines.append(f"- **Útgáfuár:** {year}")
    if year:
        lines.append(f"- **Aldur plötunnar í dag:** {this_year() - year} ár")
    if born and year:
        age = age_at_release(born, released, year)
        shown = str(int(age)) if released else f"{int(age - 0.5)}–{int(age + 0.5)}"
        lines.append(f"- **Aldur flytjanda við útgáfu:** {shown} ára")
    lines.append(f"- **Lög:** {track_count}")
    if duration_ms:
        lines.append(f"- **Lengd:** {duration_ms / 60000:.0f} mínútur (lágmarkshlustun fyrir virkan klúbbmeðlim)")
    if spotify_url:
        lines.append(f"- **Hlusta:** {spotify_link(spotify_url, title)}")
    cover = ""
    if (COVERS_DIR / f"{slug}.jpg").exists():
        with connect_ro() as con:
            source = _image_source(con, slug, "coverart-front")
        credit = (f'Umslag: <a href="{html.escape(source[0])}">Cover Art Archive</a>; höfundarréttur hjá rétthöfum'
                  if source else "Umslag")
        # Chapters live in albums/, so the cover is one directory up.
        cover = ("```{=html}\n"
                 f'<figure class="album-cover"><img src="../assets/covers/{slug}.jpg" '
                 f'alt="Umslag plötunnar {html.escape(title)}"><figcaption>{credit}</figcaption></figure>\n'
                 "```\n\n")
    return cover + "\n".join(lines) + "\n"


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
LABEL_FALLBACK_IS = {"voice": "rödd", "recording artist": "hljóðritunarlistamaður"}
PLACE_STYLES = {  # role: (marker colour, Font Awesome icon, description)
    "birth": ("green", "star", "Fæðingarstaður"),
    "death": ("black", "circle", "Dánarstaður"),
    "residence": ("orange", "home", "Búseta"),
    "mentioned": ("#2780e3", None, "Nefndur í Wikipedia-greininni"),
}
TIMELINE_LANES = {  # px from the top of the track
    "life": 18, "career": 46, "album": 76, "band": 104, "others": 132, "cover": 160, "hist": 211,
}
LANE_TITLES = {
    "life": "Ævi", "career": "Ferill", "album": "Plötur", "band": "Hljómsveitir",
    "others": "Fyrir aðra", "cover": "Ábreiður", "hist": "Útgáfur á ári",
}
HIST_BOTTOM, HIST_HEIGHT = 236, 50
HIST_GROUPS = {"album": "solo", "single": "solo", "band_release": "band", "production": "others", "guest": "others"}
HIST_TITLES = {"solo": "í eigin nafni", "band": "með hljómsveit", "others": "fyrir aðra"}


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


def _age_text(born: date, value: date, precision: int) -> str:
    age = age_at_release(born, value if precision >= 11 else None, value.year)
    return str(int(age)) if precision >= 11 else f"{int(age - 0.5)}–{int(age + 0.5)}"


def artist_tldr(artist_slug: str) -> str:
    """Photo, then birth, death, active years, studio albums and nominations as a fact list."""
    with connect_ro() as con:
        found = _artist(con, artist_slug)
        if not found:
            return ""
        places = dict(con.execute(
            "SELECT role, coalesce(label_is, title) FROM artist_places WHERE artist_id = ? AND role IN ('birth', 'death')",
            [found[0]],
        ).fetchall())
        events = _events(con, found[0])
        photo = _artist_photo(con, artist_slug)
    figure = ""
    if photo and (ARTISTS_DIR / f"{artist_slug}.jpg").exists():
        # Artist pages live in artists/, so assets are one directory up.
        figure = ("```{=html}\n"
                  f'<figure class="artist-photo"><img src="../assets/artists/{artist_slug}.jpg" alt="{html.escape(found[1])}">'
                  f'<figcaption>Mynd: <a href="{html.escape(photo[0])}">{html.escape(photo[1])}</a>, '
                  "Wikimedia Commons</figcaption></figure>\n```\n\n")
    first = {}
    for kind, when, precision, *_ in events:
        first.setdefault(kind, (when, precision))
    lines = []
    born = first.get("birth", (None,))[0]
    died = first.get("death", (None,))[0]
    if born:
        lines.append(f"- **Fæddur:** {format_date(born)}" + (f" í {places['birth']}" if "birth" in places else ""))
    if died:
        where = f" í {places['death']}" if "death" in places else ""
        age = f", {int(age_at_release(born, died, died.year))} ára" if born else ""
        lines.append(f"- **Lést:** {format_date(died)}{where}{age}")
    if "career_start" in first:
        end = first["career_end"][0].year if "career_end" in first else ""
        lines.append(f"- **Ferill:** {first['career_start'][0].year}–{end}")
    albums = [when for kind, when, *_ in events if kind == "album"]
    if albums:
        posthumous = sum(1 for when in albums if died and when > died)
        after = f", þar af {posthumous} eftir andlát" if posthumous else ""
        lines.append(f"- **Hljóðversplötur:** {len(albums)} ({albums[0].year}–{albums[-1].year}){after}")
    nominations = [(when, label) for kind, when, _, label, *_ in events if kind == "nomination"]
    if nominations:
        years = ", ".join(str(y) for y in sorted({when.year for when, _ in nominations}))
        lines.append(f"- **Tilnefningar:** {len(nominations)} ({years}): " + "; ".join(label for _, label in nominations))
    return figure + "\n".join(lines) + "\n"


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
            SELECT p.role, coalesce(p.label_is, p.title), p.latitude, p.longitude, p.context
            FROM artist_places p JOIN artists ar USING (artist_id)
            WHERE ar.slug = ? ORDER BY p.role, p.title
            """,
            [artist_slug],
        ).fetchall()
    if not places:
        return None
    fmap = folium.Map(tiles="CartoDB positron", control_scale=True)
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
    # Frame the life places; the places Wikipedia mentions stay reachable by zooming out.
    framed = [(lat, lon) for role, _, lat, lon, _ in places if role != "mentioned"] or [
        (lat, lon) for _, _, lat, lon, _ in places
    ]
    lats, lons = [p[0] for p in framed], [p[1] for p in framed]
    fmap.fit_bounds([[min(lats), min(lons)], [max(lats), max(lons)]], padding=(30, 30))
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

    def icon(css: str, lane: str, at: float, title: str, url: str | None = None, offset: int = 0) -> str:
        tag = (f'<i class="fa-solid {css} tl-icon" style="left:{pct(at):.2f}%;top:{TIMELINE_LANES[lane] + offset}px" '
               f'title="{html.escape(title)}"></i>')
        return f'<a href="{html.escape(url)}" target="_blank" rel="noopener">{tag}</a>' if url else tag

    parts = []
    for age in range(0, int(end - born_at) + 1, 10):
        parts.append(f'<div class="tl-grid" style="left:{pct(born_at + age):.2f}%">'
                     f'<span>{born.year + age}<br>{age} ára</span></div>')
    lanes = ["life"]
    life_end = _position(died, 11) if died else end - 2
    parts.append(bar("tl-life", "life", born_at, life_end, "Ævi"))
    parts.append(icon("fa-baby", "life", born_at, f"Fæddur {format_date(born)}"))
    if died:
        parts.append(icon("fa-dove", "life", life_end, f"Lést {format_date(died)}, {int(age_at_release(born, died, died.year))} ára"))
    if "career_start" in by_kind:
        lanes.append("career")
        first_year = by_kind["career_start"][0][0].year
        last_year = by_kind["career_end"][0][0].year if "career_end" in by_kind else int(end - 2)
        parts.append(bar("tl-career", "career", first_year, last_year + 1, f"Ferill: {first_year}–{last_year}"))
    albums = by_kind.get("album", [])
    if albums:
        lanes.append("album")
        previous, flip = None, False
        for when, precision, label, detail, url in albums:
            at = _position(when, precision)
            flip = (not flip) if previous is not None and pct(at) - pct(previous) < 2.5 else False
            previous = at
            posthumous = died is not None and when > died
            css = "fa-compact-disc " + ("tl-focus" if detail in focus else "tl-posthumous" if posthumous else "tl-album")
            age = "eftir andlát" if posthumous else f"{_age_text(born, when, precision)} ára"
            # Albums with a chapter link to it; the others to MusicBrainz.
            link = f"../albums/{focus[detail]}.html" if detail in focus else url
            parts.append(icon(css, "album", at, f"{_when(when, precision)}: {label} ({age})", link, -10 if flip else 0))
    covers = by_kind.get("cover", [])
    if covers:
        lanes.append("cover")
        for when, precision, label, _, url in covers:
            parts.append(icon("fa-rug tl-cover", "cover", _position(when, precision), f"{_when(when, precision)}: {label}", url))

    band_releases = by_kind.get("band_release", [])
    if band_releases:
        lanes.append("band")
        for when, precision, label, detail, url in band_releases:
            parts.append(icon("fa-users tl-band", "band", _position(when, precision),
                              f"{_when(when, precision)}: {detail} – {label}", url))
    others = sorted(
        [("production", item) for item in by_kind.get("production", [])]
        + [("guest", item) for item in by_kind.get("guest", [])],
        key=lambda pair: pair[1][0],
    )
    if others:
        lanes.append("others")
        for kind, (when, precision, label, detail, url) in others:
            css = "fa-sliders tl-production" if kind == "production" else "fa-microphone-lines tl-guest"
            parts.append(icon(css, "others", _position(when, precision),
                              f"{_when(when, precision)}: {label} ({ROLE_LABELS.get(detail, detail)})", url))
    for when, precision, label, _, url in by_kind.get("nomination", []) + by_kind.get("award", []):
        parts.append(icon("fa-award tl-award", "career", _position(when, precision),
                          f"{_when(when, precision)}: {label}", url, -14))

    # Releases per year, stacked: own name, with a band, for others.
    counts: dict[int, dict[str, int]] = {}
    for kind, group in HIST_GROUPS.items():
        for when, *_ in by_kind.get(kind, []):
            counts.setdefault(when.year, {}).setdefault(group, 0)
            counts[when.year][group] += 1
    if counts:
        lanes.append("hist")
        peak = max(sum(per.values()) for per in counts.values())
        for year, per_group in sorted(counts.items()):
            top = HIST_BOTTOM
            for group in ("solo", "band", "others"):
                n = per_group.get(group, 0)
                if n:
                    height = n / peak * HIST_HEIGHT
                    top -= height
                    width = max(pct(year + 1) - pct(year) - 0.15, 0.3)
                    parts.append(
                        f'<div class="tl-hist tl-hist-{group}" style="left:{pct(year):.2f}%;width:{width:.2f}%;'
                        f'top:{top:.1f}px;height:{height:.1f}px" title="{year}: {n} {HIST_TITLES[group]}"></div>'
                    )

    labels = "".join(f'<div style="top:{TIMELINE_LANES[lane]}px">{LANE_TITLES[lane]}</div>' for lane in lanes)
    legend = (
        '<p class="tl-legend"><i class="fa-solid fa-baby"></i> fæðing · <i class="fa-solid fa-dove"></i> andlát · '
        '<i class="fa-solid fa-compact-disc tl-album"></i> hljóðversplata · '
        '<i class="fa-solid fa-compact-disc tl-focus"></i> plata með kafla í bókinni · '
        '<i class="fa-solid fa-compact-disc tl-posthumous"></i> eftir andlát · '
        '<i class="fa-solid fa-rug tl-cover"></i> ábreiða · '
        '<i class="fa-solid fa-users tl-band"></i> með hljómsveit · '
        '<i class="fa-solid fa-sliders tl-production"></i> upptökustjórn fyrir aðra · '
        '<i class="fa-solid fa-microphone-lines tl-guest"></i> gestaframlag · '
        '<i class="fa-solid fa-award tl-award"></i> tilnefning. '
        'Súlurnar neðst eru útgáfur á ári: <span class="tl-key tl-hist-solo"></span> í eigin nafni, '
        '<span class="tl-key tl-hist-band"></span> með hljómsveit, '
        '<span class="tl-key tl-hist-others"></span> fyrir aðra. '
        "Lóðréttu línurnar eru á tíu ára fresti frá fæðingu; bentu á tákn til að sjá nánar.</p>"
    )
    timeline = (f'<div class="timeline"><div class="tl-labels">{labels}</div>'
                f'<div class="tl-track">{"".join(parts)}</div></div>{legend}')

    table = ""
    if albums:
        rows = pd.DataFrame([
            {
                "when": _when(when, precision),
                "title": f"**[{label}](../albums/{focus[detail]}.qmd)**" if detail in focus else label,
                "age": "eftir andlát" if died and when > died else _age_text(born, when, precision),
            }
            for when, precision, label, detail, _ in albums
        ])
        table = "\n**Hljóðversplötur og aldur við útgáfu**\n\n" + md_table(
            rows, {"when": "Útgáfa", "title": "Plata", "age": "Aldur"}
        )
    return "```{=html}\n" + timeline + "\n```\n" + table


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

"""Generate the Quarto book structure from config: decades are parts, focus albums chapters.

Decade and chapter files are created only when missing, so hand-written talking points
survive. The chapter list in dashboard/_quarto.yml is rewritten between the markers.
"""
from itertools import groupby
from pathlib import Path

from music_life.dashboard import DECADE_NAMES, REPO_ROOT, Chapter, load_chapters

DASHBOARD = REPO_ROOT / "dashboard"
QUARTO_YML = DASHBOARD / "_quarto.yml"
BEGIN = "# BEGIN GENERATED CHAPTERS"
END = "# END GENERATED CHAPTERS"

DECADE_TEMPLATE = """---
title: "{name}"
subtitle: "{years}"
---

```{{python}}
#| output: asis
from music_life.dashboard import decade_overview

print(decade_overview({decade}))
```

## Samhengi áratugarins

*Hér kemur stutt yfirlit yfir áratuginn.*
"""

CHAPTER_TEMPLATE = """---
title: "{heading}"
subtitle: "{artist}"
---

```{{python}}
ALBUM_SLUG = "{slug}"
```

```{{python}}
#| output: asis
from music_life.dashboard import album_cover

print(album_cover(ALBUM_SLUG))
```

*Hér kemur stutt kynning á plötunni; textinn flæðir í kringum umslagið.*

{{{{< include ../_chapter.qmd >}}}}

## Punktar fyrir þáttinn

*Hér koma umræðupunktarnir fyrir þáttinn.*
"""


ARTIST_TEMPLATE = """---
title: "{name}"
---

```{{python}}
ARTIST_SLUG = "{slug}"
```

```{{python}}
#| output: asis
from music_life.dashboard import artist_photo

print(artist_photo(ARTIST_SLUG))
```

*Hér kemur stutt samantekt um flytjandann.*

{{{{< include ../_artist.qmd >}}}}

### Helstu smellir

*Hér koma spilarar fyrir helstu smellina: {{{{< spotify-player TRACK_ID >}}}}.*

{{{{< include ../_artist_timeline.qmd >}}}}

### Fjölskylda og ástir

*Hér kemur umfjöllun um fjölskylduna.*

{{{{< include ../_artist_life.qmd >}}}}
"""


def artists_of(chapters: list[Chapter]) -> list[tuple[str, str]]:
    """(name, slug) of every artist with a chapter, alphabetically."""
    return sorted({(c.artist_name, c.artist_slug) for c in chapters})


def write_if_missing(path: Path, text: str) -> bool:
    if path.exists():
        return False
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8", newline="\n")
    return True


def chapter_lines(chapters: list[Chapter]) -> list[str]:
    """Artists first, then one part per decade with its focus albums."""
    lines = []
    artists = artists_of(chapters)
    if artists:
        lines.append('    - part: "Flytjendur"')
        lines.append("      chapters:")
        lines.extend(f"        - artists/{slug}.qmd" for _, slug in artists)
    for decade, group in groupby(chapters, key=lambda c: c.decade):
        lines.append(f"    - part: decades/{decade}s.qmd")
        lines.append("      chapters:")
        lines.extend(f"        - {c.path}" for c in group)
    return lines


def update_quarto_yml(lines: list[str]) -> bool:
    text = QUARTO_YML.read_text(encoding="utf-8")
    head_end = text.index("\n", text.index(BEGIN)) + 1
    tail_start = text.rindex("\n", 0, text.index(END)) + 1
    updated = text[:head_end] + "".join(f"{line}\n" for line in lines) + text[tail_start:]
    if updated == text:
        return False
    QUARTO_YML.write_text(updated, encoding="utf-8", newline="\n")
    return True


def main() -> None:
    chapters = load_chapters()
    created = []
    for decade in sorted({c.decade for c in chapters}):
        path = DASHBOARD / "decades" / f"{decade}s.qmd"
        years = f"{decade}–{decade + 9}"
        name = DECADE_NAMES.get(decade, years)
        if write_if_missing(path, DECADE_TEMPLATE.format(name=name, years=years, decade=decade)):
            created.append(path)
    for chapter in chapters:
        # The sidebar shows the album only (the artist has a page under Flytjendur); the artist is the subtitle.
        heading = f"*{chapter.title}* ({chapter.year})".replace('"', '\\"')
        artist = chapter.artist_name.replace('"', '\\"')
        text = CHAPTER_TEMPLATE.format(heading=heading, artist=artist, slug=chapter.slug)
        if write_if_missing(DASHBOARD / chapter.path, text):
            created.append(DASHBOARD / chapter.path)
    for name, slug in artists_of(chapters):
        path = DASHBOARD / "artists" / f"{slug}.qmd"
        if write_if_missing(path, ARTIST_TEMPLATE.format(name=name.replace('"', '\\"'), slug=slug)):
            created.append(path)

    for path in created:
        print(f"created {path.relative_to(REPO_ROOT).as_posix()}")
    if update_quarto_yml(chapter_lines(chapters)):
        print("updated dashboard/_quarto.yml chapter list")

    configured = {c.slug for c in chapters}
    for path in sorted((DASHBOARD / "albums").glob("*.qmd")):
        if path.stem not in configured:
            print(f"warning: {path.relative_to(REPO_ROOT).as_posix()} is not in config/focus-albums.yml")
    artist_slugs = {slug for _, slug in artists_of(chapters)}
    for path in sorted((DASHBOARD / "artists").glob("*.qmd")):
        if path.stem not in artist_slugs:
            print(f"warning: {path.relative_to(REPO_ROOT).as_posix()} has no focus album in config")
    print(f"book: {len(chapters)} chapters in {len({c.decade for c in chapters})} decades")


if __name__ == "__main__":
    main()

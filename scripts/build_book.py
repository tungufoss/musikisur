"""Generate the Quarto book structure from config: decades are parts, focus albums chapters.

Decade and chapter files are created only when missing, so hand-written talking points
survive. The chapter list in dashboard/_quarto.yml is rewritten between the markers.
"""
from itertools import groupby
from pathlib import Path

from music_life.dashboard import REPO_ROOT, Chapter, decade_label, load_chapters

DASHBOARD = REPO_ROOT / "dashboard"
QUARTO_YML = DASHBOARD / "_quarto.yml"
BEGIN = "# BEGIN GENERATED CHAPTERS"
END = "# END GENERATED CHAPTERS"

DECADE_TEMPLATE = """---
title: "{label}"
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
---

```{{python}}
ALBUM_SLUG = "{slug}"
```

{{{{< include ../_chapter.qmd >}}}}

## Punktar fyrir þáttinn

*Hér koma umræðupunktarnir fyrir þáttinn.*
"""


def write_if_missing(path: Path, text: str) -> bool:
    if path.exists():
        return False
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8", newline="\n")
    return True


def chapter_lines(chapters: list[Chapter]) -> list[str]:
    lines = []
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
        if write_if_missing(path, DECADE_TEMPLATE.format(label=decade_label(decade), decade=decade)):
            created.append(path)
    for chapter in chapters:
        heading = chapter.heading.replace('"', '\\"')
        if write_if_missing(DASHBOARD / chapter.path, CHAPTER_TEMPLATE.format(heading=heading, slug=chapter.slug)):
            created.append(DASHBOARD / chapter.path)

    for path in created:
        print(f"created {path.relative_to(REPO_ROOT).as_posix()}")
    if update_quarto_yml(chapter_lines(chapters)):
        print("updated dashboard/_quarto.yml chapter list")

    configured = {c.slug for c in chapters}
    for path in sorted((DASHBOARD / "albums").glob("*.qmd")):
        if path.stem not in configured:
            print(f"warning: {path.relative_to(REPO_ROOT).as_posix()} is not in config/focus-albums.yml")
    print(f"book: {len(chapters)} chapters in {len({c.decade for c in chapters})} decades")


if __name__ == "__main__":
    main()

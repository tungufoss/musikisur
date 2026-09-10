from pathlib import Path
import yaml
from .db import connect


def load_yaml(path: str | Path) -> dict:
    return yaml.safe_load(Path(path).read_text(encoding="utf-8"))


def sync_research_targets() -> None:
    artists = load_yaml("config/artists.yml")["artists"]
    focuses = load_yaml("config/focus-albums.yml")["focus_albums"]
    con = connect()

    for a in artists:
        con.execute(
            """
            INSERT INTO research_targets VALUES (?, 'artist', ?, ?, ?, ?)
            ON CONFLICT (target_id) DO UPDATE SET
              priority=excluded.priority, status=excluded.status, notes=excluded.notes
            """,
            [
                f"artist:{a['slug']}",
                a["slug"],
                1 if a.get("status") == "primary" else 10,
                a.get("status", "context"),
                a.get("research", {}).get("notes"),
            ],
        )

    for f in focuses:
        con.execute(
            """
            INSERT INTO research_targets VALUES (?, 'album', ?, ?, 'focus', ?)
            ON CONFLICT (target_id) DO UPDATE SET
              priority=excluded.priority, status=excluded.status, notes=excluded.notes
            """,
            [
                f"album:{f['slug']}",
                f["slug"],
                f.get("priority", 10),
                "\n".join(f.get("research_questions", [])),
            ],
        )
    con.close()

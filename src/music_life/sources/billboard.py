"""Billboard Hot 100 and Billboard 200 from the utdata/rwd-billboard-data submodule.

Source: https://github.com/utdata/rwd-billboard-data (MIT). Charts from 2022 on are scraped
weekly from billboard.com; the earlier archive was assembled from Kaggle and data.world and
has a few known errors listed in that repo's README. The submodule is pinned to a commit, so
chart builds are reproducible; update it deliberately with ``git submodule update --remote``.
"""
from __future__ import annotations

import subprocess
from pathlib import Path

import duckdb

REPO_URL = "https://github.com/utdata/rwd-billboard-data"
VENDOR_DIR = Path(__file__).resolve().parents[3] / "vendor" / "rwd-billboard-data" / "data-out"

# file -> (chart name, chart type)
CHART_FILES = {
    "hot-100-current.csv": ("Billboard Hot 100", "singles"),
    "billboard-200-current.csv": ("Billboard 200", "albums"),
}
# Numbers are read as text and converted with TRY_CAST, so "NA" or blanks in them become NULL
# without also turning a song literally titled "NA" into a missing title.
CSV_COLUMNS = {
    "chart_week": "DATE",
    "current_week": "VARCHAR",
    "title": "VARCHAR",
    "performer": "VARCHAR",
    "last_week": "VARCHAR",
    "peak_pos": "VARCHAR",
    "wks_on_chart": "VARCHAR",
}
COMPLETE_ROW = (
    "nullif(trim(title), '') IS NOT NULL AND nullif(trim(performer), '') IS NOT NULL "
    "AND TRY_CAST(current_week AS INTEGER) IS NOT NULL"
)


def _submodule_commit(data_dir: Path) -> str | None:
    try:
        result = subprocess.run(
            ["git", "-C", str(data_dir), "rev-parse", "HEAD"],
            capture_output=True, text=True, check=True,
        )
    except (OSError, subprocess.CalledProcessError):
        return None
    return result.stdout.strip()


def load_charts(con: duckdb.DuckDBPyConnection, data_dir: Path = VENDOR_DIR) -> dict[str, int]:
    """Load every available chart file; return inserted row counts per chart name."""
    counts: dict[str, int] = {}
    commit = _submodule_commit(data_dir)
    for filename, (name, chart_type) in CHART_FILES.items():
        path = data_dir / filename
        if not path.exists():
            continue
        row = con.execute("SELECT chart_id FROM charts WHERE name = ?", [name]).fetchone()
        chart_id = row[0] if row else con.execute(
            """
            INSERT INTO charts (name, publisher, territory, chart_type, frequency)
            VALUES (?, 'Billboard', 'US', ?, 'weekly') RETURNING chart_id
            """,
            [name, chart_type],
        ).fetchone()[0]
        source_id = con.execute(
            """
            INSERT INTO sources (source_name, source_type, source_url, retrieved_at, citation_text, raw_reference)
            VALUES ('utdata/rwd-billboard-data', 'chart_archive', ?, now(), ?, ?)
            RETURNING source_id
            """,
            [
                f"{REPO_URL}/blob/{commit or 'main'}/data-out/{filename}",
                f"{name} weekly archive, compiled by utdata/rwd-billboard-data",
                f"vendor/rwd-billboard-data/data-out/{filename}@{commit or 'unknown'}",
            ],
        ).fetchone()[0]

        columns = "{" + ", ".join(f"'{c}': '{t}'" for c, t in CSV_COLUMNS.items()) + "}"
        # Quotes inside fields are doubled ("Bobby ""Boris"" Pickett"); say so rather than let the sniffer guess.
        csv = f"read_csv(?, header = true, columns = {columns}, quote = '\"', escape = '\"')"
        total, complete = con.execute(
            f"SELECT count(*), count(*) FILTER (WHERE {COMPLETE_ROW}) FROM {csv}", [path.as_posix()]
        ).fetchone()
        before = con.execute("SELECT count(*) FROM chart_entries WHERE chart_id = ?", [chart_id]).fetchone()[0]
        con.execute(
            f"""
            INSERT INTO chart_entries
            (chart_id, chart_date, position, artist_name, title,
             previous_position, peak_to_date, weeks_on_chart, source_id)
            SELECT ?, chart_week, CAST(current_week AS INTEGER), performer, title,
                   nullif(TRY_CAST(last_week AS INTEGER), 0), TRY_CAST(peak_pos AS INTEGER),
                   TRY_CAST(wks_on_chart AS INTEGER), ?
            FROM {csv}
            WHERE {COMPLETE_ROW}
            ON CONFLICT DO NOTHING
            """,
            [chart_id, source_id, path.as_posix()],
        )
        inserted = con.execute(
            "SELECT count(*) FROM chart_entries WHERE chart_id = ?", [chart_id]
        ).fetchone()[0] - before
        if complete != total:
            print(f"warning: {name}: {total - complete} rows without a title, performer or position were skipped")
        if inserted != complete:
            print(f"warning: {name}: {complete - inserted} rows share a week and position with another row and were skipped")
        counts[name] = inserted
    return counts

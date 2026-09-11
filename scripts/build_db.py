"""Rebuild data/processed/music_life.duckdb from scratch.

1. Schema.
2. Billboard charts from the vendor/rwd-billboard-data submodule, when checked out.
3. Every album bundle in data/curated/<artist>/<album>/.
4. Demo rows, only while no album bundle exists yet.
"""
import runpy
from pathlib import Path

from music_life.bundles import iter_bundles, load_bundle, validate_bundle
from music_life.db import DEFAULT_DB, connect, init_db
from music_life.sources.billboard import load_charts


def main() -> None:
    for path in (DEFAULT_DB, DEFAULT_DB.with_name(DEFAULT_DB.name + ".wal")):
        path.unlink(missing_ok=True)
    init_db()

    con = connect()
    try:
        counts = load_charts(con)
        for name, rows in counts.items():
            print(f"{name}: {rows:,} chart rows")
        if not counts:
            print("charts: skipped, submodule not checked out (git submodule update --init)")

        bundles = list(iter_bundles())
        for path in bundles:
            errors = validate_bundle(path)
            if errors:
                raise SystemExit(f"invalid bundle {path.parent.name}/{path.name}:\n" + "\n".join(errors))
            load_bundle(con, path)
            print(f"bundle: {path.parent.name}/{path.name}")
    finally:
        con.close()

    if not bundles:
        print("no album bundles yet; loading demo rows")
        runpy.run_path(str(Path(__file__).with_name("build_demo_data.py")))


if __name__ == "__main__":
    main()

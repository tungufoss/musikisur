from pathlib import Path
import duckdb

DEFAULT_DB = Path("data/processed/music_life.duckdb")
SCHEMA = Path(__file__).with_name("schema.sql")


def connect(path: str | Path = DEFAULT_DB) -> duckdb.DuckDBPyConnection:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    return duckdb.connect(str(path))


def init_db(path: str | Path = DEFAULT_DB) -> None:
    con = connect(path)
    con.execute(SCHEMA.read_text(encoding="utf-8"))
    con.close()

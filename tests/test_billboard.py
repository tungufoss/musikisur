import duckdb

from music_life.db import init_db
from music_life.sources.billboard import load_charts

CSV = """chart_week,current_week,title,performer,last_week,peak_pos,wks_on_chart
1978-06-24,1,Song One,Artist One,1,1,10
1978-06-24,2,Song Two,Artist Two,NA,2,1
1978-06-24,2,Duplicate,Artist Three,0,2,1
1978-07-01,1,Song Two,Artist Two,2,1,2
"""


def test_load_charts_from_csv(tmp_path):
    (tmp_path / "hot-100-current.csv").write_text(CSV, encoding="utf-8")
    db = tmp_path / "test.duckdb"
    init_db(db)
    con = duckdb.connect(str(db))

    assert load_charts(con, tmp_path) == {"Billboard Hot 100": 3}
    rows = con.execute(
        """
        SELECT chart_date::VARCHAR, position, title, previous_position
        FROM chart_entries ORDER BY chart_date, position
        """
    ).fetchall()
    assert rows == [
        ("1978-06-24", 1, "Song One", 1),
        ("1978-06-24", 2, "Song Two", None),
        ("1978-07-01", 1, "Song Two", 2),
    ]
    assert con.execute("SELECT count(*) FROM sources").fetchone()[0] == 1
    con.close()


def test_missing_files_are_skipped(tmp_path):
    db = tmp_path / "test.duckdb"
    init_db(db)
    con = duckdb.connect(str(db))
    assert load_charts(con, tmp_path / "absent") == {}
    con.close()

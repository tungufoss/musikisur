from ..db import connect


def overlapping_chart_songs(chart_name: str, start_date: str, end_date: str):
    con = connect()
    result = con.execute(
        """
        SELECT ce.artist_name, ce.title,
               count(*) AS overlapping_weeks,
               min(ce.position) AS best_position
        FROM chart_entries ce
        JOIN charts c USING (chart_id)
        WHERE c.name = ?
          AND ce.chart_date BETWEEN ? AND ?
        GROUP BY ce.artist_name, ce.title
        ORDER BY overlapping_weeks DESC, best_position ASC
        """,
        [chart_name, start_date, end_date],
    ).df()
    con.close()
    return result

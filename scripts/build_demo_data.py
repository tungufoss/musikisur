"""Tiny, explicitly non-authoritative rows so CI can render the Quarto site."""
from music_life.db import connect, init_db

init_db()
con = connect()

con.execute("""
INSERT INTO artists (slug, name, sort_name)
VALUES ('gerry-rafferty', 'Gerry Rafferty', 'Rafferty, Gerry')
ON CONFLICT (slug) DO NOTHING
""")
artist_id = con.execute(
    "SELECT artist_id FROM artists WHERE slug='gerry-rafferty'"
).fetchone()[0]

con.execute("""
INSERT INTO albums
(slug, title, artist_id, original_release_date, album_type, is_focus_album)
VALUES ('city-to-city', 'City to City', ?, DATE '1978-01-01', 'album', TRUE)
ON CONFLICT (slug) DO UPDATE SET is_focus_album=TRUE
""", [artist_id])

album_id = con.execute(
    "SELECT album_id FROM albums WHERE slug='city-to-city'"
).fetchone()[0]

for title, track_no in [("The Ark", 1), ("Baker Street", 2), ("Right Down the Line", 3)]:
    row = con.execute(
        "SELECT recording_id FROM recordings WHERE title=? AND primary_artist_name='Gerry Rafferty'",
        [title],
    ).fetchone()
    if row:
        rid = row[0]
    else:
        rid = con.execute(
            """
            INSERT INTO recordings (title, primary_artist_name, release_year)
            VALUES (?, 'Gerry Rafferty', 1978)
            RETURNING recording_id
            """,
            [title],
        ).fetchone()[0]
    con.execute(
        """
        INSERT INTO album_tracks VALUES (?, ?, NULL, 1, ?, ?)
        ON CONFLICT (album_id, disc_number, track_number) DO NOTHING
        """,
        [album_id, rid, track_no, title],
    )

row = con.execute(
    "SELECT chart_id FROM charts WHERE name='Billboard Hot 100'"
).fetchone()
if row:
    chart_id = row[0]
else:
    chart_id = con.execute(
        """
        INSERT INTO charts (name, publisher, territory, chart_type, frequency)
        VALUES ('Billboard Hot 100', 'Billboard', 'US', 'singles', 'weekly')
        RETURNING chart_id
        """
    ).fetchone()[0]

for date, pos, artist, title in [
    ("1978-06-24", 1, "Andy Gibb", "Shadow Dancing"),
    ("1978-06-24", 2, "Gerry Rafferty", "Baker Street"),
    ("1978-06-24", 3, "Bonnie Tyler", "It's a Heartache"),
]:
    con.execute(
        """
        INSERT INTO chart_entries
        (chart_id, chart_date, position, artist_name, title)
        VALUES (?, ?, ?, ?, ?)
        ON CONFLICT DO NOTHING
        """,
        [chart_id, date, pos, artist, title],
    )

con.close()
print("Demo dataset ready; rows are for build testing only.")

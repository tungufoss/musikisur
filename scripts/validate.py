from music_life.db import connect

con = connect()
checks = {
    "artists": "SELECT count(*) FROM artists",
    "focus_albums": "SELECT count(*) FROM albums WHERE is_focus_album",
    "chart_entries": "SELECT count(*) FROM chart_entries",
}
failed = False
for name, sql in checks.items():
    value = con.execute(sql).fetchone()[0]
    print(f"{name}: {value}")
    if name in {"artists", "focus_albums"} and value == 0:
        failed = True
con.close()

if failed:
    raise SystemExit("Validation failed")

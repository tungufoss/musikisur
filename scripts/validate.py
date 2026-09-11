from music_life.bundles import iter_bundles, validate_bundle
from music_life.db import connect

failed = False
for path in iter_bundles():
    for error in validate_bundle(path):
        print(f"bundle {path.parent.name}/{path.name}: {error}")
        failed = True

con = connect()
checks = {
    "artists": "SELECT count(*) FROM artists",
    "focus_albums": "SELECT count(*) FROM albums WHERE is_focus_album",
    "chart_entries": "SELECT count(*) FROM chart_entries",
}
for name, sql in checks.items():
    value = con.execute(sql).fetchone()[0]
    print(f"{name}: {value}")
    if name in {"artists", "focus_albums"} and value == 0:
        failed = True
con.close()

if failed:
    raise SystemExit("Validation failed")

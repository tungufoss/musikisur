from music_life.db import init_db
from music_life.pipeline import sync_research_targets

init_db()
sync_research_targets()
print("Initialized data/processed/music_life.duckdb")

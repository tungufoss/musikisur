"""TMDB metadata adapter.

Use TMDB primarily to identify movies, TV series and episodes and to retain
stable TMDB IDs, release/air dates and external IDs such as IMDb IDs.

Do not assume TMDB's ordinary cast/crew credits constitute a complete music
soundtrack/sync dataset. Song-use observations belong in screen_appearances
and require their own provenance.
"""
from pathlib import Path
from typing import Any
from .base import SourceAdapter


class Adapter(SourceAdapter):
    source_name = "tmdb"

    def fetch(self, **kwargs: Any) -> list[Path]:
        raise NotImplementedError("Implement authenticated TMDB metadata retrieval and caching.")

    def normalize(self, raw_files: list[Path]) -> None:
        raise NotImplementedError

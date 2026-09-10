"""MusicBrainz: canonical music entities/relationships. Cache raw JSON; respect rate limits; keep works and recordings distinct."""
from pathlib import Path
from typing import Any
from .base import SourceAdapter


class Adapter(SourceAdapter):
    source_name = "musicbrainz"

    def fetch(self, **kwargs: Any) -> list[Path]:
        raise NotImplementedError("Implement live MusicBrainz ingestion.")

    def normalize(self, raw_files: list[Path]) -> None:
        raise NotImplementedError

"""Spotify enrichment only. Prefer ISRC/cross-ID matching before fuzzy artist-title-year matching; avoid accidental live/remaster substitutions."""
from pathlib import Path
from typing import Any
from .base import SourceAdapter


class Adapter(SourceAdapter):
    source_name = "spotify"

    def fetch(self, **kwargs: Any) -> list[Path]:
        raise NotImplementedError("Implement authenticated Spotify enrichment.")

    def normalize(self, raw_files: list[Path]) -> None:
        raise NotImplementedError

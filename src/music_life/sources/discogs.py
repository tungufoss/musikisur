"""Discogs: release editions, personnel and production credits."""
from pathlib import Path
from typing import Any
from .base import SourceAdapter


class Adapter(SourceAdapter):
    source_name = "discogs"

    def fetch(self, **kwargs: Any) -> list[Path]:
        raise NotImplementedError("Implement authenticated Discogs ingestion.")

    def normalize(self, raw_files: list[Path]) -> None:
        raise NotImplementedError

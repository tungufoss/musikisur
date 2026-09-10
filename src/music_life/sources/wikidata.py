"""Wikidata: structured biography, people, places, dates and external identifiers."""
from pathlib import Path
from typing import Any
from .base import SourceAdapter


class Adapter(SourceAdapter):
    source_name = "wikidata"

    def fetch(self, **kwargs: Any) -> list[Path]:
        raise NotImplementedError("Implement Wikidata SPARQL/API ingestion.")

    def normalize(self, raw_files: list[Path]) -> None:
        raise NotImplementedError

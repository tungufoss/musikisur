"""Historical charts. Ingest complete weekly snapshots when permitted, not only focus-artist rows."""
from pathlib import Path
from typing import Any
from .base import SourceAdapter


class Adapter(SourceAdapter):
    source_name = "charts"

    def fetch(self, **kwargs: Any) -> list[Path]:
        raise NotImplementedError("Implement source-specific historical chart ingestion.")

    def normalize(self, raw_files: list[Path]) -> None:
        raise NotImplementedError

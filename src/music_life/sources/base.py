from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any


class SourceAdapter(ABC):
    source_name: str

    @property
    def cache_dir(self) -> Path:
        path = Path("data/raw") / self.source_name
        path.mkdir(parents=True, exist_ok=True)
        return path

    @abstractmethod
    def fetch(self, **kwargs: Any) -> list[Path]:
        """Fetch data and return cached raw files."""

    @abstractmethod
    def normalize(self, raw_files: list[Path]) -> None:
        """Normalize cached source data into DuckDB."""

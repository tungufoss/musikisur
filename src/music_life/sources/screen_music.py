"""Film/TV music-use observations.

This adapter family is for evidence that a work/recording appeared in a movie
or TV episode. Each observation must retain its source and confidence.

Keep these concepts separate:
- screen title identity (TMDB/IMDb metadata);
- musical work;
- particular recording;
- evidence that the work/recording was used;
- optional scene/use context.

Never infer that a recording was used merely because the song title appears
in prose. Prefer recording-level matches; use work-level links when the exact
recording cannot be established.
"""
from pathlib import Path
from typing import Any
from .base import SourceAdapter


class Adapter(SourceAdapter):
    source_name = "screen_music"

    def fetch(self, **kwargs: Any) -> list[Path]:
        raise NotImplementedError("Implement source-specific screen-music evidence retrieval.")

    def normalize(self, raw_files: list[Path]) -> None:
        raise NotImplementedError

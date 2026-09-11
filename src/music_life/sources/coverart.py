"""Cover Art Archive: small front-cover thumbnails for focus albums.

https://coverartarchive.org serves artwork linked to MusicBrainz releases and release groups.
Only the 250 px thumbnail (a few tens of KB) is kept, as an identifying image; the artwork's
copyright stays with its owners. Which URL was used is recorded in data/raw/coverart/.
"""
from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import httpx

from .http import RAW_DIR, USER_AGENT

BASE_URL = "https://coverartarchive.org"


def record_path(target: Path) -> Path:
    return RAW_DIR / "coverart" / f"{target.stem}.json"


def download_front(target: Path, release_id: str, release_group_id: str, size: int = 250) -> dict[str, Any] | None:
    """Save the front cover to ``target`` unless already saved; prefer the chosen edition's cover.

    Returns {"url", "bytes"} for the image used, or None when neither has a front cover.
    """
    record = record_path(target)
    if target.exists() and record.exists():
        return json.loads(record.read_text(encoding="utf-8"))
    for entity, mbid in (("release", release_id), ("release-group", release_group_id)):
        url = f"{BASE_URL}/{entity}/{mbid}/front-{size}"
        response = httpx.get(url, headers={"User-Agent": USER_AGENT}, follow_redirects=True, timeout=30.0)
        if response.status_code == 404:
            continue
        response.raise_for_status()
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(response.content)
        info = {"url": url, "bytes": len(response.content)}
        record.parent.mkdir(parents=True, exist_ok=True)
        record.write_text(json.dumps(info), encoding="utf-8")
        return info
    return None


def source_row(target: Path, info: dict[str, Any]) -> dict[str, Any]:
    mtime = record_path(target).stat().st_mtime
    return {
        "source_key": "coverart-front",
        "source_name": "Cover Art Archive",
        "source_type": "image archive",
        "source_url": info["url"],
        "retrieved_at": datetime.fromtimestamp(int(mtime), UTC).replace(tzinfo=None),
        "citation_text": "Front cover thumbnail from the Cover Art Archive; artwork © its owners.",
    }

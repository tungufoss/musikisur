"""Discogs: master releases, editions, printed credits and community statistics.

API: https://www.discogs.com/developers (token auth, 60 requests per minute).
Attribution required on the site: "Data provided by Discogs."
"""
from __future__ import annotations

from typing import Any

from .http import CachedClient, require_env

BASE_URL = "https://api.discogs.com"


def client() -> CachedClient:
    return CachedClient(
        "discogs",
        BASE_URL,
        headers_factory=lambda: {"Authorization": f"Discogs token={require_env('DISCOGS_TOKEN')}"},
        min_interval=1.1,
    )


def fetch_master(master_id: int | str, c: CachedClient) -> dict[str, Any]:
    return c.get_json(f"masters/{master_id}", f"master-{master_id}")


def fetch_release(release_id: int | str, c: CachedClient) -> dict[str, Any]:
    return c.get_json(f"releases/{release_id}", f"release-{release_id}")


def source_row(c: CachedClient, master: dict[str, Any]) -> dict[str, Any]:
    return {
        "source_key": "discogs-master",
        "source_name": "Discogs",
        "source_type": "database",
        "source_url": f"https://www.discogs.com/master/{master['id']}",
        "retrieved_at": c.retrieved_at(f"master-{master['id']}"),
        "citation_text": f"Discogs master: {master['title']}. Data provided by Discogs.",
    }

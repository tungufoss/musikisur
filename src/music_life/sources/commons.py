"""Wikimedia Commons: small thumbnails of images linked from Wikidata (P18), with attribution.

Commons images are freely licensed but most licences require naming the author and licence,
so the author and licence are kept with the source and shown in the image caption.
"""
from __future__ import annotations

import html
import re
from pathlib import Path
from typing import Any

import httpx

from .http import USER_AGENT, CachedClient

BASE_URL = "https://commons.wikimedia.org"


def client() -> CachedClient:
    return CachedClient("commons", BASE_URL, min_interval=1.0)


def _key(filename: str) -> str:
    return "imageinfo-" + re.sub(r"[^a-z0-9]+", "-", filename.lower()).strip("-")


def _plain(value: str) -> str:
    return html.unescape(re.sub(r"<[^>]+>", "", value or "")).strip()


def image_info(filename: str, c: CachedClient, width: int = 250) -> dict[str, Any]:
    data = c.get_json("w/api.php", _key(filename), {
        "action": "query", "titles": f"File:{filename}", "prop": "imageinfo",
        "iiprop": "url|extmetadata|mime", "iiurlwidth": width, "format": "json", "formatversion": 2,
    })
    info = data["query"]["pages"][0]["imageinfo"][0]
    meta = info.get("extmetadata", {})
    return {
        "thumb_url": info["thumburl"],
        "page_url": info["descriptionurl"],
        "author": _plain(meta.get("Artist", {}).get("value", "")) or "óþekktur höfundur",
        "license": _plain(meta.get("LicenseShortName", {}).get("value", "")),
        "license_url": meta.get("LicenseUrl", {}).get("value"),
    }


def download(info: dict[str, Any], target: Path) -> None:
    """Save the thumbnail unless it is already there."""
    if target.exists():
        return
    response = httpx.get(info["thumb_url"], headers={"User-Agent": USER_AGENT}, follow_redirects=True, timeout=30.0)
    response.raise_for_status()
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(response.content)


def source_row(c: CachedClient, filename: str, info: dict[str, Any], key: str = "commons-artist-photo") -> dict[str, Any]:
    return {
        "source_key": key,
        "source_name": "Wikimedia Commons",
        "source_type": "image archive",
        "source_url": info["page_url"],
        "retrieved_at": c.retrieved_at(_key(filename)),
        "citation_text": f"{info['author']}, {info['license']}".strip(", "),
    }

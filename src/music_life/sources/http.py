"""Polite, cached JSON access to the source APIs.

Every response is stored under data/raw/<source>/<cache_key>.json (git-ignored). A later
run reads the cache instead of calling the API again, so a bundle can be rebuilt offline
and the exact raw input behind it can be inspected. Delete a cache file to refetch it.
"""
from __future__ import annotations

import json
import os
import time
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import httpx

REPO_ROOT = Path(__file__).resolve().parents[3]
RAW_DIR = REPO_ROOT / "data" / "raw"
USER_AGENT = "musikisur/0.1 ( https://github.com/tungufoss/musikisur )"
RETRY_STATUS = {429, 502, 503, 504}
# Longer Retry-After waits (Spotify can ask for hours) fail fast instead of hanging.
MAX_RETRY_WAIT = 60.0


def load_dotenv(path: Path = REPO_ROOT / ".env") -> None:
    """Load KEY=VALUE lines from .env without overriding real environment variables."""
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            key, value = line.split("=", 1)
            value = value.strip().strip('"').strip("'")
            if value:
                os.environ.setdefault(key.strip(), value)


def require_env(name: str) -> str:
    load_dotenv()
    value = os.environ.get(name, "").strip()
    if not value:
        raise RuntimeError(f"{name} is not set; add it to .env (see README 'API keys')")
    return value


class CachedClient:
    """GET JSON with a minimum interval between live requests and retry on busy servers.

    ``headers_factory`` is called only before the first live request, so rebuilding from
    the cache never needs credentials.
    """

    def __init__(
        self,
        source: str,
        base_url: str,
        headers_factory: Callable[[], dict[str, str]] | None = None,
        min_interval: float = 1.0,
        raw_dir: Path = RAW_DIR,
    ) -> None:
        self.cache_dir = raw_dir / source
        self.base_url = base_url.rstrip("/")
        self.headers_factory = headers_factory
        self.min_interval = min_interval
        self._headers: dict[str, str] | None = None
        self._last_request = 0.0

    def cache_path(self, cache_key: str) -> Path:
        return self.cache_dir / f"{cache_key}.json"

    def retrieved_at(self, cache_key: str) -> datetime:
        """When the cached response was fetched (UTC, from the cache file's timestamp)."""
        mtime = self.cache_path(cache_key).stat().st_mtime
        return datetime.fromtimestamp(int(mtime), UTC).replace(tzinfo=None)

    def _live_headers(self) -> dict[str, str]:
        if self._headers is None:
            extra = self.headers_factory() if self.headers_factory else {}
            self._headers = {"User-Agent": USER_AGENT, **extra}
        return self._headers

    def get_json(self, path: str, cache_key: str, params: dict[str, Any] | None = None) -> Any:
        cached = self.cache_path(cache_key)
        if cached.exists():
            return json.loads(cached.read_text(encoding="utf-8"))

        for attempt in range(6):
            wait = self.min_interval - (time.monotonic() - self._last_request)
            if wait > 0:
                time.sleep(wait)
            self._last_request = time.monotonic()
            try:
                response = httpx.get(
                    f"{self.base_url}/{path.lstrip('/')}",
                    params=params,
                    headers=self._live_headers(),
                    timeout=60.0,
                )
            except httpx.TransportError:
                # Timeouts and dropped connections: back off and try again.
                if attempt == 5:
                    raise
                time.sleep(2 ** attempt)
                continue
            if response.status_code not in RETRY_STATUS:
                break
            wait = float(response.headers.get("Retry-After", 2 ** attempt))
            if wait > MAX_RETRY_WAIT:
                raise RuntimeError(
                    f"{self.base_url} asks us to wait {wait:.0f} s (HTTP {response.status_code}); "
                    "try again later"
                )
            time.sleep(wait)
        response.raise_for_status()

        data = response.json()
        cached.parent.mkdir(parents=True, exist_ok=True)
        cached.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
        return data

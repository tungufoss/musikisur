"""Smoke tests that each API credential is accepted by its provider.

Each test makes one small read-only request. Tokens are never printed.
Locally, missing keys are skipped; set REQUIRE_API_TOKENS=1 (as CI does) to fail instead.
"""
import os

import httpx
import pytest

pytestmark = pytest.mark.live

USER_AGENT = "musikisur/0.1 +https://github.com/tungufoss/musikisur"
TIMEOUT = 20.0


def require(*names: str) -> list[str]:
    values = [os.environ.get(name, "").strip() for name in names]
    missing = [name for name, value in zip(names, values) if not value]
    if missing:
        message = f"missing {', '.join(missing)}"
        if os.environ.get("REQUIRE_API_TOKENS") == "1":
            pytest.fail(message)
        pytest.skip(message)
    return values


def test_discogs_token():
    (token,) = require("DISCOGS_TOKEN")
    response = httpx.get(
        "https://api.discogs.com/oauth/identity",
        headers={"Authorization": f"Discogs token={token}", "User-Agent": USER_AGENT},
        timeout=TIMEOUT,
    )
    assert response.status_code == 200, f"Discogs rejected the token (HTTP {response.status_code})"
    assert response.json().get("username")


def test_spotify_client_credentials():
    client_id, client_secret = require("SPOTIFY_CLIENT_ID", "SPOTIFY_CLIENT_SECRET")
    token_response = httpx.post(
        "https://accounts.spotify.com/api/token",
        data={"grant_type": "client_credentials"},
        auth=(client_id, client_secret),
        timeout=TIMEOUT,
    )
    assert token_response.status_code == 200, (
        f"Spotify rejected the client ID/secret (HTTP {token_response.status_code})"
    )
    access_token = token_response.json()["access_token"]

    search = httpx.get(
        "https://api.spotify.com/v1/search",
        params={"q": "album:City to City artist:Gerry Rafferty", "type": "album", "limit": 1},
        headers={"Authorization": f"Bearer {access_token}"},
        timeout=TIMEOUT,
    )
    assert search.status_code == 200, f"Spotify Web API call failed (HTTP {search.status_code})"


def test_tmdb_read_access_token():
    (token,) = require("TMDB_API_TOKEN")
    response = httpx.get(
        "https://api.themoviedb.org/3/authentication",
        headers={"Authorization": f"Bearer {token}", "accept": "application/json"},
        timeout=TIMEOUT,
    )
    assert response.status_code == 200, (
        f"TMDB rejected the token (HTTP {response.status_code}); "
        "use the API Read Access Token, not the short API Key"
    )
    assert response.json().get("success") is True

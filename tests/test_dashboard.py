"""Offline tests for the page helpers in music_life.dashboard."""
from music_life.dashboard import spotify_link


def test_spotify_link_carries_the_embed_url_for_the_in_page_player():
    html = spotify_link("https://open.spotify.com/album/35yZZTWeSrszSKjRlFETwf")
    assert 'href="https://open.spotify.com/album/35yZZTWeSrszSKjRlFETwf"' in html
    assert 'data-spotify-embed="https://open.spotify.com/embed/album/35yZZTWeSrszSKjRlFETwf"' in html


def test_non_spotify_urls_stay_plain_links():
    assert "data-spotify-embed" not in spotify_link("https://example.org/song")

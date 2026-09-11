"""Offline tests for film and TV credits (IMDb export plus TMDB ranking)."""
from music_life.sources import screen


def test_imdb_songs_take_the_artists_spelling():
    known = ["Stuck in the Middle With You", "Baker Street"]
    assert screen.canonical_song("Stuck in the Middle", known) == "Stuck in the Middle With You"
    assert screen.canonical_song("stuck in the middle with you", known) == "Stuck in the Middle With You"
    assert screen.canonical_song("Mary Skeffington", known) == "Mary Skeffington"


def test_song_links_start_with_whoever_released_the_song_first():
    def search(performer, song):
        hit = {"name": song, "artists": [{"name": performer}], "album": {"release_date": "1972"},
               "external_urls": {"spotify": f"https://open.spotify.com/track/{performer}"}}
        return (hit if song != "Unrecorded" else None), f"key-{performer}"

    rows = screen.song_links(
        ["Stuck in the Middle With You", "Baker Street", "Unrecorded"], ["Gerry Rafferty", "Stealers Wheel"],
        search, owners={"Stuck in the Middle with You": "Stealers Wheel"},
    )
    assert [(r["song"], r["cache_key"]) for r in rows] == [
        ("Stuck in the Middle With You", "key-Stealers Wheel"), ("Baker Street", "key-Gerry Rafferty"),
    ]


def test_credit_rows_split_kinds_and_years_and_rank_with_tmdb():
    export = {"retrieved_at": "2026-09-11T22:50:00", "credits": [
        {"id": "tt1", "title": "Show", "type": "TV Series", "years": "1997–2015", "episodes": 3,
         "rating": 8.6, "songs": ["Stuck in the Middle", "Baker Street"]},
        {"id": "tt2", "title": "Film", "type": "Movie", "years": "1992", "episodes": None,
         "rating": 8.2, "songs": ["Stuck in the Middle with You"]},
        {"id": "tt3", "title": "Clip", "type": "Video", "years": "2003", "episodes": None,
         "rating": None, "songs": ["Baker Street"]},
    ]}
    lookup = {"tt1": {"type": "tv", "id": 456, "votes": 9000}, "tt2": {"type": "movie", "id": 500, "votes": 15804}}.get
    rows = {r["imdb_id"]: r for r in screen.credit_rows(export, ["Baker Street", "Stuck in the Middle With You"], lookup)}
    assert (rows["tt1"]["kind"], rows["tt1"]["first_year"], rows["tt1"]["last_year"]) == ("tv", 1997, 2015)
    assert rows["tt1"]["songs"] == "Baker Street; Stuck in the Middle With You"
    assert rows["tt2"]["tmdb_url"] == "https://www.themoviedb.org/movie/500"
    assert rows["tt3"]["kind"] == "other" and rows["tt3"]["tmdb_votes"] is None

"""Offline tests for the artist context: Wikipedia places, dates with precision, album events."""
from datetime import date

from music_life import curation
from music_life.sources import musicbrainz, wikidata, wikipedia


def test_context_sentence_finds_first_mention_outside_headings():
    text = (
        "Intro line.\n== Early life ==\nHe was born in Paisley, Renfrewshire. "
        "Later he lived in Paisley again.\nIn 2008 he moved away from California."
    )
    sentences = wikipedia.sentences(text)
    assert wikipedia.context_sentence(sentences, "Paisley, Renfrewshire") == "He was born in Paisley, Renfrewshire."
    assert wikipedia.context_sentence(sentences, "California") == "In 2008 he moved away from California."
    assert wikipedia.context_sentence(sentences, "Highland (council area)") is None


def test_dates_keep_their_precision():
    assert curation.parse_date(date(1992, 9, 18)) == ("1992-09-18", 11)
    assert curation.parse_date(1998) == ("1998-01-01", 9)
    assert curation.parse_date("1988-06") == ("1988-06-01", 10)

    career = {"claims": {"P2031": [{"mainsnak": {"datavalue": {"value": {"time": "+1966-00-00T00:00:00Z", "precision": 9}}}}]}}
    assert wikidata.claim_time(career, "P2031") == ("1966-01-01", 9)


def test_song_events_count_each_song_once_at_its_first_release():
    recordings = [
        {"id": "1", "title": "Baker Street", "first-release-date": "1978-01-20"},
        {"id": "2", "title": "Baker Street (original demo)", "first-release-date": "2011-09-05"},
        {"id": "3", "title": "Baker Street (live)", "first-release-date": "1979"},
        {"id": "4", "title": "Night Owl", "first-release-date": "1979"},
        {"id": "5", "title": "Unreleased", "first-release-date": ""},
    ]
    rows = sorted((r["label"], r["event_date"]) for r in musicbrainz.song_events(recordings, "solo", "mb"))
    assert rows == [("Baker Street", "1978-01-20"), ("Night Owl", "1979-01-01")]


def test_work_for_others_counts_each_song_once():
    def row(date, kind, label):
        return {"event_date": date, "kind": kind, "label": label}

    rows = musicbrainz.unique_songs([
        row("1988-01-01", "production", "The Proclaimers – Letter From America"),
        row("1987-01-01", "production", "The Proclaimers – Letter From America (Band version)"),
        row("1993-01-01", "guest", "Richard & Linda Thompson – For Shame of Doing Wrong"),
        row("1993-01-01", "production", "Richard & Linda Thompson – For Shame of Doing Wrong"),
    ])
    assert sorted((r["event_date"], r["kind"]) for r in rows) == [
        ("1987-01-01", "production"), ("1993-01-01", "production"),
    ]


def test_album_events_keep_dated_studio_albums_only():
    groups = {"release-groups": [
        {"id": "a", "title": "Studio", "first-release-date": "1978", "secondary-types": []},
        {"id": "b", "title": "Best Of", "first-release-date": "1989", "secondary-types": ["Compilation"]},
        {"id": "c", "title": "Undated", "first-release-date": "", "secondary-types": []},
        {"id": "d", "title": "Late", "first-release-date": "2021-09-01", "secondary-types": []},
    ]}
    rows = [(r["label"], r["event_date"], r["date_precision"]) for r in musicbrainz.album_events(groups)]
    assert rows == [("Studio", "1978-01-01", 9), ("Late", "2021-09-01", 11)]

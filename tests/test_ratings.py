import json

import pytest

import ratings
import storage


@pytest.fixture(autouse=True)
def isolate_ratings_path(tmp_path, monkeypatch):
    """Point ratings.py at a throwaway file so tests never touch real data/."""
    path = tmp_path / "ratings.json"
    monkeypatch.setattr(ratings, "RATINGS_PATH", str(path))
    return path


def make_song(title="Thunderstruck", artist="AC/DC"):
    return {"title": title, "artist": artist, "genre": "rock", "energy": 9, "tags": []}


def test_get_rating_never_rated_returns_none():
    song = make_song()
    assert ratings.get_rating(song) is None


def test_rate_song_persists_to_disk(isolate_ratings_path):
    song = make_song()
    ratings.rate_song(song, 4)

    # Prove it's actually on disk, not just in-memory -- read the JSON file
    # directly rather than going through get_rating again.
    on_disk = json.loads(isolate_ratings_path.read_text(encoding="utf-8"))
    key = ratings.song_key(song)
    assert on_disk[key] == 4


def test_rate_song_round_trip_survives_simulated_restart(isolate_ratings_path):
    song = make_song()
    ratings.rate_song(song, 5)

    # Simulate a restart: load straight from storage.py rather than reusing
    # any in-memory state from rate_song's call.
    reloaded = storage.load_json(str(isolate_ratings_path), default={})
    assert reloaded[ratings.song_key(song)] == 5

    # And get_rating (a fresh call, no cached state) agrees.
    assert ratings.get_rating(song) == 5


def test_clear_rating_returns_to_unrated_never_zero():
    song = make_song()
    ratings.rate_song(song, 3)
    assert ratings.get_rating(song) == 3

    ratings.clear_rating(song)
    assert ratings.get_rating(song) is None
    assert ratings.get_rating(song) != 0


def test_clear_rating_on_never_rated_song_is_a_noop():
    song = make_song()
    ratings.clear_rating(song)  # should not raise
    assert ratings.get_rating(song) is None


@pytest.mark.parametrize("bad_stars", [0, 6, -1, 100])
def test_rate_song_out_of_range_raises_value_error(bad_stars):
    song = make_song()
    with pytest.raises(ValueError):
        ratings.rate_song(song, bad_stars)

    # the invalid attempt must not have been persisted
    assert ratings.get_rating(song) is None


def test_rate_song_non_int_stars_raises_value_error():
    song = make_song()
    with pytest.raises(ValueError):
        ratings.rate_song(song, "5")


def test_different_artists_same_title_get_different_keys():
    song_a = make_song(title="Thunderstruck", artist="AC/DC")
    song_b = make_song(title="Thunderstruck", artist="Some Cover Band")

    ratings.rate_song(song_a, 5)
    ratings.rate_song(song_b, 1)

    assert ratings.song_key(song_a) != ratings.song_key(song_b)
    assert ratings.get_rating(song_a) == 5
    assert ratings.get_rating(song_b) == 1


def test_song_key_normalizes_case_and_whitespace():
    song_a = make_song(title="  Thunderstruck  ", artist="AC/DC")
    song_b = make_song(title="Thunderstruck", artist="  ac/dc  ")

    assert ratings.song_key(song_a) == ratings.song_key(song_b)


def test_all_ratings_returns_full_map():
    song_a = make_song(title="Thunderstruck", artist="AC/DC")
    song_b = make_song(title="Lo-fi Rain", artist="DJ Calm")

    ratings.rate_song(song_a, 4)
    ratings.rate_song(song_b, 2)

    result = ratings.all_ratings()
    assert result[ratings.song_key(song_a)] == 4
    assert result[ratings.song_key(song_b)] == 2
    assert len(result) == 2

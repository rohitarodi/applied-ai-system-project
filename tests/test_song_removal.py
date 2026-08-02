from app import remove_song_from_library, most_recent_songs


def _song(title, artist="Someone"):
    return {"title": title, "artist": artist, "genre": "rock", "energy": 5, "tags": []}


def test_remove_song_from_library_removes_matching_song():
    songs = [_song("A"), _song("B"), _song("C")]
    result = remove_song_from_library(songs, _song("B"))
    assert [s["title"] for s in result] == ["A", "C"]


def test_remove_song_from_library_no_match_is_noop():
    songs = [_song("A"), _song("B")]
    result = remove_song_from_library(songs, _song("Z"))
    assert [s["title"] for s in result] == ["A", "B"]


def test_remove_song_from_library_matches_by_normalized_title_artist():
    songs = [_song("  A  ", "Bob")]
    result = remove_song_from_library(songs, _song("A", "BOB"))
    assert result == []


def test_most_recent_songs_returns_last_n_reversed():
    songs = [_song(str(i)) for i in range(10)]
    recent = most_recent_songs(songs, 5)
    assert [s["title"] for s in recent] == ["9", "8", "7", "6", "5"]


def test_most_recent_songs_handles_fewer_than_n():
    songs = [_song("A"), _song("B")]
    recent = most_recent_songs(songs, 5)
    assert [s["title"] for s in recent] == ["B", "A"]


def test_most_recent_songs_empty_list():
    assert most_recent_songs([], 5) == []

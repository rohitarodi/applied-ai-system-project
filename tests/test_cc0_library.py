import cc0_library
from playlist_logic import normalize_song


def test_curated_list_has_exactly_six_tracks():
    assert len(cc0_library.CC0_TRACKS) == 6


def test_every_track_has_a_valid_archive_url_audio_field():
    for track in cc0_library.CC0_TRACKS:
        audio = track["audio"]
        assert audio["source_type"] == "archive_url"
        assert isinstance(audio["url"], str) and audio["url"]


def test_normalize_song_does_not_have_an_audio_key():
    # normalize_song() only recognizes title/artist/genre/energy/tags and
    # rebuilds a fresh dict, so `audio` must never survive normalization on
    # its own -- it has to be reattached afterward (same pattern app.py's
    # add_song_sidebar() uses).
    normalized = normalize_song(cc0_library.CC0_TRACKS[0])
    assert "audio" not in normalized


def test_normalized_cc0_tracks_keep_audio_field_after_normalization():
    normalized = cc0_library.normalized_cc0_tracks()
    assert len(normalized) == 6
    for original, song in zip(cc0_library.CC0_TRACKS, normalized):
        assert song["audio"] == original["audio"]
        assert song["title"] == original["title"].strip()

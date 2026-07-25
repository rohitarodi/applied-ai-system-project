import os

import audio_source


def test_local_existing_supported_file_is_playable(tmp_path):
    audio_file = tmp_path / "clip.wav"
    audio_file.write_bytes(b"RIFF....WAVEfmt ")  # content doesn't matter for the guard

    song = {"title": "Test Song", "audio": {"source_type": "local", "path": str(audio_file)}}
    result = audio_source.resolve(song)

    assert result.playable is True
    assert result.reference == str(audio_file)
    assert result.reason is None


def test_local_missing_file_is_not_playable(tmp_path):
    missing_path = str(tmp_path / "nope.wav")
    song = {"title": "Ghost Song", "audio": {"source_type": "local", "path": missing_path}}

    result = audio_source.resolve(song)

    assert result.playable is False
    assert result.reason == "file not found"


def test_local_unsupported_extension_is_not_playable(tmp_path):
    audio_file = tmp_path / "clip.flac"
    audio_file.write_bytes(b"fLaC")

    song = {"title": "Lossless Song", "audio": {"source_type": "local", "path": str(audio_file)}}
    result = audio_source.resolve(song)

    assert result.playable is False
    assert "unsupported" in result.reason.lower()


def test_local_supports_mp3_and_ogg_extensions(tmp_path):
    for ext in ("mp3", "ogg"):
        audio_file = tmp_path / f"clip.{ext}"
        audio_file.write_bytes(b"data")
        song = {"title": f"Song {ext}", "audio": {"source_type": "local", "path": str(audio_file)}}

        result = audio_source.resolve(song)

        assert result.playable is True, f"{ext} should be supported"


def test_unknown_source_type_is_not_playable_and_does_not_crash():
    song = {"title": "Archive Song", "audio": {"source_type": "archive_url", "url": "https://example.com/x.mp3"}}

    result = audio_source.resolve(song)

    assert result.playable is False
    assert result.reason == "unsupported source_type"


def test_missing_audio_field_does_not_crash():
    song = {"title": "No Audio Field"}

    result = audio_source.resolve(song)

    assert result.playable is False
    assert result.reason is not None

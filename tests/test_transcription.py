import os

import transcription


def test_import_never_raises_even_without_faster_whisper():
    # If we got this far, `import transcription` at the top of this file
    # already succeeded without faster_whisper being installed -- this test
    # just documents that as an explicit assertion.
    assert transcription is not None


def test_isolated_failure_path_does_not_propagate_exception():
    def fake_loader_that_raises(audio_reference):
        raise ModuleNotFoundError("No module named 'faster_whisper'")

    song = {"title": "Some Song", "artist": "Some Artist"}
    result = transcription.transcribe(
        song, "path/to/audio.wav", model_loader=fake_loader_that_raises
    )

    assert result.available is False
    assert result.text is None
    assert isinstance(result.reason, str) and len(result.reason) > 0


def test_isolated_failure_path_catches_arbitrary_runtime_errors():
    def fake_loader_that_blows_up(audio_reference):
        raise RuntimeError("model failed to load: no network access")

    song = {"title": "Some Song", "artist": "Some Artist"}
    result = transcription.transcribe(
        song, "https://example.com/clip.mp3", model_loader=fake_loader_that_blows_up
    )

    assert result.available is False
    assert result.text is None
    assert "model failed to load" in result.reason


def test_success_path_with_injected_fake_transcriber():
    def fake_loader_that_succeeds(audio_reference):
        return "never gonna give you up, never gonna let you down"

    song = {"title": "Karaoke Song", "artist": "Someone"}
    result = transcription.transcribe(
        song, "data/samples/tone_a.wav", model_loader=fake_loader_that_succeeds
    )

    assert result.available is True
    assert result.text == "never gonna give you up, never gonna let you down"
    assert result.reason is None


def test_no_audio_reference_is_unavailable_without_calling_loader():
    calls = []

    def fake_loader(audio_reference):
        calls.append(audio_reference)
        return "should not be called"

    song = {"title": "No Audio Song"}
    result = transcription.transcribe(song, "", model_loader=fake_loader)

    assert result.available is False
    assert result.text is None
    assert result.reason
    assert calls == []


def test_empty_transcription_result_is_treated_as_unavailable():
    def fake_loader_returns_empty(audio_reference):
        return ""

    song = {"title": "Silent Song"}
    result = transcription.transcribe(
        song, "data/samples/tone_b.wav", model_loader=fake_loader_returns_empty
    )

    assert result.available is False
    assert result.text is None
    assert result.reason


def test_local_path_for_local_reference_is_passed_through_unchanged():
    with transcription._local_path_for("data/samples/tone_a.wav") as local_path:
        assert local_path == "data/samples/tone_a.wav"


def test_local_path_for_url_downloads_and_cleans_up_temp_file(monkeypatch):
    captured = {}

    def fake_urlretrieve(url, tmp_path):
        captured["path"] = tmp_path
        with open(tmp_path, "wb") as f:
            f.write(b"fake audio bytes")

    monkeypatch.setattr(transcription, "urlretrieve", fake_urlretrieve)

    with transcription._local_path_for("https://example.com/clip.ogg") as local_path:
        assert local_path == captured["path"]
        assert local_path.endswith(".ogg")
        assert os.path.exists(local_path)

    # Temp file must be cleaned up after the context manager exits, success
    # or failure.
    assert not os.path.exists(captured["path"])


def test_local_path_for_url_cleans_up_temp_file_on_download_failure(monkeypatch):
    captured = {}

    def fake_urlretrieve_that_fails(url, tmp_path):
        captured["path"] = tmp_path
        raise OSError("network error: timed out")

    monkeypatch.setattr(transcription, "urlretrieve", fake_urlretrieve_that_fails)

    raised = False
    try:
        with transcription._local_path_for("https://example.com/clip.mp3") as _local_path:
            pass
    except OSError:
        raised = True

    assert raised
    assert not os.path.exists(captured["path"])


def test_transcribe_surfaces_url_download_failure_as_isolated_unavailable(monkeypatch):
    def fake_urlretrieve_that_fails(url, tmp_path):
        raise OSError("network error: timed out")

    monkeypatch.setattr(transcription, "urlretrieve", fake_urlretrieve_that_fails)

    song = {"title": "Archive Song", "artist": "Someone"}
    result = transcription.transcribe(
        song, "https://example.com/clip.mp3", model_loader=transcription._load_and_transcribe
    )

    # _load_and_transcribe will fail either on the faster_whisper import (if
    # not installed) or on the download (patched to fail here) -- either way
    # it must surface through transcribe()'s single existing catch point as
    # an isolated unavailable result, never an exception.
    assert result.available is False
    assert result.text is None
    assert isinstance(result.reason, str) and len(result.reason) > 0

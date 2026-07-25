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

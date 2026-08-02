"""Standalone TranscriptionTool: generate karaoke/lyrics text for a Song.

Uses a local faster-whisper model (tiny/base size) to transcribe a Song's
resolved audio reference into text. `faster_whisper` is a heavy optional
dependency that may not be installed (or may fail to download/load its
model with no network) in a given environment. This module is a designed
isolation boundary: NOTHING in here may ever let an exception escape
`transcribe()`. Every failure mode -- missing package, model load failure,
transcription runtime error -- is caught and converted into a typed
`TranscriptionResult(available=False, ...)` so the rest of the app (audio
playback, ratings, VibeQuery) keeps working regardless of whether this
tool can function at all.

Standalone, user-invoked in this ticket. Agent tool-call integration
(letting the RecommendationAgent invoke this itself) is a later ticket --
this module does not import or wire into any agent flow.
"""

import os
import tempfile
from contextlib import contextmanager
from dataclasses import dataclass
from typing import Callable, Optional
from urllib.parse import urlsplit
from urllib.request import Request, urlopen

# Wikimedia (and some other hosts) reject the default urllib User-Agent with
# a 403 -- identify the request honestly instead of spoofing a browser.
_DOWNLOAD_USER_AGENT = "PlaylistChaos-TranscriptionTool/1.0"


def urlretrieve(url: str, dest_path: str, timeout: int = 20) -> None:
    """Download `url` to `dest_path`. Thin wrapper so tests can monkeypatch
    this single call point without needing real network access."""
    request = Request(url, headers={"User-Agent": _DOWNLOAD_USER_AGENT})
    with urlopen(request, timeout=timeout) as response, open(dest_path, "wb") as f:
        f.write(response.read())


@dataclass
class TranscriptionResult:
    available: bool
    text: Optional[str] = None
    reason: Optional[str] = None


@contextmanager
def _local_path_for(audio_reference: str):
    """Yield a local filesystem path for `audio_reference`.

    faster-whisper's WhisperModel.transcribe() only accepts a local file
    path, not a URL. If `audio_reference` is already local (the common case
    for "local" source_type songs), it's yielded unchanged -- no download,
    no temp file. If it's an http(s) URL (archive_url songs), it's
    downloaded to a temp file first (extension inferred from the URL so
    faster-whisper's format sniffing works), which is always cleaned up on
    the way out, success or failure.
    """
    if not audio_reference.startswith(("http://", "https://")):
        yield audio_reference
        return

    _, ext = os.path.splitext(urlsplit(audio_reference).path)
    fd, tmp_path = tempfile.mkstemp(suffix=ext or ".audio")
    os.close(fd)
    try:
        urlretrieve(audio_reference, tmp_path)  # noqa: S310 -- known http(s) archive URL
        yield tmp_path
    finally:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)


def _load_and_transcribe(audio_reference: str) -> str:
    """Real implementation: lazily import faster_whisper, load a small model,
    and transcribe the given audio reference.

    Imported lazily (inside this function, not at module top-level) so that
    `import transcription` never fails just because `faster_whisper` isn't
    installed -- anything importing this module for unrelated reasons (e.g.
    the test suite) must not explode on the missing optional dependency.
    """
    from faster_whisper import WhisperModel  # heavy optional dependency

    with _local_path_for(audio_reference) as local_path:
        # "tiny" is the smallest/fastest model size -- appropriate for a
        # local, best-effort karaoke/lyrics tool rather than a production
        # transcription service.
        model = WhisperModel("tiny")
        segments, _info = model.transcribe(local_path)
        return " ".join(segment.text.strip() for segment in segments).strip()


def transcribe(
    song: dict,
    audio_reference: str,
    model_loader: Optional[Callable[[str], str]] = None,
) -> TranscriptionResult:
    """Attempt to transcribe `audio_reference` into karaoke/lyrics text.

    `model_loader` is an injectable dependency: a callable that takes the
    audio reference and returns transcribed text (or raises). Defaults to
    the real faster-whisper-backed loader. Tests inject a fake here --
    one that raises (simulating "package not installed" / "model failed to
    load") and one that returns canned text (simulating success) -- so the
    isolated-failure path and the success path can both be exercised
    without the real model being installed anywhere.

    This function is the designed isolation boundary described in
    CONTEXT.md's TranscriptionTool entry: failure or absence of the
    underlying model must never break Queue generation or playback, so
    every exception raised by the loader -- import errors, model load
    errors, bad-audio runtime errors, anything -- is caught here (broad
    `except Exception` is intentional, not sloppy) and converted into a
    typed unavailable result instead of propagating to the caller.
    """
    loader = model_loader if model_loader is not None else _load_and_transcribe

    if not audio_reference:
        return TranscriptionResult(
            available=False, text=None, reason="no audio reference to transcribe"
        )

    try:
        text = loader(audio_reference)
    except Exception as exc:  # noqa: BLE001 -- intentional isolation boundary
        return TranscriptionResult(available=False, text=None, reason=str(exc) or type(exc).__name__)

    if not text:
        return TranscriptionResult(
            available=False, text=None, reason="transcription produced no text"
        )

    return TranscriptionResult(available=True, text=text, reason=None)

"""Resolve a Song's AudioSource into something playable (or a guard reason).

This module is a designed seam: `resolve()` is the one function every later
ticket (archive_url support in Ticket 2, playback calls elsewhere) is meant
to call. Keep its signature stable: resolve(song: dict) -> AudioSourceResult.

Ticket 1 only implements the "local" source_type. Anything else (e.g. the
future "archive_url") is recognized but not yet handled — it returns a
graceful not-playable result instead of raising, so app.py never crashes on
an unimplemented source type.
"""

import os
from dataclasses import dataclass
from typing import Optional

SUPPORTED_LOCAL_EXTENSIONS = {".wav", ".mp3", ".ogg"}


@dataclass
class AudioSourceResult:
    playable: bool
    reference: Optional[str] = None
    reason: Optional[str] = None


def resolve(song: dict) -> AudioSourceResult:
    """Resolve a song's audio field into a playable reference or a guard reason."""
    audio = song.get("audio") if isinstance(song, dict) else None

    if not audio or not isinstance(audio, dict):
        return AudioSourceResult(playable=False, reference=None, reason="no audio source configured")

    source_type = audio.get("source_type")

    if source_type == "local":
        return _resolve_local(audio)

    return AudioSourceResult(playable=False, reference=None, reason="unsupported source_type")


def _resolve_local(audio: dict) -> AudioSourceResult:
    path = audio.get("path")

    if not path:
        return AudioSourceResult(playable=False, reference=None, reason="no path configured")

    _, ext = os.path.splitext(path)
    if ext.lower() not in SUPPORTED_LOCAL_EXTENSIONS:
        return AudioSourceResult(
            playable=False,
            reference=path,
            reason=f"unsupported audio format: {ext or '(no extension)'}",
        )

    if not os.path.isfile(path):
        return AudioSourceResult(playable=False, reference=path, reason="file not found")

    return AudioSourceResult(playable=True, reference=path, reason=None)

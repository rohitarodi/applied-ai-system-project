"""Rating CRUD for songs, persisted via storage.py.

Design choice (Ticket 3): a Rating is a user-assigned 1-5 star score for a
Song. Absence of a Rating means "unrated" -- represented as the song's key
simply not being present in the ratings map, and surfaced to callers as
``None`` from ``get_rating``. This is never conflated with 0 or any other
numeric default: a later ticket (RatingPredictor) depends on being able to
tell "never rated" apart from "rated low", so unrated must stay a distinct
absence, not a value.

Songs don't currently carry a unique id field, so ratings are keyed by a
composite ``f"{title}::{artist}"`` string, normalized through the same
``normalize_title``/``normalize_artist`` helpers playlist_logic.py already
uses elsewhere -- reusing those exact normalizers (rather than writing new
ones here) keeps keys consistent regardless of case/whitespace differences
between where a song was added and where it's later rated.

Ratings persist to data/ratings.json (gitignored runtime state, see
.gitignore and storage.py's docstring). Every write calls storage.save_json
immediately -- there is no in-memory-only state here, so a rating survives
an app restart.
"""

from typing import Dict, Optional

import storage
from playlist_logic import Song, normalize_artist, normalize_title

RATINGS_PATH = "data/ratings.json"


def song_key(song: Song) -> str:
    """Return the stable composite key used to look up a song's rating."""
    title = normalize_title(str(song.get("title", "")))
    artist = normalize_artist(str(song.get("artist", "")))
    return f"{title}::{artist}"


def _load() -> Dict[str, int]:
    return storage.load_json(RATINGS_PATH, default={})


def _save(ratings: Dict[str, int]) -> None:
    storage.save_json(RATINGS_PATH, ratings)


def rate_song(song: Song, stars: int) -> None:
    """Persist a 1-5 star rating for ``song``.

    Raises ValueError if ``stars`` is out of the 1-5 range. This is a
    programming-contract violation, not a guardrail-worthy user input path --
    the UI constrains the widget to valid values already.
    """
    if not isinstance(stars, int) or isinstance(stars, bool) or not (1 <= stars <= 5):
        raise ValueError(f"stars must be an int in 1-5, got {stars!r}")

    ratings = _load()
    ratings[song_key(song)] = stars
    _save(ratings)


def get_rating(song: Song) -> Optional[int]:
    """Return the persisted rating for ``song``, or None if unrated.

    Never returns 0 -- unrated is always represented as None.
    """
    ratings = _load()
    return ratings.get(song_key(song))


def clear_rating(song: Song) -> None:
    """Remove any persisted rating for ``song``, restoring "unrated"."""
    ratings = _load()
    key = song_key(song)
    if key in ratings:
        del ratings[key]
        _save(ratings)


def all_ratings() -> Dict[str, int]:
    """Return the full song_key -> stars ratings map."""
    return _load()

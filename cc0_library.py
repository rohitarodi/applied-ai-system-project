"""Curated list of real, public-domain (Wikimedia Commons) music tracks.

Addresses "add songs from the internet without pasting one URL at a time":
a one-click, idempotent import of a small fixed list, rather than a general
web-search/import feature. These are REAL classical recordings (not the
synthetic sine-wave tones in data/samples/) hosted on upload.wikimedia.org --
stable, no auth, no rate limit for normal playback.

All six tracks are instrumental (no vocals) -- transcription on them will
legitimately produce empty/near-empty text. That's correct behavior via
transcription.py's existing "transcription produced no text" unavailable
path, not a bug.
"""

from typing import List

from playlist_logic import Song

CC0_TRACKS: List[Song] = [
    {
        "title": "Clair de Lune (Orchestral)",
        "artist": "Claude Debussy",
        "genre": "ambient",
        "energy": 2,
        "tags": ["piano", "classical", "cc0-import"],
        "audio": {
            "source_type": "archive_url",
            "url": "https://upload.wikimedia.org/wikipedia/commons/b/be/Clair_de_lune_%28Claude_Debussy%29_Suite_bergamasque.ogg",
        },
    },
    {
        "title": "Symphony No. 5 (III. Allegro)",
        "artist": "Ludwig van Beethoven",
        "genre": "classical",
        "energy": 7,
        "tags": ["orchestral", "classic"],
        "audio": {
            "source_type": "archive_url",
            "url": "https://upload.wikimedia.org/wikipedia/commons/5/5b/Ludwig_van_Beethoven_-_symphony_no._5_in_c_minor%2C_op._67_-_iii._allegro.ogg",
        },
    },
    {
        "title": "Eine kleine Nachtmusik (I. Allegro)",
        "artist": "Wolfgang Amadeus Mozart",
        "genre": "classical",
        "energy": 6,
        "tags": ["orchestral", "strings"],
        "audio": {
            "source_type": "archive_url",
            "url": "https://upload.wikimedia.org/wikipedia/commons/2/24/Mozart_-_Eine_kleine_Nachtmusik_-_1._Allegro.ogg",
        },
    },
    {
        "title": "Ride of the Valkyries",
        "artist": "Richard Wagner",
        "genre": "classical",
        "energy": 10,
        "tags": ["orchestral", "epic", "cc0-import"],
        "audio": {
            "source_type": "archive_url",
            "url": "https://upload.wikimedia.org/wikipedia/commons/2/29/Richard_Wagner_-_Ride_of_the_Valkyries.ogg",
        },
    },
    {
        "title": "1812 Overture",
        "artist": "Pyotr Ilyich Tchaikovsky",
        "genre": "classical",
        "energy": 9,
        "tags": ["orchestral", "epic"],
        "audio": {
            "source_type": "archive_url",
            "url": "https://upload.wikimedia.org/wikipedia/commons/0/04/Pyotr_Ilyich_Tchaikovsky_-_1812_overture.ogg",
        },
    },
    {
        "title": "Moonlight Sonata (II. Movement)",
        "artist": "Ludwig van Beethoven",
        "genre": "ambient",
        "energy": 3,
        "tags": ["piano", "calm"],
        "audio": {
            "source_type": "archive_url",
            "url": "https://upload.wikimedia.org/wikipedia/commons/4/47/Beethoven_Moonlight_2nd_movement.ogg",
        },
    },
]


def normalized_cc0_tracks() -> List[Song]:
    """Return CC0_TRACKS run through normalize_song(), audio field reattached.

    normalize_song() only recognizes title/artist/genre/energy/tags and
    rebuilds a fresh dict -- same fix pattern app.py's add_song_sidebar()
    already uses: normalize first, then attach `audio` onto the result.
    """
    from playlist_logic import normalize_song

    result = []
    for raw in CC0_TRACKS:
        normalized = normalize_song(raw)
        normalized["audio"] = dict(raw["audio"])
        result.append(normalized)
    return result

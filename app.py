import streamlit as st

import agent
import audio_source
import cc0_library
import ratings
import retrieval
import storage
import transcription
from playlist_logic import (
    DEFAULT_PROFILE,
    Song,
    build_playlists,
    classify_song,
    compute_playlist_stats,
    history_summary,
    lucky_pick,
    merge_playlists,
    normalize_song,
    search_songs,
)

LIBRARY_PATH = "data/library.json"
LOCAL_SAMPLE_FILES = [
    "data/samples/tone_a.wav",
    "data/samples/tone_b.wav",
    "data/samples/tone_c.wav",
]

# Star widget options. Index 0 ("Unrated") is a distinct state, never a
# numeric 0 -- absence of a rating must never be confused with "rated 0".
STAR_OPTIONS = ["Unrated", "★", "★★", "★★★", "★★★★", "★★★★★"]


def _stars_to_option(stars):
    """Map a persisted rating (int 1-5 or None) to a STAR_OPTIONS label."""
    if stars is None:
        return STAR_OPTIONS[0]
    return STAR_OPTIONS[stars]


def _option_to_stars(option):
    """Map a STAR_OPTIONS label back to a rating (int 1-5 or None)."""
    if option == STAR_OPTIONS[0]:
        return None
    return STAR_OPTIONS.index(option)


def init_state():
    """Initialize Streamlit session state."""
    if "songs" not in st.session_state:
        # Source of truth is data/library.json (see storage.py docstring for
        # the seed-vs-runtime file design choice). The hardcoded list here is
        # only a last-resort fallback if that file is missing or malformed.
        st.session_state.songs = storage.load_json(LIBRARY_PATH, default=default_songs())
    if "profile" not in st.session_state:
        st.session_state.profile = dict(DEFAULT_PROFILE)
    if "history" not in st.session_state:
        st.session_state.history = []


def default_songs():
    """Return a default list of songs."""
    return [
        {
            "title": "Thunderstruck",
            "artist": "AC/DC",
            "genre": "rock",
            "energy": 9,
            "tags": ["classic", "guitar"],
        },
        {
            "title": "Lo-fi Rain",
            "artist": "DJ Calm",
            "genre": "lofi",
            "energy": 2,
            "tags": ["study"],
        },
        {
            "title": "Night Drive",
            "artist": "Neon Echo",
            "genre": "electronic",
            "energy": 6,
            "tags": ["synth"],
        },
        {
            "title": "Soft Piano",
            "artist": "Sleep Sound",
            "genre": "ambient",
            "energy": 1,
            "tags": ["sleep"],
        },
        {
            "title": "Bohemian Rhapsody",
            "artist": "Queen",
            "genre": "rock",
            "energy": 8,
            "tags": ["classic", "opera"],
        },
        {
            "title": "Blinding Lights",
            "artist": "The Weeknd",
            "genre": "pop",
            "energy": 8,
            "tags": ["synth", "dance"],
        },
        {
            "title": "Take Five",
            "artist": "Dave Brubeck",
            "genre": "jazz",
            "energy": 4,
            "tags": ["classic", "instrumental"],
        },
        {
            "title": "Strobe",
            "artist": "Deadmau5",
            "genre": "electronic",
            "energy": 7,
            "tags": ["progressive", "long"],
        },
        {
            "title": "Weightless",
            "artist": "Marconi Union",
            "genre": "ambient",
            "energy": 1,
            "tags": ["relax", "sleep"],
        },
        {
            "title": "Smells Like Teen Spirit",
            "artist": "Nirvana",
            "genre": "rock",
            "energy": 9,
            "tags": ["grunge", "90s"],
        },
        {
            "title": "Levitating",
            "artist": "Dua Lipa",
            "genre": "pop",
            "energy": 8,
            "tags": ["dance", "party"],
        },
        {
            "title": "So What",
            "artist": "Miles Davis",
            "genre": "jazz",
            "energy": 3,
            "tags": ["trumpet", "cool"],
        },
        {
            "title": "Midnight City",
            "artist": "M83",
            "genre": "electronic",
            "energy": 7,
            "tags": ["indie", "dream"],
        },
        {
            "title": "Gymnopedie No.1",
            "artist": "Erik Satie",
            "genre": "ambient",
            "energy": 1,
            "tags": ["piano", "calm"],
        },
        {
            "title": "Sweet Child O' Mine",
            "artist": "Guns N' Roses",
            "genre": "rock",
            "energy": 8,
            "tags": ["guitar", "80s"],
        },
        {
            "title": "Bad Guy",
            "artist": "Billie Eilish",
            "genre": "pop",
            "energy": 6,
            "tags": ["bass", "dark"],
        },
        {
            "title": "Fly Me to the Moon",
            "artist": "Frank Sinatra",
            "genre": "jazz",
            "energy": 5,
            "tags": ["vocal", "swing"],
        },
        {
            "title": "Sandstorm",
            "artist": "Darude",
            "genre": "electronic",
            "energy": 10,
            "tags": ["trance", "meme"],
        },
        {
            "title": "Clair de Lune",
            "artist": "Claude Debussy",
            "genre": "ambient",
            "energy": 2,
            "tags": ["piano", "classical"],
        },
        {
            "title": "Hotel California",
            "artist": "Eagles",
            "genre": "rock",
            "energy": 6,
            "tags": ["classic", "guitar"],
        },
        {
            "title": "Uptown Funk",
            "artist": "Mark Ronson ft. Bruno Mars",
            "genre": "pop",
            "energy": 9,
            "tags": ["funk", "dance"],
        },
        {
            "title": "Feeling Good",
            "artist": "Nina Simone",
            "genre": "jazz",
            "energy": 6,
            "tags": ["soul", "vocal"],
        },
    ]


def profile_sidebar():
    """Render and update the user profile."""
    st.sidebar.header("Mood profile")

    profile = st.session_state.profile

    profile["name"] = st.sidebar.text_input(
        "Profile name",
        value=str(profile.get("name", "")),
    )

    col1, col2 = st.sidebar.columns(2)
    with col1:
        profile["hype_min_energy"] = st.sidebar.slider(
            "Hype min energy",
            min_value=1,
            max_value=10,
            value=int(profile.get("hype_min_energy", 7)),
        )
    with col2:
        profile["chill_max_energy"] = st.sidebar.slider(
            "Chill max energy",
            min_value=1,
            max_value=10,
            value=int(profile.get("chill_max_energy", 3)),
        )

    profile["favorite_genre"] = st.sidebar.selectbox(
        "Favorite genre",
        options=["rock", "lofi", "pop", "jazz", "electronic", "ambient", "other"],
        index=0,
    )

    profile["include_mixed"] = st.sidebar.checkbox(
        "Include Mixed playlist in views",
        value=bool(profile.get("include_mixed", True)),
    )

    st.sidebar.write("Current profile:", profile["name"])


def add_song_sidebar():
    """Render the Add Song controls in the sidebar."""
    st.sidebar.header("Add a song")

    title = st.sidebar.text_input("Title")
    artist = st.sidebar.text_input("Artist")
    genre = st.sidebar.selectbox(
        "Genre",
        options=["rock", "lofi", "pop", "jazz", "electronic", "ambient", "other"],
    )
    energy = st.sidebar.slider("Energy", min_value=1, max_value=10, value=5)
    tags_text = st.sidebar.text_input("Tags (comma separated)")

    audio_choice = st.sidebar.radio(
        "Audio source",
        options=["Local sample (round-robin)", "Archive URL"],
    )
    archive_url = ""
    if audio_choice == "Archive URL":
        archive_url = st.sidebar.text_input("Archive URL (direct link to .wav/.mp3/.ogg)")

    if st.sidebar.button("Add to playlist"):
        raw_tags = [t.strip() for t in tags_text.split(",")]
        tags = [t for t in raw_tags if t]

        song: Song = {
            "title": title,
            "artist": artist,
            "genre": genre,
            "energy": energy,
            "tags": tags,
        }
        if title and artist:
            # normalize_song() only recognizes title/artist/genre/energy/tags
            # and rebuilds a fresh dict, so the audio field has to be attached
            # after normalization rather than on the raw `song` above.
            normalized = normalize_song(song)
            all_songs = st.session_state.songs[:]
            if audio_choice == "Archive URL":
                normalized["audio"] = {"source_type": "archive_url", "url": archive_url}
            else:
                sample_path = LOCAL_SAMPLE_FILES[len(all_songs) % len(LOCAL_SAMPLE_FILES)]
                normalized["audio"] = {"source_type": "local", "path": sample_path}
            all_songs.append(normalized)
            st.session_state.songs = all_songs
            storage.save_json(LIBRARY_PATH, all_songs)


def import_cc0_sidebar():
    """Render a one-click importer for the curated CC0 track list.

    Addresses "add songs from the internet without pasting one URL at a
    time": imports a small fixed list of real Wikimedia Commons
    public-domain classical recordings (not synthetic tones) in one click.
    Idempotent -- already-imported tracks (matched by ratings.song_key,
    the same title+artist composite key used everywhere else) are skipped,
    so clicking twice never duplicates.
    """
    st.sidebar.header("Import CC0 tracks")
    st.sidebar.caption(
        "Real public-domain classical recordings from Wikimedia Commons "
        "(not the synthetic sample tones). Instrumental only -- Transcribe "
        "will legitimately return no lyrics for these."
    )

    if st.sidebar.button("Import curated public-domain library"):
        existing_keys = {ratings.song_key(s) for s in st.session_state.songs}

        # Build the full new list in a local variable first, only assigning
        # to session_state once it's complete -- a partially-built import
        # can never leave session_state in a half-updated state.
        all_songs = st.session_state.songs[:]
        added = 0
        skipped = 0
        for candidate in cc0_library.normalized_cc0_tracks():
            if ratings.song_key(candidate) in existing_keys:
                skipped += 1
                continue
            all_songs.append(candidate)
            existing_keys.add(ratings.song_key(candidate))
            added += 1

        if added:
            st.session_state.songs = all_songs
            storage.save_json(LIBRARY_PATH, all_songs)
        st.sidebar.success(f"Imported {added} new track(s), skipped {skipped} already in library.")


def playlist_tabs(playlists):
    """Render playlists in tabs."""
    include_mixed = st.session_state.profile.get("include_mixed", True)

    tab_labels = ["Hype", "Chill"]
    if include_mixed:
        tab_labels.append("Mixed")

    tabs = st.tabs(tab_labels)

    for label, tab in zip(tab_labels, tabs):
        with tab:
            render_playlist(label, playlists.get(label, []))


def render_playlist(label, songs):
    st.subheader(f"{label} playlist")
    if not songs:
        st.write("No songs in this playlist.")
        return

    query = st.text_input(f"Search {label} playlist by artist", key=f"search_{label}")
    filtered = search_songs(songs, query, field="artist")

    col1, col2 = st.columns(2)
    with col1:
        sort_choice = st.selectbox(
            "Sort by",
            options=["Default", "Rating: high to low"],
            key=f"sort_{label}",
        )
    with col2:
        filter_choice = st.selectbox(
            "Filter",
            options=["All", "Rated only", "Unrated only"],
            key=f"filter_{label}",
        )

    if filter_choice == "Rated only":
        filtered = [s for s in filtered if ratings.get_rating(s) is not None]
    elif filter_choice == "Unrated only":
        filtered = [s for s in filtered if ratings.get_rating(s) is None]

    if sort_choice == "Rating: high to low":
        # Unrated songs (None) always sort after every rated song, regardless
        # of direction -- "unrated" is a distinct absence, not a 0.
        filtered = sorted(
            filtered,
            key=lambda s: (
                ratings.get_rating(s) is None,
                -(ratings.get_rating(s) or 0),
            ),
        )

    if not filtered:
        st.write("No matching songs.")
        return

    for song in filtered:
        mood = song.get("mood", "?")
        tags = ", ".join(song.get("tags", []))
        st.write(
            f"- **{song['title']}** by {song['artist']} "
            f"(genre {song['genre']}, energy {song['energy']}, mood {mood}) "
            f"[{tags}]"
        )

        result = audio_source.resolve(song)
        if result.playable:
            st.audio(result.reference)
        else:
            st.caption(f"Playback unavailable: {result.reason}")

        transcribe_song_widget(label, song, result.reference)

        current_rating = ratings.get_rating(song)
        widget_key = f"rating_{label}_{ratings.song_key(song)}"
        chosen = st.select_slider(
            "Your rating",
            options=STAR_OPTIONS,
            value=_stars_to_option(current_rating),
            key=widget_key,
        )
        chosen_stars = _option_to_stars(chosen)
        if chosen_stars != current_rating:
            if chosen_stars is None:
                ratings.clear_rating(song)
            else:
                ratings.rate_song(song, chosen_stars)


def transcribe_song_widget(label, song, audio_reference):
    """Render a standalone 'Transcribe' button for one song.

    Calls transcription.transcribe(), which is isolated by design: whether
    faster-whisper is installed, fails to load, or errors during
    transcription, this always returns a typed TranscriptionResult rather
    than raising -- so a click here can never break the rest of the page.
    Result is cached in session_state so it survives Streamlit reruns
    triggered by other widgets (e.g. the rating slider below it).
    """
    widget_key = f"transcribe_{label}_{ratings.song_key(song)}"
    result_key = f"{widget_key}_result"

    if st.button("Transcribe", key=widget_key):
        st.session_state[result_key] = transcription.transcribe(song, audio_reference)

    stored_result = st.session_state.get(result_key)
    if stored_result is not None:
        if stored_result.available:
            st.info(f"Lyrics/transcript: {stored_result.text}")
        else:
            st.caption(f"Transcription unavailable: {stored_result.reason}")


def lucky_section(playlists):
    """Render the lucky pick controls and result."""
    st.header("Lucky pick")

    mode = st.selectbox(
        "Pick from",
        options=["any", "hype", "chill"],
        index=0,
    )

    if st.button("Feeling lucky"):
        pick = lucky_pick(playlists, mode=mode)
        if pick is None:
            st.warning("No songs available for this mode.")
            return

        st.success(
            f"Lucky song: {pick['title']} by {pick['artist']} "
            f"(mood {pick.get('mood', '?')})"
        )

        history = st.session_state.history
        history.append(pick)
        st.session_state.history = history


def smart_recommend_section():
    """Render the Smart Recommend controls and result.

    Distinct from Lucky Pick: this triggers agent.recommend()'s rule-based
    plan/act/check/critique loop (never an LLM -- see agent.py's module
    docstring and docs/adr/0001-no-llm-local-only-agent.md) to build a
    reasoned Queue of several songs, rather than one random pick. The
    optional vibe text here narrows the candidate pool via retrieval.py
    before planning, same as the standalone VibeQuery section above but
    feeding straight into the agent instead of just displaying candidates.
    """
    st.header("Smart Recommend")
    st.caption(
        "Runs the RecommendationAgent's plan/act/check/critique loop to "
        "build a reasoned Queue -- a deterministic rule-based agent, not an "
        "LLM. Contrast this with Lucky Pick's single random choice above."
    )

    vibe_text = st.text_input(
        "Optional vibe to narrow candidates (leave blank to consider the full library)",
        key="smart_recommend_vibe_text",
    )

    if st.button("Smart Recommend"):
        songs = st.session_state.songs
        profile = st.session_state.profile
        history = st.session_state.history

        queue, trace = agent.recommend(
            songs,
            profile,
            history,
            ratings.all_ratings(),
            vibe_query=vibe_text or None,
        )

        if not queue:
            st.warning("The agent could not assemble a Queue from the current library.")
            return

        if trace.exhausted_retries:
            st.warning(
                f"Retries exhausted after {len(trace.iterations)} iterations without "
                f"clearing the Score threshold ({trace.threshold:.2f}). Showing the "
                f"best Queue found (Score {trace.final_score:.3f})."
            )
        else:
            st.success(
                f"Queue ready -- Score {trace.final_score:.3f} "
                f"(threshold {trace.threshold:.2f}) in {len(trace.iterations)} iteration(s)."
            )

        last_iteration = trace.iterations[-1]
        breakdown = ", ".join(f"{k} {v:.2f}" for k, v in last_iteration.score_breakdown.items())
        st.write(
            f"Strategy: **{last_iteration.strategy}** "
            f"(energy variance / artist-repeat / rating-alignment: {breakdown})"
        )

        for song in queue:
            tags = ", ".join(song.get("tags", []))
            st.write(
                f"- **{song['title']}** by {song['artist']} "
                f"(genre {song.get('genre', '?')}, energy {song.get('energy', '?')}, "
                f"mood {song.get('mood', '?')}) [{tags}]"
            )

        history = st.session_state.history
        history.extend(queue)
        st.session_state.history = history


def vibe_query_section():
    """Render the VibeQuery free-text retrieval controls and results.

    This is retrieval only: a TF-IDF ranking over Song metadata (title,
    artist, genre, tags). It bypasses Playlist mood filtering entirely --
    candidates can span Hype, Chill, and Mixed -- and it does not pick or
    recommend a song for the user, it just shows the ranked candidate list.
    """
    st.header("VibeQuery")
    st.caption(
        "Describe a mood or vibe in free text (e.g. \"rainy night drive\") "
        "and see the ranked candidates. This does not filter by playlist "
        "or recommend a single pick -- it just ranks the whole song pool."
    )

    vibe_text = st.text_input("Describe the vibe", key="vibe_query_text")

    if st.button("Find the vibe"):
        songs = st.session_state.songs
        index = retrieval.build_index(songs)
        results = retrieval.query(index, vibe_text, top_k=10)

        if not results:
            st.warning("No songs available to search.")
            return

        st.write(f"Top {len(results)} candidates for: \"{vibe_text}\"")
        profile = st.session_state.profile
        for song in results:
            tags = ", ".join(song.get("tags", []))
            genre = song.get("genre", "?")
            # Mood is computed here purely for display context -- retrieval
            # itself never used mood/Playlist bucket to filter or rank
            # `results`, so candidates above may already span Hype/Chill/Mixed.
            mood = classify_song(normalize_song(song), profile)
            st.write(
                f"- **{song.get('title', '?')}** by {song.get('artist', '?')} "
                f"(genre {genre}, mood {mood}) [{tags}]"
            )


def stats_section(playlists):
    """Render statistics based on the playlists."""
    st.header("Playlist stats")

    stats = compute_playlist_stats(playlists)

    col1, col2, col3 = st.columns(3)
    col1.metric("Total songs", stats["total_songs"])
    col2.metric("Hype songs", stats["hype_count"])
    col3.metric("Chill songs", stats["chill_count"])

    col4, col5, col6 = st.columns(3)
    col4.metric("Mixed songs", stats["mixed_count"])
    col5.metric("Hype ratio", f"{stats['hype_ratio']:.2f}")
    col6.metric("Average energy", f"{stats['avg_energy']:.2f}")

    top_artist = stats["top_artist"]
    if top_artist:
        st.write(
            f"Most common artist: {top_artist} "
            f"({stats['top_artist_count']} songs)"
        )
    else:
        st.write("No top artist yet.")


def history_section():
    """Render the pick history overview."""
    st.header("History")

    history = st.session_state.history
    if not history:
        st.write("No history yet.")
        return

    summary = history_summary(history)
    st.write("Recent picks by mood:", summary)

    show_details = st.checkbox("Show full history")
    if show_details:
        for song in history:
            st.write(
                f"{song.get('mood', '?')}: {song['title']} by {song['artist']}"
            )


def clear_controls():
    """Render a small section for clearing data."""
    st.sidebar.header("Manage data")
    if st.sidebar.button("Reset songs to default"):
        st.session_state.songs = default_songs()
    if st.sidebar.button("Clear history"):
        st.session_state.history = []


def main():
    st.set_page_config(page_title="Playlist Chaos", layout="wide")
    st.title("Playlist Chaos")

    st.write(
        "An AI assistant tried to build a smart playlist engine. "
        "The code runs, but the behavior is a bit unpredictable."
    )

    init_state()
    profile_sidebar()
    add_song_sidebar()
    import_cc0_sidebar()
    clear_controls()

    profile = st.session_state.profile
    songs = st.session_state.songs

    base_playlists = build_playlists(songs, profile)
    merged_playlists = merge_playlists(base_playlists, {})

    playlist_tabs(merged_playlists)
    st.divider()
    lucky_section(merged_playlists)
    st.divider()
    smart_recommend_section()
    st.divider()
    vibe_query_section()
    st.divider()
    stats_section(merged_playlists)
    st.divider()
    history_section()


if __name__ == "__main__":
    main()

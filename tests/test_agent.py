import pytest

import agent
import ratings


def make_song(title, artist, genre, energy, tags):
    return {"title": title, "artist": artist, "genre": genre, "energy": energy, "tags": tags}


def make_pool():
    """A small, fixed pool spanning artists/genres/energies (12 songs).

    Deliberately not the live 22-song data/library.json -- per this
    project's Testing Decisions, agent assertions must run against a
    fixture we control.

    Includes:
    - Two AC/DC songs (artist repeat, for diversify_artist testing).
    - Three "jazz"-tagged songs at different energies (4, 3, 7) so a
      vibe_query="jazz" narrows to candidates spanning different moods
      under DEFAULT-like profile (hype_min_energy=7, chill_max_energy=3):
      Take Five (energy 4) -> Mixed, So What (energy 3) -> Chill,
      Feeling Good (energy 7) -> Hype.
    """
    return [
        make_song("Thunderstruck", "AC/DC", "rock", 9, ["classic", "guitar"]),
        make_song("Back In Black", "AC/DC", "rock", 8, ["classic", "guitar"]),
        make_song("Lo-fi Rain", "DJ Calm", "lofi", 2, ["study"]),
        make_song("Night Drive", "Neon Echo", "electronic", 6, ["synth"]),
        make_song("Soft Piano", "Sleep Sound", "ambient", 1, ["sleep"]),
        make_song("Take Five", "Dave Brubeck", "jazz", 4, ["jazz", "instrumental"]),
        make_song("So What", "Miles Davis", "jazz", 3, ["jazz", "cool"]),
        make_song("Feeling Good", "Nina Simone", "jazz", 7, ["jazz", "soul"]),
        make_song("Blinding Lights", "The Weeknd", "pop", 8, ["synth", "dance"]),
        make_song("Weightless", "Marconi Union", "ambient", 1, ["relax", "sleep"]),
        make_song("Strobe", "Deadmau5", "electronic", 7, ["progressive"]),
        make_song("Levitating", "Dua Lipa", "pop", 8, ["dance", "party"]),
    ]


def make_profile():
    return {
        "name": "Test Profile",
        "hype_min_energy": 7,
        "chill_max_energy": 3,
        "favorite_genre": "rock",
        "include_mixed": True,
    }


@pytest.fixture(autouse=True)
def isolate_trace_path(tmp_path, monkeypatch):
    """Point agent.py's ReasoningTrace writer at a throwaway file so tests
    never append to the real ai_interactions.md."""
    path = tmp_path / "ai_interactions.md"
    monkeypatch.setattr(agent, "TRACE_PATH", str(path))
    return path


# --- Plan logic: at least 2 distinct scenarios producing different
# strategies, proving _plan is not a constant. -----------------------------


def test_plan_picks_explore_unrated_on_cold_start():
    pool = make_pool()
    strategy = agent._plan(make_profile(), history=[], ratings={})
    assert strategy == "explore_unrated"


def test_plan_picks_favor_high_rated_when_enough_real_ratings_exist():
    pool = make_pool()
    real_ratings = {
        ratings.song_key(pool[0]): 5,
        ratings.song_key(pool[1]): 4,
        ratings.song_key(pool[2]): 2,
    }
    strategy = agent._plan(make_profile(), history=[], ratings=real_ratings)
    assert strategy == "favor_high_rated"


def test_plan_picks_diversify_artist_when_history_repeats_an_artist():
    pool = make_pool()
    history = [pool[0], pool[1]]  # both AC/DC
    strategy = agent._plan(make_profile(), history=history, ratings={})
    assert strategy == "diversify_artist"


def test_plan_picks_diversify_artist_when_history_mood_is_concentrated():
    pool = make_pool()
    # All high-energy rock/pop -> all classify as Hype under this profile,
    # so the recent-history window is 100% one mood bucket.
    history = [
        make_song("Song A", "Artist A", "rock", 9, []),
        make_song("Song B", "Artist B", "pop", 8, []),
        make_song("Song C", "Artist C", "rock", 10, []),
    ]
    strategy = agent._plan(make_profile(), history=history, ratings={})
    assert strategy == "diversify_artist"


def test_plan_picks_use_vibe_candidates_when_vibe_query_given():
    strategy = agent._plan(make_profile(), history=[], ratings={}, vibe_query="rainy jazz")
    assert strategy == "use_vibe_candidates"


def test_plan_is_not_a_constant_across_scenarios():
    # Proves at least two distinct scenarios yield different strategy labels.
    cold_start = agent._plan(make_profile(), history=[], ratings={})
    with_ratings = agent._plan(
        make_profile(),
        history=[],
        ratings={"a::b": 5, "c::d": 4, "e::f": 3},
    )
    assert cold_start != with_ratings


# --- Score computation: artist repetition should score lower, all else
# equal. -------------------------------------------------------------------


def test_check_score_is_lower_with_repeated_artists_all_else_equal():
    model = agent.rating_predictor.train(make_pool(), ratings={})

    diverse_queue = [
        make_song("Take Five", "Dave Brubeck", "jazz", 4, []),
        make_song("Night Drive", "Neon Echo", "electronic", 6, []),
        make_song("Soft Piano", "Sleep Sound", "ambient", 1, []),
    ]
    repeated_queue = [
        make_song("Take Five", "Dave Brubeck", "jazz", 4, []),
        make_song("Blue Rondo", "Dave Brubeck", "jazz", 4, []),
        make_song("Soft Piano", "Sleep Sound", "ambient", 1, []),
    ]

    diverse_score, diverse_breakdown = agent._check(diverse_queue, model, ratings={})
    repeated_score, repeated_breakdown = agent._check(repeated_queue, model, ratings={})

    assert repeated_breakdown["artist"] < diverse_breakdown["artist"]
    assert repeated_score < diverse_score


def test_check_empty_queue_returns_zero_score_without_crashing():
    model = agent.rating_predictor.train(make_pool(), ratings={})
    score, breakdown = agent._check([], model, ratings={})
    assert score == 0.0
    assert breakdown == {"variance": 0.0, "artist": 0.0, "rating": 0.0}


# --- recommend(): normal case returns a non-empty Queue with Score at or
# above threshold. -----------------------------------------------------------


def test_recommend_returns_queue_and_trace_with_score_at_or_above_threshold():
    pool = make_pool()
    queue, trace = agent.recommend(pool, make_profile(), history=[], ratings={})

    assert isinstance(queue, list)
    assert len(queue) > 0
    assert trace.final_score >= agent.SCORE_THRESHOLD
    assert trace.exhausted_retries is False
    assert len(trace.iterations) >= 1


def test_recommend_appends_queue_songs_shape_compatible_with_history():
    pool = make_pool()
    queue, _trace = agent.recommend(pool, make_profile(), history=[], ratings={})
    for song in queue:
        assert "title" in song and "artist" in song and "mood" in song


# --- Bounded retry: Score can never clear an impossibly high threshold ->
# recommend() still returns within MAX_ITERATIONS. --------------------------


def test_recommend_bounded_retry_terminates_when_threshold_unreachable(monkeypatch):
    monkeypatch.setattr(agent, "SCORE_THRESHOLD", 999.0)

    pool = make_pool()
    queue, trace = agent.recommend(pool, make_profile(), history=[], ratings={})

    # Must still return cleanly, with a real (possibly low-scoring) Queue.
    assert isinstance(queue, list)
    assert len(queue) > 0

    # Concrete proof it's bounded: at most MAX_ITERATIONS iteration records,
    # never more.
    assert len(trace.iterations) <= agent.MAX_ITERATIONS
    assert len(trace.iterations) == agent.MAX_ITERATIONS

    # And the trace clearly reports that retries were exhausted.
    assert trace.exhausted_retries is True


def test_recommend_bounded_retry_respects_custom_max_iterations(monkeypatch):
    monkeypatch.setattr(agent, "SCORE_THRESHOLD", 999.0)
    monkeypatch.setattr(agent, "MAX_ITERATIONS", 2)

    pool = make_pool()
    _queue, trace = agent.recommend(pool, make_profile(), history=[], ratings={})

    assert len(trace.iterations) == 2
    assert trace.exhausted_retries is True


# --- VibeQuery narrowing: candidate set narrows without pre-filtering by
# mood. ----------------------------------------------------------------------


def test_vibe_query_narrows_pool_and_queue_stays_within_narrowed_set():
    pool = make_pool()
    profile = make_profile()

    queue, trace = agent.recommend(pool, profile, history=[], ratings={}, vibe_query="jazz")

    assert trace.narrowed_pool_size is not None
    assert trace.narrowed_pool_size < len(pool)

    # Reconstruct the exact narrowed candidate set the agent used, and
    # confirm the returned Queue is fully contained within it (by title,
    # since normalize_song may lowercase/strip fields).
    index = agent.retrieval.build_index(pool)
    narrowed = agent.retrieval.query(index, "jazz", top_k=agent.VIBE_CANDIDATE_TOP_K)
    narrowed_titles = {s["title"] for s in narrowed}
    assert all(song["title"] in narrowed_titles for song in queue)

    # Confirm the narrowed candidate set itself spans multiple moods -- i.e.
    # nothing pre-filtered it down to a single mood bucket before the agent
    # got to see it. The three jazz songs sit at energies 4/3/7, which
    # classify to Mixed/Chill/Hype respectively under this profile.
    narrowed_moods = {
        agent.classify_song(agent.normalize_song(s), profile) for s in narrowed
    }
    assert len(narrowed_moods) > 1


def test_vibe_query_none_does_not_narrow_pool():
    pool = make_pool()
    _queue, trace = agent.recommend(pool, make_profile(), history=[], ratings={}, vibe_query=None)
    assert trace.narrowed_pool_size is None


# --- Lucky Pick regression guard: playlist_logic.lucky_pick and
# app.lucky_section must stay unchanged by this ticket. ----------------------


def test_lucky_pick_regression_any_mode_draws_from_hype_and_chill():
    import playlist_logic

    playlists = {
        "Hype": [make_song("H1", "A1", "rock", 9, [])],
        "Chill": [make_song("C1", "A2", "ambient", 1, [])],
        "Mixed": [make_song("M1", "A3", "jazz", 5, [])],
    }

    seen_titles = set()
    for _ in range(50):
        pick = playlist_logic.lucky_pick(playlists, mode="any")
        assert pick is not None
        seen_titles.add(pick["title"])

    # "any" draws from Hype + Chill only, never Mixed -- unchanged baseline
    # behavior that Smart Recommend must not have touched.
    assert seen_titles <= {"H1", "C1"}


def test_lucky_pick_regression_hype_mode_only_returns_hype_songs():
    import playlist_logic

    playlists = {
        "Hype": [make_song("H1", "A1", "rock", 9, [])],
        "Chill": [make_song("C1", "A2", "ambient", 1, [])],
        "Mixed": [],
    }

    for _ in range(20):
        pick = playlist_logic.lucky_pick(playlists, mode="hype")
        assert pick["title"] == "H1"


def test_lucky_pick_regression_returns_none_when_no_songs_available():
    import playlist_logic

    assert playlist_logic.lucky_pick({}, mode="any") is None
    assert playlist_logic.lucky_pick({"Hype": [], "Chill": []}, mode="chill") is None

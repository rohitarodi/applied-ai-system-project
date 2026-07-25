"""eval_harness.py: standalone scenario test harness for RecommendationAgent
(Ticket 8, the "Test Harness" stretch feature).

Runs `agent.recommend` against a fixed set of NAMED scenarios (profile +
history + ratings + optional vibe_query) and prints a plain-text PASS/FAIL +
Score summary table. This is a diagnostic script, not a pytest suite -- it
has no dependency on Streamlit or any running app, and needs no CLI args to
produce useful output against the bundled data/library.json.

Pass/fail definition (reuses agent.py's own real values, never a duplicate
hardcoded threshold):

    PASS  Score  >= agent.SCORE_THRESHOLD  (equivalently, trace.exhausted_retries
          is False -- agent.py guarantees these two are equivalent, see
          ReasoningTrace's docstring).
    FAIL  MAX_ITERATIONS retries were exhausted without ever clearing
          SCORE_THRESHOLD (trace.exhausted_retries is True).

Each scenario also declares an `expected` outcome ("pass" or "fail") right
alongside its definition in `build_scenarios()`. The harness's own exit code
is a self-check: it is 0 only if every scenario's *actual* result matched its
*expected* result -- proving this script actually distinguishes pass from
fail rather than always reporting success. One scenario
("impossible_artist_repeat") is deliberately built so it can never clear
SCORE_THRESHOLD (see that scenario's note for the arithmetic), so a
regression that made every Queue trivially pass would show up here as a
self-check failure, not a false "all green".

Usage:
    python eval_harness.py
"""

import sys
from dataclasses import dataclass
from typing import Dict, List, Optional

import agent
import ratings as ratings_module
import storage
from playlist_logic import DEFAULT_PROFILE, Song

LIBRARY_PATH = "data/library.json"


@dataclass
class Scenario:
    """One named eval scenario: exactly the four real recommend() inputs
    (plus the optional vibe_query), a declared `expected` outcome, and a
    human-readable `note` explaining why that outcome is expected.
    """

    name: str
    pool: List[Song]
    profile: Dict[str, object]
    history: List[Song]
    ratings: Dict[str, int]
    vibe_query: Optional[str]
    expected: str  # "pass" or "fail"
    note: str


@dataclass
class ScenarioResult:
    """The outcome of running one Scenario through agent.recommend, plus the
    harness's own self-check (`matches_expected`) comparing what actually
    happened to what the scenario was designed to prove.
    """

    name: str
    expected: str
    actual: str
    final_score: float
    iterations: int
    matches_expected: bool
    note: str


def _song(title: str, artist: str, genre: str, energy: int, tags: List[str]) -> Song:
    return {"title": title, "artist": artist, "genre": genre, "energy": energy, "tags": tags}


def _load_library() -> List[Song]:
    """Load the real bundled library (data/library.json), same shape the app
    itself uses, via storage.load_json (never raises -- an empty list is a
    safe fallback if the file is somehow missing)."""
    return storage.load_json(LIBRARY_PATH, default=[])


def build_scenarios() -> List[Scenario]:
    """Return the fixed, named scenario set this harness runs every time.

    Six scenarios: a cold start, an established-taste (favor_high_rated)
    case, a VibeQuery-driven case, a diversify_artist case (history repeats
    an artist), a scenario exercising a non-default Profile, and one
    scenario deliberately designed so it can never clear SCORE_THRESHOLD
    (the required "designed to fail" scenario per the ticket's acceptance
    criteria).
    """
    library = _load_library()

    cold_start = Scenario(
        name="cold_start",
        pool=library,
        profile=dict(DEFAULT_PROFILE),
        history=[],
        ratings={},
        vibe_query=None,
        expected="pass",
        note="empty history/ratings against the full library -- baseline explore_unrated path",
    )

    rock_artists = {"AC/DC", "Queen", "Guns N' Roses", "Eagles", "Nirvana"}
    rock_fan_songs = [s for s in library if s.get("artist") in rock_artists]
    established_ratings: Dict[str, int] = {}
    for s in rock_fan_songs[:3]:
        established_ratings[ratings_module.song_key(s)] = 5
    for s in rock_fan_songs[3:5]:
        established_ratings[ratings_module.song_key(s)] = 4
    established_taste = Scenario(
        name="established_taste",
        pool=library,
        profile=dict(DEFAULT_PROFILE),
        history=[],
        ratings=established_ratings,
        vibe_query=None,
        expected="pass",
        note=">=3 real high ratings on rock songs -- exercises favor_high_rated strategy",
    )

    vibe_driven = Scenario(
        name="vibe_query_jazz",
        pool=library,
        profile=dict(DEFAULT_PROFILE),
        history=[],
        ratings={},
        vibe_query="jazz",
        expected="pass",
        note="vibe_query narrows to jazz-genre/tagged songs spanning multiple energies -- exercises use_vibe_candidates",
    )

    repeat_artist_history = [
        _song("Thunderstruck", "AC/DC", "rock", 9, ["classic", "guitar"]),
        _song("Back In Black", "AC/DC", "rock", 8, ["classic", "guitar"]),
    ]
    diversify = Scenario(
        name="diversify_artist_history",
        pool=library,
        profile=dict(DEFAULT_PROFILE),
        history=repeat_artist_history,
        ratings={},
        vibe_query=None,
        expected="pass",
        note="recent history repeats one artist -- exercises diversify_artist strategy over a diverse library",
    )

    jazz_night_owl_profile = {
        "name": "Jazz Night Owl",
        "hype_min_energy": 8,
        "chill_max_energy": 2,
        "favorite_genre": "jazz",
        "include_mixed": True,
    }
    jazz_ratings = {
        ratings_module.song_key(s): 4 for s in library if s.get("genre") == "jazz"
    }
    custom_profile_scenario = Scenario(
        name="custom_profile_jazz_lover",
        pool=library,
        profile=jazz_night_owl_profile,
        history=[_song("Take Five", "Dave Brubeck", "jazz", 4, ["jazz"])],
        ratings=jazz_ratings,
        vibe_query=None,
        expected="pass",
        note="non-default Profile + real jazz ratings -- broadens coverage beyond DEFAULT_PROFILE",
    )

    # Designed to fail: a 2-song pool, both by the same artist, both rated 1
    # star. Score's three terms (see agent._check):
    #   - artist_score: 2 songs, 1 duplicate artist -> max(0, 1 - 1/2) = 0.5
    #   - rating_score: both real ratings are 1 star -> (1-1)/4 = 0.0 for both
    #   - variance_score: capped at 1.0 in the best case
    # Best possible Score = 0.3*1.0 (variance) + 0.3*0.5 (artist) + 0.4*0.0
    #                     = 0.45, which is < SCORE_THRESHOLD (0.55) no matter
    # what energy values are chosen -- the artist-repeat penalty and the low
    # real ratings together make this pool mathematically unable to clear
    # threshold, even across all MAX_ITERATIONS retries (every strategy still
    # only has these same 2 songs to choose from).
    impossible_pool = [
        _song("Same Artist Track One", "Lone Artist", "rock", 5, []),
        _song("Same Artist Track Two", "Lone Artist", "rock", 9, []),
    ]
    impossible_ratings = {ratings_module.song_key(s): 1 for s in impossible_pool}
    designed_to_fail = Scenario(
        name="impossible_artist_repeat",
        pool=impossible_pool,
        profile=dict(DEFAULT_PROFILE),
        history=[],
        ratings=impossible_ratings,
        vibe_query=None,
        expected="fail",
        note=(
            "2-song pool, same artist, both rated 1 star -- artist-repeat + low "
            "rating caps best-case Score at 0.45 < threshold 0.55, so retries "
            "must exhaust"
        ),
    )

    return [
        cold_start,
        established_taste,
        vibe_driven,
        diversify,
        custom_profile_scenario,
        designed_to_fail,
    ]


def run_scenario(scenario: Scenario) -> ScenarioResult:
    """Run one Scenario through the real agent.recommend() and classify the
    outcome. Uses agent.SCORE_THRESHOLD (the real constant, never a
    duplicated hardcoded value) and trace.exhausted_retries (ticket 6's
    field for exactly this purpose) as two independent, cross-checked
    signals of the same thing.
    """
    _queue, trace = agent.recommend(
        scenario.pool,
        scenario.profile,
        scenario.history,
        scenario.ratings,
        vibe_query=scenario.vibe_query,
    )

    cleared_threshold = trace.final_score >= agent.SCORE_THRESHOLD
    # These two signals must always agree -- if they don't, agent.py's
    # exhausted_retries bookkeeping and its own threshold comparison have
    # drifted apart, which is itself a bug worth surfacing loudly here.
    assert cleared_threshold == (not trace.exhausted_retries), (
        f"{scenario.name}: final_score>=threshold ({cleared_threshold}) "
        f"disagrees with exhausted_retries ({trace.exhausted_retries})"
    )

    actual = "pass" if cleared_threshold else "fail"

    if actual == "fail":
        detail = "exhausted retries"
    else:
        last_strategy = trace.iterations[-1].strategy if trace.iterations else "?"
        detail = f"strategy={last_strategy}"

    return ScenarioResult(
        name=scenario.name,
        expected=scenario.expected,
        actual=actual,
        final_score=trace.final_score,
        iterations=len(trace.iterations),
        matches_expected=(actual == scenario.expected),
        note=f"{scenario.note} | {detail}",
    )


def run_all(scenarios: Optional[List[Scenario]] = None) -> List[ScenarioResult]:
    """Run every scenario (the fixed set from build_scenarios() by default)
    and return their results in order."""
    if scenarios is None:
        scenarios = build_scenarios()
    return [run_scenario(s) for s in scenarios]


def print_summary_table(results: List[ScenarioResult]) -> None:
    """Print a plain-text summary table to stdout: scenario name, PASS/FAIL,
    final Score, iteration count, and a brief note. No external table
    library -- fixed-width f-string columns keep this dependency-free.
    """
    name_w = max(8, max((len(r.name) for r in results), default=0))
    header = (
        f"{'Scenario':<{name_w}}  {'Result':<6}  {'Score':>7}  {'Iters':>5}  Note"
    )
    print(header)
    print("-" * len(header))
    for r in results:
        result_label = "PASS" if r.actual == "pass" else "FAIL"
        print(
            f"{r.name:<{name_w}}  {result_label:<6}  {r.final_score:>7.3f}  "
            f"{r.iterations:>5}  {r.note}"
        )


def main() -> int:
    scenarios = build_scenarios()
    results = run_all(scenarios)

    print_summary_table(results)

    mismatches = [r for r in results if not r.matches_expected]
    if mismatches:
        print()
        print("HARNESS SELF-CHECK FAILED -- scenario(s) did not behave as designed:")
        for r in mismatches:
            print(
                f"  - {r.name}: expected {r.expected!r}, got {r.actual!r} "
                f"(Score {r.final_score:.3f})"
            )
        return 1

    print()
    print(f"Harness self-check OK: all {len(results)} scenarios behaved as designed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())

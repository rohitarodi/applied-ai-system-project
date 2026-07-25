"""RecommendationAgent: the rule-based plan -> act -> check -> critique loop
that produces a Queue (Ticket 6).

Per ADR 0001 (docs/adr/0001-no-llm-local-only-agent.md), this agent NEVER
calls an LLM. Every decision below -- the strategy chosen in `_plan`, the
candidate selection in `_act`, the Score computed in `_check` -- is plain
deterministic Python over the caller's Profile/History/Ratings and
RatingPredictor output. The ReasoningTrace text written to
`ai_interactions.md` is formatted output of those same values, not
natural-language generation.

Public seam (do not change this signature -- see SPEC.md):

    agent.recommend(pool, profile, history, ratings, vibe_query=None)
        -> (Queue, ReasoningTrace)

- `pool`: list[Song] -- the full library (e.g. st.session_state.songs).
- `profile`: the Profile dict (same shape as playlist_logic.DEFAULT_PROFILE).
- `history`: list[Song] -- previously-picked songs (Lucky Pick and/or past
  Smart Recommend runs).
- `ratings`: song_key -> stars dict, the exact shape ratings.all_ratings()
  returns.
- `vibe_query`: optional free-text string. When given, `pool` is narrowed via
  retrieval.py FIRST, before planning -- this is candidate-set narrowing, not
  a mood filter (CONTEXT.md). Playlist mood bucket (Hype/Chill/Mixed) is
  never used as a pre-filter anywhere in this module; mood is only ever a
  scoring input, matching the RecommendationAgent's CONTEXT.md definition.

Queue: an ordered list[Song] (plain dicts, same normalize_song() shape the
rest of the app uses, with a "mood" key attached the same way
playlist_logic.build_playlists does).

Score: a float in [0.0, 1.0] combining energy variance, an artist-repeat
penalty, and rating alignment (see `_check`'s docstring for the exact
formula and weights).
"""

import statistics
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Dict, List, Optional

import ratings as ratings_module
import rating_predictor
import retrieval
from playlist_logic import Song, classify_song, normalize_artist, normalize_song

# --- Tunable constants (documented; exact values are not load-bearing) -----

# Target Queue size for one recommend() run. 6 sits comfortably inside the
# ticket's suggested 5-8 range -- big enough to show real variety, small
# enough to stay readable in the UI.
QUEUE_SIZE = 6

# How many of the most recent History entries `_plan` inspects when judging
# mood/artist diversity. Older history is treated as stale taste evidence.
RECENT_HISTORY_WINDOW = 6

# If one mood bucket makes up more than this share of the recent History
# window, `_plan` treats that as "not diverse" and picks "diversify_artist".
DIVERSITY_MOOD_THRESHOLD = 0.7

# Minimum number of real Ratings before `_plan` trusts them enough to pick
# "favor_high_rated" over the cold-start "explore_unrated" strategy.
MIN_RATINGS_FOR_TRUST = 3

# Artist caps `_act` enforces per strategy: 1 = "at most one song per
# artist", 2 = a looser "at most two" cap used as a backfill/moderate cap.
MAX_PER_ARTIST_STRICT = 1
MAX_PER_ARTIST_DEFAULT = 2

# How many candidates retrieval.query() returns when vibe_query is given.
# Kept a little larger than QUEUE_SIZE so `_act` still has room to apply its
# artist cap and strategy ranking on top of the VibeQuery ranking.
VIBE_CANDIDATE_TOP_K = 10

# Score formula weights (must sum to 1.0) -- see `_check`'s docstring.
W_VARIANCE = 0.3
W_ARTIST = 0.3
W_RATING = 0.4

# Energy variance (statistics.pvariance over the Queue's `energy` values)
# that counts as "fully good" spread for the variance_score term. Chosen as
# roughly the variance of a well-mixed Queue spanning low/mid/high energy on
# the 1-10 scale (e.g. energies 2, 5, 8 -> pvariance 6.0). Variance above
# this is capped at a variance_score of 1.0, not rewarded further.
TARGET_ENERGY_VARIANCE = 6.0

# Score at or above this clears the critique; below it, `recommend()` retries
# planning (bounded -- see MAX_ITERATIONS).
SCORE_THRESHOLD = 0.55

# Hard cap on plan/act/check/critique iterations per recommend() call. This
# is what makes the retry loop provably bounded: a Queue that can never
# clear SCORE_THRESHOLD still returns (the best-scoring Queue seen) after at
# most this many iterations, never looping forever.
MAX_ITERATIONS = 4

# Where ReasoningTrace entries are appended. A module-level constant (not a
# default argument value) so tests can redirect it via
# monkeypatch.setattr(agent, "TRACE_PATH", ...), same pattern as
# ratings.RATINGS_PATH.
TRACE_PATH = "ai_interactions.md"


@dataclass
class IterationRecord:
    """One attempted plan/act/check/critique iteration within one run."""

    iteration: int
    strategy: str
    queue_titles: List[str]
    score: float
    score_breakdown: Dict[str, float]
    retried: bool


@dataclass
class ReasoningTrace:
    """The full recorded trace for one recommend() call.

    `exhausted_retries` is True iff every iteration ran out (MAX_ITERATIONS
    attempts) without any Score clearing SCORE_THRESHOLD -- the caller
    (app.py) uses this to decide whether to warn the user instead of
    silently presenting a low-scoring Queue as if it were a normal result.
    """

    timestamp: str
    profile_name: str
    history_length: int
    vibe_query: Optional[str]
    narrowed_pool_size: Optional[int]
    threshold: float
    iterations: List[IterationRecord] = field(default_factory=list)
    final_score: float = 0.0
    exhausted_retries: bool = False


def _plan(profile: Dict[str, object], history: List[Song], ratings: Dict[str, int],
          vibe_query: Optional[str] = None) -> str:
    """Choose a strategy label from Profile + History + Ratings.

    Deterministic rule branches, evaluated in this order (first match wins):

    1. `vibe_query` is a non-empty string -> "use_vibe_candidates". The user
       gave explicit free-text intent; the agent leans into the
       VibeQuery-narrowed candidate set rather than second-guessing it.
    2. The most recent `min(RECENT_HISTORY_WINDOW, len(history))` History
       entries show low diversity -- either one mood bucket (recomputed
       fresh against the *current* `profile` via classify_song, never a
       stale stored "mood" field, since the profile may have changed since
       those picks) makes up more than DIVERSITY_MOOD_THRESHOLD of the
       window, or any single artist repeats within the window ->
       "diversify_artist": counter the streak.
    3. `len(ratings) >= MIN_RATINGS_FOR_TRUST` real ratings exist ->
       "favor_high_rated": enough real signal to weight selection toward it.
    4. Otherwise (History too short/uniform to judge, ratings sparse) ->
       "explore_unrated": prioritize gathering taste signal on songs with no
       real rating yet.

    This is genuinely load-bearing: `_act` branches on the returned string to
    change candidate selection (artist caps, ranking order), not just for
    display.
    """
    if vibe_query:
        return "use_vibe_candidates"

    window = history[-RECENT_HISTORY_WINDOW:] if history else []
    if len(window) >= 2:
        moods = [classify_song(normalize_song(s), profile) for s in window]
        dominant_share = max(moods.count(m) for m in set(moods)) / len(moods)

        artists = [normalize_artist(str(s.get("artist", ""))) for s in window]
        has_artist_repeat = len(artists) != len(set(artists))

        if dominant_share > DIVERSITY_MOOD_THRESHOLD or has_artist_repeat:
            return "diversify_artist"

    if len(ratings) >= MIN_RATINGS_FOR_TRUST:
        return "favor_high_rated"

    return "explore_unrated"


def _retry_strategy(breakdown: Dict[str, float]) -> str:
    """Pick the next strategy for a retry, based on which Score term was
    weakest in the previous iteration's critique.

    Documented mapping: whichever of variance/artist/rating scored lowest is
    treated as "what went wrong", and the next strategy is the one most
    likely to fix that specific term:

    - weakest "artist"   -> "diversify_artist" (directly targets repeats)
    - weakest "rating"   -> "favor_high_rated" (directly targets alignment)
    - weakest "variance" -> "explore_unrated" (pulls in different/novel
      songs, which tends to widen the energy spread versus re-ranking the
      same top-rated cluster)

    Ties are broken deterministically by dict iteration order (variance,
    then artist, then rating), so retries are reproducible.
    """
    weakest = min(breakdown, key=breakdown.get)
    return {
        "variance": "explore_unrated",
        "artist": "diversify_artist",
        "rating": "favor_high_rated",
    }[weakest]


def _score_song(song: Song, ratings: Dict[str, int], model) -> tuple:
    """Return (score, is_unrated) for one normalized song.

    Real rating (via ratings.song_key against the `ratings` dict) wins when
    present; otherwise falls back to rating_predictor.predict(), clamped to
    the 1-5 scale (the regressor can output slightly outside that range).
    """
    key = ratings_module.song_key(song)
    if key in ratings:
        return float(ratings[key]), False
    predicted = rating_predictor.predict(model, song)
    return max(1.0, min(5.0, predicted)), True


def _cap_by_artist(ranked_entries: List[dict], cap: int, target: int) -> List[dict]:
    """Select up to `target` entries from `ranked_entries` (already sorted
    best-first), allowing at most `cap` entries per artist on the first
    pass. If that cap can't fill `target` (pool too small/too concentrated),
    backfills from the leftover entries in their existing rank order so the
    Queue still reaches `target` when the candidate pool allows it.
    """
    counts: Dict[str, int] = {}
    selected: List[dict] = []
    leftover: List[dict] = []

    for entry in ranked_entries:
        if len(selected) >= target:
            break
        artist = entry["song"].get("artist", "")
        if counts.get(artist, 0) < cap:
            selected.append(entry)
            counts[artist] = counts.get(artist, 0) + 1
        else:
            leftover.append(entry)

    for entry in leftover:
        if len(selected) >= target:
            break
        selected.append(entry)

    return selected


def _act(pool: List[Song], strategy: str, model, ratings: Dict[str, int],
          profile: Dict[str, object]) -> List[Song]:
    """Assemble a candidate Queue (up to QUEUE_SIZE songs) from `pool`.

    Every candidate is normalized, mood-classified against `profile` (for
    display -- mood is a scoring input elsewhere, never a filter here), and
    scored via `_score_song`. `strategy` then decides ranking/diversity:

    - "diversify_artist": rank by score, cap MAX_PER_ARTIST_STRICT (1) per
      artist first, backfilling with MAX_PER_ARTIST_DEFAULT (2) only if the
      strict cap can't fill the Queue.
    - "explore_unrated": unrated candidates ranked ahead of rated ones (both
      internally sorted by score), so the Queue biases toward gathering new
      taste signal without excluding known favorites entirely. Moderate (2)
      artist cap.
    - "favor_high_rated" / "use_vibe_candidates" (and any other label, as a
      safe fallback): rank purely by score, moderate (2) artist cap. For
      "use_vibe_candidates" `pool` is already the VibeQuery-narrowed
      candidate set by the time it reaches this function.

    Deterministic: ties broken by (artist, title) -- no randomness, so the
    same inputs always produce the same Queue.
    """
    scored = []
    for raw in pool:
        song = normalize_song(raw)
        song["mood"] = classify_song(song, profile)
        score, is_unrated = _score_song(song, ratings, model)
        scored.append({"song": song, "score": score, "unrated": is_unrated})

    def sort_key(entry):
        return (-entry["score"], entry["song"].get("artist", ""), entry["song"].get("title", ""))

    if strategy == "diversify_artist":
        ranked = sorted(scored, key=sort_key)
        chosen = _cap_by_artist(ranked, MAX_PER_ARTIST_STRICT, QUEUE_SIZE)
        if len(chosen) < min(QUEUE_SIZE, len(ranked)):
            chosen = _cap_by_artist(ranked, MAX_PER_ARTIST_DEFAULT, QUEUE_SIZE)
    elif strategy == "explore_unrated":
        unrated = sorted((e for e in scored if e["unrated"]), key=sort_key)
        rated = sorted((e for e in scored if not e["unrated"]), key=sort_key)
        chosen = _cap_by_artist(unrated + rated, MAX_PER_ARTIST_DEFAULT, QUEUE_SIZE)
    else:
        ranked = sorted(scored, key=sort_key)
        chosen = _cap_by_artist(ranked, MAX_PER_ARTIST_DEFAULT, QUEUE_SIZE)

    return [entry["song"] for entry in chosen]


def _check(queue: List[Song], model, ratings: Dict[str, int]) -> tuple:
    """Compute this Queue's Score (float in [0.0, 1.0]) plus a term
    breakdown dict ({"variance": .., "artist": .., "rating": ..}).

    Three documented terms, combined with module-level weights that sum to
    1.0 (W_VARIANCE + W_ARTIST + W_RATING):

    - variance_score: statistics.pvariance() of the Queue's `energy` values,
      divided by TARGET_ENERGY_VARIANCE and capped at 1.0. Spread is
      rewarded (not penalized) -- an all-hype or all-chill Queue scores
      lower here than one with some energy range.
    - artist_score: 1.0 minus (duplicate artist count / Queue size). A
      Queue with no repeated artist scores 1.0; more repeats push this
      toward 0.0.
    - rating_score: mean of each song's normalized rating (real rating from
      `ratings` if present, else `model`'s prediction), rescaled from the
      1-5 star scale to 0.0-1.0.

    An empty Queue returns Score 0.0 with an all-zero breakdown rather than
    raising (a divide-by-zero guard).
    """
    if not queue:
        return 0.0, {"variance": 0.0, "artist": 0.0, "rating": 0.0}

    energies = [float(s.get("energy", 0)) for s in queue]
    variance = statistics.pvariance(energies) if len(energies) > 1 else 0.0
    variance_score = min(variance / TARGET_ENERGY_VARIANCE, 1.0)

    artists = [s.get("artist", "") for s in queue]
    duplicates = len(artists) - len(set(artists))
    artist_score = max(0.0, 1.0 - duplicates / len(artists))

    normalized = []
    for song in queue:
        raw_rating, _ = _score_song(song, ratings, model)
        normalized.append((raw_rating - 1.0) / 4.0)
    rating_score = sum(normalized) / len(normalized)

    score = (
        W_VARIANCE * variance_score
        + W_ARTIST * artist_score
        + W_RATING * rating_score
    )
    breakdown = {
        "variance": variance_score,
        "artist": artist_score,
        "rating": rating_score,
    }
    return score, breakdown


def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")


def _write_trace(trace: ReasoningTrace, path: Optional[str] = None) -> None:
    """Append one human-readable Markdown entry for this recommend() run to
    `path` (defaults to the module-level TRACE_PATH, read at call time so
    tests can monkeypatch it).

    Every value written here is a plain Python value already computed by
    `recommend()`/`_plan`/`_act`/`_check` above -- deterministic rule-trace
    text, never natural-language model output (see module docstring / ADR
    0001). Appends rather than truncates, so this file accumulates a running
    log across every run.
    """
    target = path if path is not None else TRACE_PATH

    lines = [f"## Run at {trace.timestamp}", ""]
    vibe_note = f"\"{trace.vibe_query}\"" if trace.vibe_query else "(none)"
    header = (
        f"- Profile: {trace.profile_name} | History length: {trace.history_length} "
        f"| VibeQuery: {vibe_note}"
    )
    if trace.narrowed_pool_size is not None:
        header += f" | Narrowed pool: {trace.narrowed_pool_size} candidates"
    lines.append(header)
    lines.append(f"- Score threshold: {trace.threshold:.2f}")

    for record in trace.iterations:
        lines.append(f"- Iteration {record.iteration}: plan -> strategy `{record.strategy}`")
        titles = ", ".join(record.queue_titles) if record.queue_titles else "(empty queue)"
        lines.append(f"  - act -> Queue: {titles}")
        breakdown_str = ", ".join(f"{k}={v:.2f}" for k, v in record.score_breakdown.items())
        lines.append(f"  - check -> Score {record.score:.3f} ({breakdown_str})")
        if record.retried:
            lines.append("  - critique -> below threshold, retrying with adjusted strategy")
        elif record.score >= trace.threshold:
            lines.append("  - critique -> threshold cleared, stopping")
        else:
            lines.append("  - critique -> retries exhausted, returning best Queue found")

    outcome = "EXHAUSTED RETRIES without clearing threshold" if trace.exhausted_retries else "threshold cleared"
    lines.append(f"- Final: Score {trace.final_score:.3f} ({outcome})")
    lines.append("")

    with open(target, "a", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")


def recommend(pool: List[Song], profile: Dict[str, object], history: List[Song],
              ratings: Dict[str, int], vibe_query: Optional[str] = None):
    """Run the RecommendationAgent's plan -> act -> check -> critique loop.

    See the module docstring for the full seam contract. Summary of the
    control flow:

    1. If `vibe_query` is given, narrow `pool` via retrieval.py FIRST (top
       VIBE_CANDIDATE_TOP_K by TF-IDF similarity) -- before any planning.
       This never touches mood/Playlist bucket.
    2. Train a RatingPredictor once for this call (`rating_predictor.train`
       over the *full*, unnarrowed `pool` + `ratings` -- the model should
       reflect the whole library's feature distribution regardless of
       whether this particular run is VibeQuery-narrowed).
    3. Plan an initial strategy (`_plan`).
    4. Loop up to MAX_ITERATIONS times: act (assemble a Queue), check
       (compute a Score), critique (decide whether to retry). On retry, the
       strategy for the next iteration is chosen by `_retry_strategy` based
       on which Score term was weakest.
    5. Return the best-scoring Queue seen across all attempted iterations
       (not necessarily the last one), plus a ReasoningTrace recording every
       iteration. `exhausted_retries` is True iff no iteration's Score ever
       cleared SCORE_THRESHOLD.
    6. Append the ReasoningTrace to ai_interactions.md as a side effect.
    """
    candidate_pool = list(pool)
    narrowed_pool_size = None
    if vibe_query:
        index = retrieval.build_index(pool)
        candidate_pool = retrieval.query(index, vibe_query, top_k=VIBE_CANDIDATE_TOP_K)
        narrowed_pool_size = len(candidate_pool)

    model = rating_predictor.train(pool, ratings)

    strategy = _plan(profile, history, ratings, vibe_query=vibe_query)

    iterations: List[IterationRecord] = []
    best_queue: List[Song] = []
    best_score = -1.0
    cleared_threshold = False

    for i in range(MAX_ITERATIONS):
        queue = _act(candidate_pool, strategy, model, ratings, profile)
        score, breakdown = _check(queue, model, ratings)
        cleared = score >= SCORE_THRESHOLD
        will_retry = (not cleared) and (i < MAX_ITERATIONS - 1)

        iterations.append(
            IterationRecord(
                iteration=i + 1,
                strategy=strategy,
                queue_titles=[str(s.get("title", "?")) for s in queue],
                score=score,
                score_breakdown=breakdown,
                retried=will_retry,
            )
        )

        if score > best_score:
            best_score = score
            best_queue = queue

        if cleared:
            cleared_threshold = True
            break

        if will_retry:
            strategy = _retry_strategy(breakdown)

    trace = ReasoningTrace(
        timestamp=_now_iso(),
        profile_name=str(profile.get("name", "")),
        history_length=len(history),
        vibe_query=vibe_query,
        narrowed_pool_size=narrowed_pool_size,
        threshold=SCORE_THRESHOLD,
        iterations=iterations,
        final_score=best_score,
        exhausted_retries=not cleared_threshold,
    )

    _write_trace(trace)

    return best_queue, trace

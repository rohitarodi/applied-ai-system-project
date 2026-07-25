# Tickets: Playlist Chaos → Agentic Music System

Builds the system described in `SPEC.md` (terminology in `CONTEXT.md`, no-LLM/local-only constraint in `docs/adr/0001-no-llm-local-only-agent.md`).

Work the **frontier**: any ticket whose blockers are all done. Right now only ticket 1 is unblocked.

## 1. Persisted local audio library & playback

**What to build:** Repo scaffolding (`assets/`, `diagrams/`, `data/`, `tests/`), `storage.py` for shared JSON load/save (missing/malformed file degrades to empty default + logged warning, never a crash), 2-3 bundled CC0/public-domain sample tracks under `data/samples/` with license noted, the existing hardcoded song library moved into JSON-backed storage, `audio_source.py` resolving local-file Songs to a playable reference, a format-support guard that shows a clear message instead of silent failure on unplayable formats, and real `st.audio()` playback wired into `app.py` in place of the current static text rendering.

**Blocked by:** None — can start immediately.

- [ ] App starts with the bundled sample songs loaded from JSON, not a hardcoded Python list
- [ ] Each song in the UI has a working native audio player for local files
- [ ] An intentionally-unsupported format shows a guard message, not a crash or silent failure
- [ ] Library persists across an app restart
- [ ] pytest covers storage.py load/save edge cases and the format guard

## 2. Archive-URL audio source

**What to build:** Extend `audio_source.py` to resolve `source_type: "archive_url"` Songs (direct link to an open archive) through the same playable-reference + format-guard path as local files, plus a UI way to add/select an archive-URL song.

**Blocked by:** 1

- [ ] A Song with `source_type: "archive_url"` plays through the same `st.audio()` path as local files
- [ ] Format guard applies identically to archive-sourced songs
- [ ] pytest covers both `source_type` values

## 3. Rating system

**What to build:** `ratings.py` with 1-5 star Rating CRUD persisted via `storage.py`, a star widget per song in the UI, and filter/sort of playlist views by rating. "Unrated" is a distinct state, never defaulted to 0.

**Blocked by:** 1

- [ ] User can rate a song 1-5 stars and it persists across restart
- [ ] Unrated songs are visibly distinct from any rated value in the UI and in storage
- [ ] Playlist view can be filtered/sorted by rating
- [ ] pytest covers rating persistence round-trip and the unrated-vs-rated distinction

## 4. VibeQuery retrieval (RAG)

**What to build:** `retrieval.py` building a TF-IDF index over each Song's title/artist/genre/tags (no lyrics), a free-text VibeQuery UI input, and a ranked candidate list shown to the user. Retrieval only returns candidates — it makes no recommendation itself.

**Blocked by:** 1

- [ ] Free-text vibe input returns a ranked, non-empty candidate list for a query that matches existing metadata
- [ ] Candidates span all Playlist moods, not pre-filtered by Hype/Chill/Mixed
- [ ] pytest covers the retrieval ranking on a fixed metadata fixture

## 5. RatingPredictor (fine-tuned stretch)

**What to build:** `rating_predictor.py` — a synthetic bootstrap dataset generator, a locally-trained scikit-learn regressor predicting a user's likely rating for an unrated Song, and a documented before/after comparison against a naive baseline (e.g. average rating).

**Blocked by:** 3

- [ ] Predictor trains and produces a rating prediction for an unrated song using only synthetic data (no real ratings yet)
- [ ] Predictor incorporates real Ratings once present and its output changes measurably from the synthetic-only baseline
- [ ] Baseline-vs-predictor comparison example is written down (README or model_card)
- [ ] pytest covers predictor training/inference on a fixed fixture

## 6. RecommendationAgent core (Smart Recommend)

**What to build:** `agent.py` implementing `agent.recommend(pool, profile, history, ratings, vibe_query=None) -> (Queue, ReasoningTrace)` — plan step (strategy from profile/history/ratings), act step (assemble candidate Queue using RatingPredictor + rules, narrowing by VibeQuery candidates when given), check/critique step (Score from energy variance, artist-repeat penalty, rating alignment), bounded retry on low Score, and a ReasoningTrace written to `ai_interactions.md`. New "Smart Recommend" UI section in `app.py` alongside the untouched Lucky Pick.

**Blocked by:** 3, 4, 5

- [ ] Smart Recommend produces a Queue with a Score at or above threshold, or clearly reports it exhausted retries
- [ ] Retry loop is bounded — a persistently low Score cannot loop forever
- [ ] Every run's plan/act/check/critique steps are logged to `ai_interactions.md`
- [ ] Passing a VibeQuery narrows the candidate pool without pre-filtering by mood bucket
- [ ] Lucky Pick behavior is unchanged
- [ ] pytest covers plan/check logic and the bounded-retry guarantee on fixed fixtures

## 7. TranscriptionTool

**What to build:** `transcription.py` wrapping a local faster-whisper (tiny/base) model, isolated so import/model-load failure is caught and surfaced as a typed "unavailable" result rather than an exception. Standalone user-invoked karaoke/lyrics text generation for a Song in the UI.

**Blocked by:** 1

- [ ] User can request transcription for a song with a resolvable AudioSource and get lyrics/karaoke text back
- [ ] Model-unavailable or transcription-failure path returns a typed "unavailable" result and the rest of the app keeps working
- [ ] pytest covers the isolated-failure path without requiring the actual model to be installed

## 8. eval_harness.py (Test Harness stretch)

**What to build:** A standalone script running `agent.recommend` against a fixed set of named profile/history/vibe-query scenarios, printing a pass/fail + Score summary table.

**Blocked by:** 6

- [ ] Running the script against the fixed scenario set prints a clear pass/fail + Score summary with no manual setup beyond the bundled sample data
- [ ] At least one scenario is designed to fail (e.g. impossible constraints) to prove the harness actually distinguishes pass from fail

## 9. Docs & submission package

**What to build:** `diagrams/architecture.mmd` (Mermaid source covering AudioSource, Ratings, VibeQuery/RAG, RatingPredictor, RecommendationAgent, TranscriptionTool and their data flow), `README.md` (names Playlist Chaos as the original project, architecture overview, setup steps, 2-3 real command-output samples covering Smart Recommend/VibeQuery/eval_harness, design decisions, testing summary, reproducible execution evidence), `model_card.md` (limitations/biases, misuse + mitigation, testing surprises, one helpful + one flawed AI-collaboration example), and finalized `ai_interactions.md` with real embedded/linked ReasoningTrace examples.

**Blocked by:** 2, 5, 6, 7, 8

- [ ] README contains real, reproducible command output for at least 2-3 end-to-end scenarios, not placeholder text
- [ ] Architecture diagram source (`.mmd`) exists and matches the actual module boundaries built
- [ ] model_card.md answers all four required reflection questions under clearly labeled headers
- [ ] README explicitly names and summarizes the original Playlist Chaos project

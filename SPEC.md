## Problem Statement

Playlist Chaos (the Module 1-3 mini-project) sorts songs into mood buckets and picks one at random. It has no real audio, no memory of what the user liked, no way to search by feeling, and no reasoning behind its one recommendation mechanism (Lucky Pick). The user wants a real, playable music system where recommendations are reasoned about and checked rather than random, where their taste is learned over time, and where none of it costs them anything to run (no API keys, no cloud AI billing).

## Solution

Extend Playlist Chaos into an agentic music system. A rule-based RecommendationAgent plans, assembles, and self-critiques a Queue of songs using the user's Profile, History, and Ratings — retrying its own plan if the critique Score is too low. A free-text VibeQuery lets the user describe a mood in their own words, retrieved via TF-IDF over song metadata into candidates the agent can draw from. A locally-trained RatingPredictor learns the user's taste from their Ratings (bootstrapped with synthetic data) and feeds that into the agent's scoring. Real audio (local files or open-archive URLs) is playable, ratable, and optionally transcribed into karaoke text by a local, isolated TranscriptionTool. Every agent run leaves a ReasoningTrace explaining what it decided and why. Everything — agent, predictor, retrieval, transcription — runs locally with no API key and no per-request cost.

## User Stories

1. As a user, I want to point the app at a folder of my own local audio files, so that I can play music I already own.
2. As a user, I want to give the app a direct URL to an audio file on an open archive, so that I can play music without downloading it first.
3. As a user, I want a clear message when a song's format can't be played in-browser, so that I understand why playback failed instead of seeing a silent error.
4. As a user, I want to play a Song with native browser controls, so that I don't need any special software.
5. As a user, I want to rate a Song 1-5 stars, so that the system learns what I like.
6. As a user, I want my ratings to persist across app restarts, so that I don't have to re-rate my library every session.
7. As a user, I want to filter and sort playlists by my rating, so that I can find my favorites quickly.
8. As a user, I want to leave a Song unrated without it being treated as a low rating, so that "unrated" and "rated 1 star" mean different things.
9. As a user, I want to type a free-text vibe description ("rainy night drive"), so that I can search by feeling instead of exact genre/tag matches.
10. As a user, I want VibeQuery results to consider all my songs regardless of their Hype/Chill/Mixed bucket, so that a vibe spanning moods isn't artificially restricted.
11. As a user, I want the system to predict how I'd rate a song I haven't heard yet, so that recommendations reflect my taste even for new songs.
12. As a developer, I want the RatingPredictor to have a synthetic bootstrap dataset, so that it can produce reasonable predictions before I've rated many songs.
13. As a user, I want a "Smart Recommend" action that builds me a Queue, so that I get a reasoned set of songs instead of one random pick.
14. As a user, I want Lucky Pick to keep working exactly as before, so that I still have the simple random baseline for contrast.
15. As a user, I want the RecommendationAgent to plan a strategy based on my Profile and History before picking songs, so that the Queue isn't just a filtered list.
16. As a user, I want the agent to check its own Queue for problems (too little energy variance, too many repeats of the same artist, poor rating alignment) and retry if it's bad, so that I get a better result than a first-pass guess.
17. As a developer, I want the agent's retry loop bounded, so that a persistently low Score can't cause an infinite loop.
18. As a user, I want to see why the agent picked what it picked, so that I can trust or challenge the recommendation.
19. As a developer, I want every agent run's plan/act/check/critique steps written to `ai_interactions.md`, so that the reasoning is inspectable after the fact, not just in a live UI.
20. As a user, I want to optionally get karaoke/lyrics text for a song, so that I can sing along.
21. As a user, I want transcription to be optional, so that if the transcription model isn't installed or fails, the rest of the app keeps working.
22. As a developer, I want the TranscriptionTool isolated behind its own module, so that a transcription failure can't crash Queue generation or playback.
23. As a developer, I want the entire system to run with zero API keys and zero external network calls to paid services, so that running the app never costs the end user money.
24. As a developer, I want song library, ratings, and history stored in local JSON files, so that the app's state survives restarts without a database dependency.
25. As a grader, I want a bundled set of small CC0 sample tracks, so that I can run the app and see real playback/rating/recommendation behavior without supplying my own files.
26. As a grader, I want a pytest suite covering classify_song, the agent's plan/check logic, ratings persistence, and the audio format guard, so that I have automated evidence the system behaves correctly.
27. As a grader, I want an `eval_harness.py` script that runs the agent against fixed scenarios and prints a pass/fail + Score summary, so that I can see reliability evidence without running the UI.
28. As a grader, I want a Mermaid architecture diagram in `diagrams/architecture.mmd`, so that I can read the system's structure from source, not just a screenshot.
29. As a grader, I want the README to name Playlist Chaos as the original project and summarize its original capabilities, so that the extension's baseline is clear.
30. As a grader, I want 2-3 real command-output examples in the README (Smart Recommend run, VibeQuery search, eval_harness output), so that I have reproducible text evidence without watching a video.
31. As a grader, I want `model_card.md` to cover limitations/biases, misuse potential, testing surprises, and one helpful + one flawed AI-collaboration example, so that the responsible-AI reflection is answered in the right place.

## Implementation Decisions

- **Modules**: `app.py` (Streamlit UI only, no business logic) · `playlist_logic.py` (existing normalize/classify/build/search/stats, kept and extended, not replaced) · `agent.py` (RecommendationAgent: plan/act/check/critique) · `audio_source.py` (AudioSource resolution + format guard) · `ratings.py` (Rating CRUD) · `transcription.py` (TranscriptionTool wrapper, isolated) · `storage.py` (shared JSON load/save) · `rating_predictor.py` (RatingPredictor training/inference, synthetic bootstrap generation) · `retrieval.py` (VibeQuery TF-IDF index and query).
- **agent.recommend(pool, profile, history, ratings, vibe_query=None) -> (Queue, ReasoningTrace)**: the single top-level seam. Internally: if `vibe_query` given, narrow `pool` via `retrieval.py` first (mood bucket is not used as a pre-filter, per CONTEXT.md); plan a strategy from profile/history/ratings; act by assembling a candidate Queue using RatingPredictor scores; check by computing a Score (energy variance, artist-repeat penalty, rating alignment); if Score below threshold, retry planning up to a bounded number of iterations; return final Queue plus a ReasoningTrace record of every iteration.
- **Lucky Pick is untouched** — remains the existing random-choice function in `playlist_logic.py`, kept as the contrast baseline alongside Smart Recommend.
- **Playlist buckets (Hype/Chill/Mixed) are unchanged** in meaning and computation (`classify_song`); RecommendationAgent treats mood as one scoring input, never a hard pre-filter, per ADR-consistent design in CONTEXT.md.
- **Rating scale**: integer 1-5 stars. Absence of a rating is a distinct "unrated" state, never defaulted to 0 or any numeric value, in storage and in RatingPredictor training data.
- **RatingPredictor**: scikit-learn regressor (e.g. linear/tree-based — final choice left to implementation, not load-bearing). Trained on real Ratings; when real ratings are sparse, augmented with a synthetic bootstrap dataset generated from heuristic taste rules. Retrains (or is retrainable on demand) as real Ratings accumulate. Consumed only by `agent.py`'s act/check steps — not called directly from `app.py`.
- **VibeQuery retrieval**: TF-IDF over each Song's title/artist/genre/tags concatenated into one document string. No lyrics in the corpus (copyright). Retrieval returns a ranked candidate list; the agent decides what to do with it, retrieval itself makes no recommendation.
- **AudioSource**: `source_type` field of `"local"` or `"archive_url"`. `audio_source.resolve(song)` returns a playable reference (path or URL) plus a guard result indicating whether the browser can likely play the format; playback goes through Streamlit's native `st.audio()` — no server-side transcoding, no ffmpeg dependency for playback itself.
- **TranscriptionTool**: wraps a local faster-whisper model (tiny/base size). Import and model load are isolated inside `transcription.py` so their absence/failure raises a caught, typed condition the caller can treat as "unavailable" rather than a crash. Can be invoked standalone by the user or as a tool-call from the agent's flow when building a Queue.
- **Persistence**: plain JSON files under `data/` (library, ratings, history), read/write via `storage.py`. Malformed or missing files degrade to an empty default plus a logged warning, never a crash.
- **Bundled sample audio**: 2-3 small CC0/public-domain tracks committed under `data/samples/`, with license/provenance noted in the README.
- **No LLM anywhere in the stack** — this is the load-bearing decision from ADR 0001. The agent's "reasoning" and the ReasoningTrace text are generated from deterministic rule evaluations, not natural-language model output.

## Testing Decisions

- Good tests here exercise the four seams' external behavior (inputs → Queue/Rating/playable-ref/lyrics-or-unavailable) — not internal call counts or intermediate data shapes.
- `agent.recommend`: tested with fixed Profile/History/Ratings fixtures and assertions on Queue properties (bounded retry count, Score above threshold on return, ReasoningTrace has one entry per attempted iteration). Also test the `vibe_query` path narrows the pool as expected without mood pre-filtering.
- `ratings.rate_song`: tested for persistence round-trip, and that "unrated" is distinguishable from any rated value.
- `audio_source.resolve`: tested against both `source_type` values, and against at least one deliberately unsupported format to confirm the guard fires instead of raising.
- `transcription.transcribe`: tested for the isolated-failure path (model unavailable) returning a typed "unavailable" result rather than propagating an exception into the caller.
- Existing `classify_song`/`build_playlists` tests (new, since none exist today) act as regression coverage so the RecommendationAgent's use of mood as a scoring input doesn't silently break bucket assignment.
- `eval_harness.py` is a separate, coarser-grained artifact: runs `agent.recommend` against a fixed set of named scenarios and prints a pass/fail + Score table — this is the reliability evidence for grading, not a substitute for the pytest suite.
- No prior art for tests in this codebase — Playlist Chaos ships no tests today; this spec establishes the first test suite.

## Out of Scope

- Any cloud/paid AI API (LLM, hosted transcription, hosted embeddings) — explicitly excluded by the no-API-key/no-cost constraint (ADR 0001).
- Audio EQ/DSP (bass/treble/effects) — descoped during grilling in favor of the rating system.
- Server-side transcoding/ffmpeg pipeline for playback — native browser playback only, with a format guard instead.
- Bundling or displaying copyrighted song lyrics text — VibeQuery's corpus is metadata only.
- A second stretch model beyond RatingPredictor (e.g. a separate fine-tuned mood classifier) — one specialized local model is in scope, not two.
- GitHub issue/label creation itself — this spec is the input to `/to-tickets`, which will propose the actual issue breakdown for separate confirmation before anything is created on the public repo.
- Multi-user accounts or auth — single local user, single machine, matching the existing Streamlit session-state model's scope.

## Further Notes

- Terminology throughout this spec follows `CONTEXT.md` (Song, Profile, Playlist, History, Lucky Pick, Rating, RecommendationAgent, Queue, Score, VibeQuery, RatingPredictor, TranscriptionTool, AudioSource, ReasoningTrace) — implementers should read it before starting.
- ADR 0001 (`docs/adr/0001-no-llm-local-only-agent.md`) records why the agent is rule-based rather than LLM-driven; don't revisit that decision mid-implementation without a new ADR.
- This spec covers the full system in one document because the grilling session treated it as one coherent design; `/to-tickets` is expected to split it into the epics already sketched in `TASKS.md` (foundation, audio, rating, RAG, fine-tuned predictor, agent, transcription, testing, docs) — that draft should be treated as a strong starting point for ticket boundaries, not re-derived from scratch.
- Rubric alignment (for the implementer's awareness, not part of the product itself): RecommendationAgent = required Agentic Workflow feature; TranscriptionTool tool-call + ReasoningTrace = Agentic Workflow Enhancement stretch; `eval_harness.py` = Test Harness stretch; VibeQuery/retrieval = RAG Enhancement stretch; RatingPredictor = Fine-Tuning/Specialization stretch.

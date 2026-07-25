# Task Breakdown

Draft for review. Nothing here is created on GitHub yet — once approved, these become issues on `rohitarodi/applied-ai-system-project`. Terms used below are defined in `CONTEXT.md`.

## Epic 1: Foundation & repo hygiene

1. **Repo scaffolding** — create `assets/`, `diagrams/`, `data/`, `tests/` folders; `.gitignore` for `data/*.json` runtime state (keep bundled sample audio + seed JSON tracked); initial commit.
2. **storage.py** — JSON load/save helpers used by ratings/history/library. Handles missing-file (first run) and malformed-JSON (guardrail: log + fall back to empty, never crash).
3. **Bundle sample audio** — source 2-3 small CC0/public-domain tracks (e.g. Musopen/freesound), add to `data/samples/`, document provenance/license in README.

## Epic 2: AudioSource & playback

4. **audio_source.py: dual source resolution** — `source_type: "local" | "archive_url"`, resolves a Song's playable reference from either a filesystem path or a direct archive URL.
5. **Format-support guard** — detect unsupported/unplayable formats at load time (e.g. exotic codecs), show clear guardrail message in UI instead of silent failure.
6. **Wire playback into app.py** — replace static song list rendering with real `st.audio()` playback per Song.

## Epic 3: Rating system

7. **ratings.py: Rating CRUD** — 1-5 star rating per Song, persisted via storage.py. Unrated songs stay unrated (no default score).
8. **Rating UI in app.py** — star widget per song in playlist views, filter/sort playlist by rating.

## Epic 4: RAG (VibeQuery retrieval)

9. **Metadata corpus + TF-IDF retrieval** — build retrieval index over Song title/artist/genre/tags (no lyrics). Given free-text VibeQuery, return ranked candidate songs.
10. **VibeQuery UI** — free-text input box, shows retrieved candidates before handing off to the agent.

## Epic 5: Fine-tuned RatingPredictor

11. **Synthetic bootstrap dataset** — generate synthetic (Song features → rating) examples to allow training before real ratings accumulate.
12. **Train RatingPredictor** — scikit-learn regressor (energy/genre/tags → predicted rating), retrains/updates as real Ratings accumulate.
13. **Baseline comparison doc** — before/after example showing RatingPredictor output vs. a naive baseline (e.g. average rating), for README/model_card per RAG/Fine-Tuning stretch requirement.

## Epic 6: RecommendationAgent (core required feature)

14. **agent.py: plan step** — given Profile + History + Ratings, decide a strategy (e.g. "need more Hype," "diversify artist," "use VibeQuery candidates").
15. **agent.py: act step** — assemble a candidate Queue from the full song pool (or VibeQuery candidates) using RatingPredictor + rules.
16. **agent.py: check/critique step** — compute Score (energy variance, artist-repeat penalty, rating alignment); retry planning (bounded iterations) if Score below threshold.
17. **ReasoningTrace logging** — write each run's plan/act/check/critique steps to `ai_interactions.md`.
18. **Smart Recommend UI** — new section in app.py alongside existing Lucky Pick, triggers the agent, displays Queue + why it was chosen.

## Epic 7: TranscriptionTool (agentic stretch)

19. **transcription.py: faster-whisper wrapper** — isolated local transcription call (tiny/base model), returns lyrics/karaoke text for a Song's AudioSource.
20. **Tool-call integration** — agent (or user) can request transcription for a Queue song; failure/absence of model doesn't break the rest of the app.

## Epic 8: Reliability & testing

21. **pytest suite** — cover classify_song (existing), agent plan/check logic, ratings persistence, audio format guard, storage load/save edge cases.
22. **eval_harness.py** — run RecommendationAgent against fixed profile/history/VibeQuery scenarios, print pass/fail + Score summary (satisfies Test Harness stretch).

## Epic 9: Documentation & submission

23. **diagrams/architecture.mmd** — Mermaid source covering components (AudioSource, Ratings, VibeQuery/RAG, RatingPredictor, RecommendationAgent, TranscriptionTool) and data flow.
24. **README.md** — name original project (Playlist Chaos), architecture overview, setup steps, 2-3 sample interactions with real command output, design decisions, testing summary, reflection pointer to model_card.md, reproducible execution evidence (commands + outputs).
25. **model_card.md** — limitations/biases, misuse potential + mitigation, testing surprises, AI-collaboration reflection (one helpful + one flawed suggestion).
26. **ai_interactions.md** — embed or link committed ReasoningTrace log examples.

---

Review this list — reorder, cut, merge, or split anything before these become GitHub issues.

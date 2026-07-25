# Playlist Chaos → Agentic Music System

A Streamlit music app that classifies songs by mood, lets a user rate and play their own audio, and uses a rule-based agent to plan, check, and critique song recommendations. Extends the original "Playlist Chaos" mini-project (Modules 1-3).

## Language

**Song**:
A track with metadata (title, artist, genre, energy, tags) and a resolved `mood`. Owns zero or one `Rating` and references exactly one `AudioSource`.
_Avoid_: Track, item (when metadata is meant, not the audio bytes)

**Profile**:
The user's tunable preferences (hype/chill energy thresholds, favorite genre) that `classify_song` uses to assign a Song's mood.
_Avoid_: Settings, preferences (when the specific tunable thresholds are meant)

**Playlist**:
One of the three fixed mood buckets (Hype, Chill, Mixed) a Song is sorted into by `classify_song`. Structural grouping, not a recommendation.
_Avoid_: Queue (see below — a Queue is agent output, not a mood bucket)

**History**:
The ordered log of songs the user has played or been given, via Lucky Pick or the RecommendationAgent. Distinct from ReasoningTrace, which logs *why* an agent chose what it chose.

**Lucky Pick**:
The existing random-choice baseline (one Song, no reasoning). Kept unchanged as the "dumb" contrast case against the RecommendationAgent's Queue.
_Avoid_: Random pick, quick pick

**Rating**:
A user-assigned 1-5 star score for a Song, persisted, and the training signal for RatingPredictor. Absence of a Rating means "unrated," not zero.
_Avoid_: Score (Score is the RecommendationAgent's internal critique metric — a different thing, see below)

**RecommendationAgent**:
The rule-based plan → act → check → critique loop that produces a Queue. Never calls an LLM — its "reasoning" is deterministic Python logic over Profile, History, Rating, and RatingPredictor output. See ADR 0001.
_Avoid_: Recommender, engine (too vague — this is specifically the agentic loop, not just a scoring function)

**Queue**:
An ordered list of Songs produced by one RecommendationAgent run, drawn from the full song pool across all Playlist moods (mood is a scoring input, not a pre-filter). Ephemeral per request — not persisted as its own entity, only logged via ReasoningTrace and appended to History.
_Avoid_: Playlist (a Queue is agent output; a Playlist is a static mood bucket)

**Score**:
The RecommendationAgent's internal numeric self-critique of a candidate Queue (energy variance, artist-repeat penalty, rating alignment). Used to decide whether to retry planning.
_Avoid_: Confidence (Confidence is user/reader-facing framing of this same number in reliability reporting; Score is the internal mechanism)

**VibeQuery**:
Free-text natural-language mood/vibe input from the user (e.g. "rainy night drive"). Resolved via TF-IDF retrieval over Song metadata (title, artist, genre, tags — never lyrics) into a candidate set for the RecommendationAgent. Bypasses Playlist mood filtering entirely; the agent's own critique handles coherence.
_Avoid_: Search query, prompt

**RatingPredictor**:
A locally-trained scikit-learn regressor that predicts the Rating a user would likely give an unrated Song. Trained on real Ratings plus a synthetic bootstrap dataset when real ratings are sparse. Consulted by the RecommendationAgent's check/critique step — not user-facing on its own.
_Avoid_: Model (too generic — this project has exactly one specialized model; name it)

**TranscriptionTool**:
An optional tool the RecommendationAgent (or user) can invoke to generate karaoke/lyrics text for a Song via a local faster-whisper model. Isolated: failure or absence never breaks Queue generation or playback.
_Avoid_: Transcriber

**AudioSource**:
Where a Song's playable bytes come from — `source_type` of either `local` (filesystem path) or `archive_url` (direct link to an open archive). Carries the format-support guard result for playback.
_Avoid_: File, stream (either alone is ambiguous between the two source_types)

**ReasoningTrace**:
The recorded plan/act/check/critique steps for one RecommendationAgent run, written to `ai_interactions.md`. The evidence artifact for "explain the AI's decision-making," not the same thing as History (which just logs the outcome).
_Avoid_: Log (too generic — this project has application logs too; ReasoningTrace is specifically agent reasoning)

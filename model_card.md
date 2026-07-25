# Model Card: Playlist Chaos → Agentic Music System

This is the required responsible-AI reflection for this project (per `instructions.txt`
Step 5). It covers limitations/biases, misuse potential, testing surprises, and an
honest account of AI collaboration during the build — answered here only, not repeated
in `README.md`.

## What are the limitations or biases in your system?

- **RatingPredictor's synthetic bootstrap encodes an arbitrary heuristic taste rule, not
  real user taste.** `rating_predictor.py`'s `generate_synthetic_dataset` rates songs
  higher for high energy and for `rock`/`electronic` genres with `guitar`/`synth`/
  `party` tags (`PREFERRED_GENRES`, `PREFERRED_TAGS`). This is a made-up stand-in so the
  regressor has *something* to fit before real ratings exist — it is explicitly not a
  claim about any actual person's preferences, and until a user has rated enough songs,
  every prediction is biased toward this arbitrary rule (e.g. a fan of quiet ambient
  music would see their unrated songs under-predicted at first).
- **TF-IDF retrieval (VibeQuery) has no semantic understanding beyond token/n-gram
  overlap.** A query like "melancholy" will not match a song tagged "sad" unless that
  exact token (or a shared stem) appears in the song's title/artist/genre/tags — there
  is no embedding space capturing synonymy or mood concepts the corpus text doesn't
  literally contain.
- **Cold-start scenarios rely heavily on synthetic data.** Both the RatingPredictor
  (synthetic bootstrap) and the RecommendationAgent's `explore_unrated` strategy assume
  a new user's early experience is shaped mostly by heuristics, not by anything they've
  actually told the system.
- **Small bundled sample pool.** The shipped library is 22 songs and 3 synthetic audio
  tones; VibeQuery's ranking quality and the agent's Score computation (energy variance,
  artist-repeat penalty) are only as meaningful as the diversity of that small pool —
  behavior on a real user's much larger library is untested.
- **The agent's Score weights are hand-tuned constants, not learned or validated.**
  `W_VARIANCE = 0.3`, `W_ARTIST = 0.3`, `W_RATING = 0.4`, `SCORE_THRESHOLD = 0.55`, and
  `TARGET_ENERGY_VARIANCE = 6.0` in `agent.py` were chosen because they produced
  reasonable-looking Queues during development, not because they were fit or validated
  against real user satisfaction data. A different set of constants would produce
  differently "reasoned" Queues with equal internal consistency.

## Could your AI be misused, and how would you prevent that?

- **Blast radius is limited by design**: the entire stack (RecommendationAgent,
  RatingPredictor, TranscriptionTool, retrieval) runs locally with no API key and no
  outbound network calls to any paid or third-party AI service (ADR 0001). There is no
  server-side component collecting or transmitting user data anywhere — ratings, history,
  and library data stay in local JSON files under `data/`.
- **TranscriptionTool could theoretically be pointed at copyrighted audio to extract
  lyrics.** `transcription.py` will attempt to transcribe whatever audio reference it's
  given, including a user-supplied `archive_url`. Mitigation: it is a standalone,
  user-invoked, single-song tool — there is no bulk-scraping or batch-transcription
  feature, no crawler, and no mechanism to feed it a list of URLs automatically. Using it
  against content the user doesn't have rights to would require the same manual,
  one-song-at-a-time effort as playing that file directly; the tool doesn't lower that
  bar in any meaningful way, and VibeQuery's retrieval corpus deliberately excludes
  lyrics entirely so no transcript text is ever indexed or persisted.
- **RatingPredictor doesn't store or transmit personal taste data externally** — it
  trains an in-memory scikit-learn model per call from local `data/ratings.json`
  contents; nothing about a user's ratings leaves the machine.
- **No accounts, no auth, no multi-user data mixing** — the app is explicitly scoped
  (per `SPEC.md`) to a single local user on a single machine, so there's no scenario
  where one user's ratings or history could leak to or influence another user's session.

## What surprised you while testing your AI's reliability?

Two concrete things stood out from real test/eval_harness runs, not hypotheticals:

1. **How few real ratings were needed to measurably move RatingPredictor's output.**
   Per `docs/rating_predictor_comparison.md`, before any real rating exists, the
   synthetic-only model predicts Thunderstruck (rock, energy 9) at **4.44** — the
   synthetic heuristic already favors loud rock songs. After adding exactly *one* real
   1-star rating for that exact song, the retrained prediction drops to **1.86** — a
   swing of about 2.59 on a 1-5 scale from a single data point. That the
   `REAL_RATING_WEIGHT = 20.0` weighting was enough to move a model trained on ~200
   synthetic rows that dramatically, from one real example, was a bigger effect than
   expected going in.
2. **The bounded-retry loop actually needed multiple iterations on a real scenario, not
   just in theory.** `eval_harness.py`'s `impossible_artist_repeat` scenario (a 2-song
   pool, both by the same artist, both rated 1 star) is designed so its best-possible
   Score (0.45) can never clear the 0.55 threshold. Running it for real showed the agent
   didn't just fail fast — it retried through all `MAX_ITERATIONS = 4` iterations,
   trying `explore_unrated` then `favor_high_rated` three more times, each attempt
   landing on the identical Score (0.350) before giving up and returning the best Queue
   found (see the corresponding `ai_interactions.md` entry). Seeing the retry loop
   genuinely exhaust itself against real math, rather than just trusting the bound
   existed, was reassuring evidence the guardrail works as designed rather than being
   dead code.

## Describe your collaboration with AI during this project

**A helpful instance**: during Ticket 2 (archive-URL audio source, commit `01f6c7a`),
the implementing agent caught that `normalize_song()` in `playlist_logic.py` only
recognizes and rebuilds `title`/`artist`/`genre`/`energy`/`tags` — any other key on the
raw song dict passed in, including a freshly-attached `audio` field, would have been
silently dropped by the normalization rebuild. The fix (visible in `app.py`'s
`add_song_sidebar()`) was to call `normalize_song(song)` first and attach the `audio`
field to the *normalized* dict afterward, with a comment explaining why order matters
here. Without that catch, every song added through the sidebar would have lost its audio
reference the moment it was normalized, and playback would have silently failed for
every newly-added song — a bug that would have been confusing to track down later since
nothing would have raised an error.

**A flawed instance**: the RecommendationAgent's Score formula (`W_VARIANCE = 0.3`,
`W_ARTIST = 0.3`, `W_RATING = 0.4`, and `SCORE_THRESHOLD = 0.55`) was proposed and
accepted as a reasonable-looking set of constants during Ticket 6, without any actual
validation against how a real user would judge Queue quality — they were tuned by eyeballing
a handful of example Queues rather than by any systematic process. That's a real gap:
the whole premise of the critique step is "the agent checks whether its Queue is good,"
but "good" here is defined by numbers nobody tested against actual human satisfaction. A
more rigorous approach would have been to collect example Queues, have a person rank
them, and fit the weights to match those rankings — instead the weights are honestly
documented as "not load-bearing" placeholders in `agent.py`'s own comments, which is the
right level of humility about them but doesn't make them correct.

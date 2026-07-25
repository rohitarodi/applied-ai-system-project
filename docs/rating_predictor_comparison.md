# RatingPredictor: baseline-vs-predictor comparison

This is the required before/after evidence for RatingPredictor (Ticket 5),
captured from an actual run of `rating_predictor.py` against a fixed
4-song test fixture (`Thunderstruck`/AC-DC rock energy=9, `Lo-fi Rain`/DJ
Calm lofi energy=2, `Night Drive`/Neon Echo electronic energy=6, `Mystery
Song`/Unknown Artist pop energy=5). See `tests/test_rating_predictor.py`
for the exact fixture and the reproducible numeric assertion.

## Numbers

For the song **Thunderstruck** (rock, energy 9, tags `classic`/`guitar`):

| Predictor | Real ratings available | Predicted rating |
|---|---|---|
| Naive baseline (`naive_baseline_predict`) | none | **3.0** (documented fallback midpoint) |
| RatingPredictor, synthetic-bootstrap-only | none | **4.44** |
| RatingPredictor, retrained after one real rating | Thunderstruck rated **1 star** | **1.86** |
| Naive baseline (`naive_baseline_predict`) | Thunderstruck rated 1 star | **1.0** (plain average of the one real rating) |

Synthetic-only vs. with-real-rating delta for Thunderstruck: **4.44 → 1.86**,
a swing of about **2.59** on the 1-5 scale.

## What this shows

Before any real ratings exist, RatingPredictor's synthetic bootstrap
heuristic (which favors high energy and rock/electronic genres with
guitar/synth/party tags) predicts Thunderstruck fairly high at 4.44 --
noticeably above the naive 3.0 fallback, since the synthetic rule already
"likes" loud rock songs. Once a single real 1-star rating for that exact
song is added, RatingPredictor is retrained with that real rating weighted
20x a synthetic row (`REAL_RATING_WEIGHT` in `rating_predictor.py`), and the
prediction drops to 1.86 -- a measurable shift toward the real signal,
demonstrating that the predictor incorporates real Ratings once present
rather than staying anchored to the synthetic-only baseline. The naive
average baseline reacts even more sharply (jumping straight to the single
observed value, 1.0) because it has no model of song features at all --
RatingPredictor's 1.86 reflects a blend of the real signal and the
synthetic prior, which is the intended behavior for a regressor trained on
a mix of both.

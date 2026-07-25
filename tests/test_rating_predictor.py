import math

import rating_predictor
import ratings


def make_song(title, artist, genre, energy, tags):
    return {"title": title, "artist": artist, "genre": genre, "energy": energy, "tags": tags}


# Fixed, small fixture -- intentionally not the live 22-song data/library.json.
LOUD_ROCK_SONG = make_song("Thunderstruck", "AC/DC", "rock", 9, ["classic", "guitar"])
QUIET_LOFI_SONG = make_song("Lo-fi Rain", "DJ Calm", "lofi", 2, ["study"])
MID_ELECTRONIC_SONG = make_song("Night Drive", "Neon Echo", "electronic", 6, ["synth"])
UNRATED_POP_SONG = make_song("Mystery Song", "Unknown Artist", "pop", 5, [])

FIXTURE_SONGS = [LOUD_ROCK_SONG, QUIET_LOFI_SONG, MID_ELECTRONIC_SONG, UNRATED_POP_SONG]


def test_generate_synthetic_dataset_is_deterministic_given_same_seed():
    first = rating_predictor.generate_synthetic_dataset(n_samples=50, seed=42)
    second = rating_predictor.generate_synthetic_dataset(n_samples=50, seed=42)

    assert first == second


def test_generate_synthetic_dataset_differs_across_seeds():
    seed_42 = rating_predictor.generate_synthetic_dataset(n_samples=50, seed=42)
    seed_7 = rating_predictor.generate_synthetic_dataset(n_samples=50, seed=7)

    assert seed_42 != seed_7


def test_train_predict_round_trip_synthetic_only():
    model = rating_predictor.train(FIXTURE_SONGS, ratings={})
    prediction = rating_predictor.predict(model, UNRATED_POP_SONG)

    assert isinstance(prediction, float)
    assert math.isfinite(prediction)
    # Regression output on a 1-5 scale -- allow slack rather than a brittle
    # narrow range, per the ticket's guidance.
    assert 0.0 <= prediction <= 6.0


def test_real_ratings_measurably_shift_prediction_from_synthetic_only_baseline():
    # Synthetic-only model: no real ratings at all.
    synthetic_only_model = rating_predictor.train(FIXTURE_SONGS, ratings={})
    prediction_before = rating_predictor.predict(synthetic_only_model, LOUD_ROCK_SONG)

    # Now add a real rating that *contradicts* the synthetic heuristic's
    # expectation for this song: LOUD_ROCK_SONG is high-energy rock with
    # preferred tags, so the synthetic rule pushes its rating up -- but the
    # (simulated) real user hates it and rates it 1 star. A single real
    # rating is enough here because train() weights each real rating
    # REAL_RATING_WEIGHT (20x) heavier than a synthetic row when fitting.
    real_ratings = {ratings.song_key(LOUD_ROCK_SONG): 1}
    retrained_model = rating_predictor.train(FIXTURE_SONGS, ratings=real_ratings)
    prediction_after = rating_predictor.predict(retrained_model, LOUD_ROCK_SONG)

    assert abs(prediction_after - prediction_before) > 0.3
    # The real 1-star rating should have pulled the prediction down, not up.
    assert prediction_after < prediction_before


def test_naive_baseline_predict_is_plain_average_of_real_ratings():
    real_ratings = {
        ratings.song_key(LOUD_ROCK_SONG): 5,
        ratings.song_key(QUIET_LOFI_SONG): 1,
    }

    result = rating_predictor.naive_baseline_predict(FIXTURE_SONGS, real_ratings)

    assert result == 3.0  # (5 + 1) / 2


def test_naive_baseline_predict_falls_back_to_documented_default_when_no_ratings():
    result = rating_predictor.naive_baseline_predict(FIXTURE_SONGS, {})

    assert result == rating_predictor.NAIVE_BASELINE_FALLBACK
    assert result == 3.0

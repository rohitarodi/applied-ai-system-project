import retrieval


def make_fixture():
    """A small, fixed metadata fixture spanning multiple genres/tags/moods.

    Deliberately not the live 22-song data/library.json -- per the project's
    Testing Decisions, ranking assertions must run against a fixture we
    control so they don't silently break when someone edits library data.

    Two songs ("Thunder Rain" and "Rainy Study") are both tagged "rain" but
    sit at very different energy levels (one clearly Hype-ish, one clearly
    Chill-ish under any reasonable profile), so a "rain" query can be
    checked for spanning moods without retrieval itself knowing about mood.
    """
    return [
        {
            "title": "Thunder Rain",
            "artist": "Storm Crew",
            "genre": "rock",
            "energy": 9,
            "tags": ["rain", "storm", "loud"],
        },
        {
            "title": "Rainy Study",
            "artist": "Lo-fi Bear",
            "genre": "lofi",
            "energy": 2,
            "tags": ["rain", "study", "calm"],
        },
        {
            "title": "Desert Sun",
            "artist": "Dune Riders",
            "genre": "rock",
            "energy": 8,
            "tags": ["heat", "drive"],
        },
        {
            "title": "Neon Nights",
            "artist": "Synth City",
            "genre": "electronic",
            "energy": 6,
            "tags": ["city", "night"],
        },
        {
            "title": "Ocean Breeze",
            "artist": "Coastal Sound",
            "genre": "ambient",
            "energy": 1,
            "tags": ["ocean", "sleep"],
        },
        {
            "title": "Jazz Cafe",
            "artist": "Blue Note Trio",
            "genre": "jazz",
            "energy": 4,
            "tags": ["cafe", "smooth"],
        },
    ]


def test_query_matching_genre_and_title_ranks_song_at_top():
    songs = make_fixture()
    index = retrieval.build_index(songs)

    results = retrieval.query(index, "thunder rain storm", top_k=3)

    assert results
    assert results[0]["title"] == "Thunder Rain"


def test_query_matching_tag_across_moods_spans_both_songs():
    songs = make_fixture()
    index = retrieval.build_index(songs)

    results = retrieval.query(index, "rain", top_k=6)
    titles = {song["title"] for song in results}

    # Both the loud/Hype-ish song and the calm/Chill-ish song carry the
    # "rain" tag -- retrieval must not filter either out based on energy
    # or genre, proving there's no hidden mood/bucket filter.
    assert "Thunder Rain" in titles
    assert "Rainy Study" in titles


def test_results_are_not_grouped_or_pre_filtered_by_bucket():
    songs = make_fixture()
    index = retrieval.build_index(songs)

    results = retrieval.query(index, "rain calm study", top_k=6)

    # The full pool (all 6 songs, spanning rock/lofi/electronic/ambient/jazz)
    # is eligible to appear -- retrieval ranks across the whole set rather
    # than restricting to a single genre or energy band.
    assert len(results) == 6
    genres_present = {song["genre"] for song in results}
    assert len(genres_present) > 1


def test_empty_song_pool_returns_empty_list_without_crashing():
    index = retrieval.build_index([])

    results = retrieval.query(index, "anything", top_k=5)

    assert results == []


def test_query_with_no_vocabulary_overlap_does_not_crash():
    songs = make_fixture()
    index = retrieval.build_index(songs)

    # None of these words appear anywhere in the fixture's metadata, so
    # every similarity score is 0. Documented behavior: fall back to
    # original pool order rather than raising or returning garbage.
    results = retrieval.query(index, "xyzzy quux frobnicate", top_k=3)

    assert len(results) == 3
    assert results == songs[:3]


def test_top_k_limits_result_count():
    songs = make_fixture()
    index = retrieval.build_index(songs)

    results = retrieval.query(index, "rain", top_k=2)

    assert len(results) == 2

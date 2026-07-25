"""VibeQuery retrieval: TF-IDF search over Song metadata.

This module implements retrieval-only ranking for free-text "vibe" queries
(e.g. "rainy night drive"). It is deliberately NOT a recommender: it never
looks at ratings, never filters by Playlist mood (Hype/Chill/Mixed), and
never picks a single "best" song. It only ranks the full song pool by
textual similarity to the query and hands back the ordered candidates so a
later stage (a RecommendationAgent, not built yet) can decide what to do
with them.

Indexed fields are strictly metadata: title, artist, genre, and tags. Lyrics
are never indexed here (Playlist Chaos has no lyrics field on Song, and even
if it gained one, VibeQuery must stay metadata-only per the project spec).
"""

from dataclasses import dataclass
from typing import List

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity


@dataclass
class RetrievalIndex:
    """A fitted TF-IDF index over a fixed pool of songs.

    Bundles the fitted vectorizer, the document-term matrix, and the exact
    list of song dicts the matrix rows correspond to (by position), so
    `query()` can map similarity scores back to full song records.
    """

    vectorizer: TfidfVectorizer
    matrix: object  # scipy sparse matrix, shape (len(songs), vocab_size)
    songs: List[dict]


def _document_for(song: dict) -> str:
    """Build the flat text document TF-IDF is fit over for one song.

    Concatenates title, artist, genre, and tags (tags joined with spaces).
    Deliberately excludes energy, mood, ratings, and audio fields -- none of
    those are text and mood in particular must stay out so VibeQuery ranking
    never becomes a proxy for Playlist bucket membership.
    """
    title = str(song.get("title", ""))
    artist = str(song.get("artist", ""))
    genre = str(song.get("genre", ""))
    tags = song.get("tags", [])
    if isinstance(tags, str):
        tags = [tags]
    tags_text = " ".join(str(t) for t in tags)
    return " ".join([title, artist, genre, tags_text])


def build_index(songs: List[dict]) -> RetrievalIndex:
    """Fit a TF-IDF vectorizer + matrix over a song pool.

    No persistence or caching -- the pool is small (~22 songs in this
    project) so refitting per query is cheap and keeps the index always in
    sync with whatever song list the caller passes in.
    """
    vectorizer = TfidfVectorizer()

    if not songs:
        # Nothing to fit -- fit_transform on an all-empty corpus raises
        # ("empty vocabulary"), so skip fitting entirely. query() checks
        # `index.songs` first and returns [] before ever touching matrix.
        return RetrievalIndex(vectorizer=vectorizer, matrix=None, songs=[])

    documents = [_document_for(song) for song in songs]
    matrix = vectorizer.fit_transform(documents)

    return RetrievalIndex(vectorizer=vectorizer, matrix=matrix, songs=list(songs))


def query(index: RetrievalIndex, text: str, top_k: int = 10) -> List[dict]:
    """Rank the indexed song pool by cosine similarity to a free-text query.

    Returns up to `top_k` songs ordered by similarity descending. Never
    filters or groups by mood/Playlist bucket -- candidates may span Hype,
    Chill, and Mixed alike, since retrieval only knows about text, not mood.

    Edge cases:
    - Empty song pool -> returns [] without crashing.
    - Query with zero vocabulary overlap (all similarities 0, e.g. an empty
      query string, or words never seen in any song's metadata) -> returns
      the first `top_k` songs in original pool order rather than crashing.
      This is a deliberate choice: a "no match" query still surfaces some
      candidates instead of leaving the user with nothing, and callers can
      treat a fully-zero similarity result as "unranked" if they care to.
    """
    songs = index.songs
    if not songs:
        return []

    query_vec = index.vectorizer.transform([text or ""])
    similarities = cosine_similarity(query_vec, index.matrix)[0]

    if not similarities.any():
        return songs[:top_k]

    ranked_positions = sorted(
        range(len(songs)),
        key=lambda i: similarities[i],
        reverse=True,
    )
    top_positions = ranked_positions[:top_k]
    return [songs[i] for i in top_positions]

"""Reciprocal Rank Fusion — combines multiple ranked id lists (e.g. semantic
search and full-text search) into one ranking, without needing their scores
to be on comparable scales.
"""
from __future__ import annotations

import uuid

# Standard RRF constant (as used by Elasticsearch and the original RRF paper).
# Dampens the impact of rank 1 vs. rank 2 so one method's top hit doesn't
# dominate purely by being first.
DEFAULT_K = 60


def reciprocal_rank_fusion(
    rankings: list[list[uuid.UUID]], k: int = DEFAULT_K
) -> list[tuple[uuid.UUID, float]]:
    """Fuse ranked id lists into one list of (id, score) sorted by score desc.

    score(id) = sum over rankings containing id of 1 / (k + rank), where rank
    is that id's 1-based position in the ranking. Ids absent from a ranking
    contribute nothing from it, so a candidate found by only one method can
    still rank if it placed highly there.
    """
    scores: dict[uuid.UUID, float] = {}
    for ranking in rankings:
        for rank, doc_id in enumerate(ranking, start=1):
            scores[doc_id] = scores.get(doc_id, 0.0) + 1.0 / (k + rank)

    return sorted(scores.items(), key=lambda item: item[1], reverse=True)

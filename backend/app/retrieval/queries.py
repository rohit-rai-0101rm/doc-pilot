"""Raw retrieval queries against `document_chunks`: pgvector semantic search
and Postgres full-text search. Each returns chunk ids ranked by that method's
own score so `fusion.py` can combine them independently of scale.
"""
from __future__ import annotations

import uuid

from sqlalchemy import select, text
from sqlalchemy.orm import Session

from app.database.models import DocumentChunk


def semantic_search(
    db: Session, query_embedding: list[float], limit: int
) -> list[tuple[uuid.UUID, float]]:
    """Nearest chunks by cosine distance (smaller is more similar)."""
    rows = db.execute(
        select(
            DocumentChunk.id,
            DocumentChunk.embedding.cosine_distance(query_embedding).label("distance"),
        )
        .where(DocumentChunk.embedding.is_not(None))
        .order_by("distance")
        .limit(limit)
    ).all()
    return [(row.id, row.distance) for row in rows]


def full_text_search(
    db: Session, query_text: str, limit: int
) -> list[tuple[uuid.UUID, float]]:
    """Chunks matching `query_text` by Postgres full-text search, ranked by
    `ts_rank_cd` (higher is more relevant). `websearch_to_tsquery` tolerates
    free-form user input (quotes, `-exclude`) without raising on syntax.
    """
    rows = db.execute(
        text(
            """
            SELECT id, ts_rank_cd(search_vector, websearch_to_tsquery('english', :query)) AS rank
            FROM document_chunks
            WHERE search_vector @@ websearch_to_tsquery('english', :query)
            ORDER BY rank DESC
            LIMIT :limit
            """
        ),
        {"query": query_text, "limit": limit},
    ).all()
    return [(row.id, row.rank) for row in rows]

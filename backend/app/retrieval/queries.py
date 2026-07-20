"""Raw retrieval queries against `document_chunks`: pgvector semantic search
and Postgres full-text search. Each returns chunk ids ranked by that method's
own score so `fusion.py` can combine them independently of scale.
"""
from __future__ import annotations

import uuid

from sqlalchemy import select, text
from sqlalchemy.orm import Session, selectinload

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


def fetch_chunk_by_id(db: Session, chunk_id: uuid.UUID) -> DocumentChunk | None:
    return db.scalars(
        select(DocumentChunk)
        .where(DocumentChunk.id == chunk_id)
        .options(selectinload(DocumentChunk.document))
    ).first()


def fetch_neighbor_chunks(
    db: Session, document_id: uuid.UUID, chunk_index: int
) -> tuple[DocumentChunk | None, DocumentChunk | None]:
    """Bounded read of the chunks immediately before/after `chunk_index` in the
    same document — never an open-ended range, so an agent tool built on this
    can't be used to walk an entire filing.
    """
    chunks = db.scalars(
        select(DocumentChunk)
        .where(
            DocumentChunk.document_id == document_id,
            DocumentChunk.chunk_index.in_([chunk_index - 1, chunk_index + 1]),
        )
        .options(selectinload(DocumentChunk.document))
    ).all()
    before = next((c for c in chunks if c.chunk_index == chunk_index - 1), None)
    after = next((c for c in chunks if c.chunk_index == chunk_index + 1), None)
    return before, after

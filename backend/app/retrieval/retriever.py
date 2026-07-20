"""Query -> ranked, grounded source passages.

Embeds the query, runs semantic + full-text search in parallel candidate
lists, fuses them with RRF, then hydrates the fused top-k chunk ids into
`SourcePassage`s carrying their immediate neighbor chunks (same document,
chunk_index +/- 1) so a later grounding step has surrounding context without
a second round trip.
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime

from openai import OpenAI
from sqlalchemy import select, tuple_
from sqlalchemy.orm import Session, selectinload

from app.config import settings
from app.database.models import DocumentChunk
from app.retrieval.fusion import reciprocal_rank_fusion
from app.retrieval.queries import full_text_search, semantic_search

SEMANTIC_CANDIDATES = 20
FULL_TEXT_CANDIDATES = 20
DEFAULT_TOP_K = 8


@dataclass(frozen=True)
class SourcePassage:
    chunk_id: uuid.UUID
    document_id: uuid.UUID
    ticker: str
    company: str
    filing_type: str
    filing_date: datetime | None
    section_label: str | None
    page_label: str | None
    chunk_index: int
    text: str
    score: float
    context_before: str | None
    context_after: str | None


def embed_query(query: str) -> list[float]:
    client = OpenAI(api_key=settings.gemini_api_key, base_url=settings.gemini_base_url)
    response = client.embeddings.create(
        model=settings.gemini_embedding_model,
        input=[query],
        dimensions=settings.gemini_embedding_dimensions,
    )
    return response.data[0].embedding


def build_source_passage(
    chunk: DocumentChunk,
    score: float,
    context_before: str | None,
    context_after: str | None,
) -> SourcePassage:
    return SourcePassage(
        chunk_id=chunk.id,
        document_id=chunk.document_id,
        ticker=chunk.document.ticker,
        company=chunk.document.company,
        filing_type=chunk.document.filing_type,
        filing_date=chunk.document.filing_date,
        section_label=chunk.section_label,
        page_label=chunk.page_label,
        chunk_index=chunk.chunk_index,
        text=chunk.text,
        score=score,
        context_before=context_before,
        context_after=context_after,
    )


def retrieve(
    db: Session,
    query: str,
    top_k: int = DEFAULT_TOP_K,
    semantic_candidates: int = SEMANTIC_CANDIDATES,
    full_text_candidates: int = FULL_TEXT_CANDIDATES,
) -> list[SourcePassage]:
    query_embedding = embed_query(query)

    semantic_ranking = [
        chunk_id for chunk_id, _ in semantic_search(db, query_embedding, semantic_candidates)
    ]
    full_text_ranking = [
        chunk_id for chunk_id, _ in full_text_search(db, query, full_text_candidates)
    ]

    fused = reciprocal_rank_fusion([semantic_ranking, full_text_ranking])
    top_ids = [chunk_id for chunk_id, _ in fused[:top_k]]
    if not top_ids:
        return []
    scores_by_id = dict(fused)

    chunks = db.scalars(
        select(DocumentChunk)
        .where(DocumentChunk.id.in_(top_ids))
        .options(selectinload(DocumentChunk.document))
    ).all()
    chunks_by_id = {chunk.id: chunk for chunk in chunks}

    neighbor_keys = {
        (chunk.document_id, chunk.chunk_index + offset)
        for chunk in chunks
        for offset in (-1, 1)
    }
    neighbor_by_key: dict[tuple[uuid.UUID, int], DocumentChunk] = {}
    if neighbor_keys:
        neighbor_chunks = db.scalars(
            select(DocumentChunk).where(
                tuple_(DocumentChunk.document_id, DocumentChunk.chunk_index).in_(neighbor_keys)
            )
        ).all()
        neighbor_by_key = {
            (chunk.document_id, chunk.chunk_index): chunk for chunk in neighbor_chunks
        }

    passages = []
    for chunk_id in top_ids:
        chunk = chunks_by_id.get(chunk_id)
        if chunk is None:
            continue
        before = neighbor_by_key.get((chunk.document_id, chunk.chunk_index - 1))
        after = neighbor_by_key.get((chunk.document_id, chunk.chunk_index + 1))
        passages.append(
            build_source_passage(
                chunk,
                scores_by_id[chunk_id],
                before.text if before else None,
                after.text if after else None,
            )
        )
    return passages

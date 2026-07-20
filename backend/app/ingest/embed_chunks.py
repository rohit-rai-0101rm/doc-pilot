"""Embeds `document_chunks` rows where `embedding` is still NULL, via Gemini.

Safe to re-run: only picks up chunks that don't have an embedding yet.

Run from `backend/`: `uv run python -m app.ingest.embed_chunks`
"""
from __future__ import annotations

import time

from openai import OpenAI, RateLimitError
from sqlalchemy import select

from app.config import settings
from app.database.models import DocumentChunk
from app.database.session import SessionLocal

# Gemini's free tier has two separate limits: a per-request token budget
# (~20-49k tokens/request — 50 real-sized ~1000-token chunks 429s, 20 doesn't)
# and a flat 1000 embed-requests/day cap (EmbedContentRequestsPerDayPerUser...
# -FreeTier). Since the daily cap counts requests, not items, batch size should
# be as large as the token budget allows to conserve it.
BATCH_SIZE = 20
MAX_RETRIES = 5
INITIAL_BACKOFF_SECONDS = 15


def embed_chunks() -> None:
    client = OpenAI(api_key=settings.gemini_api_key, base_url=settings.gemini_base_url)

    with SessionLocal() as db:
        pending = db.scalars(
            select(DocumentChunk).where(DocumentChunk.embedding.is_(None))
        ).all()

        if not pending:
            print("No chunks pending embedding.")
            return

        print(f"Embedding {len(pending)} chunks...")

        for start in range(0, len(pending), BATCH_SIZE):
            batch = pending[start : start + BATCH_SIZE]

            backoff = INITIAL_BACKOFF_SECONDS
            for attempt in range(1, MAX_RETRIES + 1):
                try:
                    response = client.embeddings.create(
                        model=settings.gemini_embedding_model,
                        input=[chunk.text for chunk in batch],
                        dimensions=settings.gemini_embedding_dimensions,
                    )
                    break
                except RateLimitError:
                    if attempt == MAX_RETRIES:
                        raise
                    print(f"  Rate limited, retrying in {backoff}s (attempt {attempt}/{MAX_RETRIES})")
                    time.sleep(backoff)
                    backoff *= 2

            for chunk, embedding_data in zip(batch, response.data, strict=True):
                chunk.embedding = embedding_data.embedding
            db.commit()
            print(f"  Embedded {start + len(batch)}/{len(pending)}")

    print("Done.")


if __name__ == "__main__":
    embed_chunks()

"""Chunks each `source_documents` row and writes `document_chunks` (embedding left NULL).

Run a separate embed-existing-chunks pass afterward to fill in embeddings.

Run from `backend/`: `uv run python -m app.ingest.chunk_documents`
"""
from __future__ import annotations

from sqlalchemy import select

from app.database.models import DocumentChunk, SourceDocument
from app.database.session import SessionLocal
from app.ingest.chunking import chunk_markdown


def chunk_documents() -> None:
    with SessionLocal() as db:
        documents = db.scalars(select(SourceDocument)).all()

        chunked = 0
        skipped = 0

        for document in documents:
            existing = db.scalar(
                select(DocumentChunk).where(DocumentChunk.document_id == document.id)
            )
            if existing is not None:
                print(f"Already chunked: {document.ticker} {document.fiscal_year}")
                skipped += 1
                continue

            chunks = chunk_markdown(document.markdown_content)
            for index, chunk in enumerate(chunks):
                db.add(
                    DocumentChunk(
                        document_id=document.id,
                        chunk_index=index,
                        section_label=chunk.section_label,
                        text=chunk.text,
                        token_count=chunk.token_count,
                        metadata_={
                            "ticker": document.ticker,
                            "company": document.company,
                            "filing_type": document.filing_type,
                            "filing_date": (
                                document.filing_date.isoformat() if document.filing_date else None
                            ),
                            "year": document.fiscal_year,
                            "accession_number": document.accession_number,
                            "start_offset": chunk.start_offset,
                            "end_offset": chunk.end_offset,
                        },
                    )
                )
            db.commit()
            chunked += 1
            print(f"Chunked {document.ticker} {document.fiscal_year}: {len(chunks)} chunks")

        print(f"\nDone: {chunked} documents chunked, {skipped} already chunked")


if __name__ == "__main__":
    chunk_documents()

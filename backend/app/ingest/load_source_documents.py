"""Loads converted Markdown filings (from `data/convert_to_markdown.py`) into `source_documents`.

Reads `data/downloads/manifest.json`, finds the sibling `.md` file for each
filing, and inserts one `SourceDocument` row per filing keyed by
`accession_number` (already-loaded filings are skipped).

Run from `backend/`: `uv run python -m app.ingest.load_source_documents`
"""
from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

from sqlalchemy import select

from app.database.models import SourceDocument
from app.database.session import SessionLocal

DATA_DIR = Path(__file__).resolve().parents[3] / "data"
MANIFEST_PATH = DATA_DIR / "downloads" / "manifest.json"

COMPANY_NAMES = {
    "AAPL": "Apple Inc.",
    "MSFT": "Microsoft Corporation",
    "NVDA": "NVIDIA Corporation",
    "AMZN": "Amazon.com, Inc.",
    "GOOGL": "Alphabet Inc.",
}


def load_documents() -> None:
    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    downloads_dir = MANIFEST_PATH.parent

    loaded = 0
    skipped = 0
    missing_markdown = 0

    with SessionLocal() as db:
        for filing in manifest["filings"]:
            markdown_path = (downloads_dir / filing["local_path"]).with_suffix(".md")

            if not markdown_path.exists():
                print(f"Missing markdown for {filing['local_path']}, skipping")
                missing_markdown += 1
                continue

            existing = db.scalar(
                select(SourceDocument).where(
                    SourceDocument.accession_number == filing["accession_number"]
                )
            )
            if existing is not None:
                print(f"Already loaded: {filing['ticker']} {filing['accession_number']}")
                skipped += 1
                continue

            markdown_content = markdown_path.read_text(encoding="utf-8")
            filing_date = datetime.fromisoformat(filing["filing_date"]).replace(tzinfo=UTC)
            fiscal_year = int(filing["report_date"][:4])

            document = SourceDocument(
                ticker=filing["ticker"],
                company=COMPANY_NAMES[filing["ticker"]],
                filing_type=filing["form"],
                filing_date=filing_date,
                fiscal_year=fiscal_year,
                accession_number=filing["accession_number"],
                source_url=filing["source_url"],
                markdown_content=markdown_content,
                metadata_={
                    "report_date": filing["report_date"],
                    "primary_document": filing["primary_document"],
                },
            )
            db.add(document)
            db.commit()
            loaded += 1
            print(f"Loaded {filing['ticker']} {filing['report_date']} ({len(markdown_content)} chars)")

    print(f"\nDone: {loaded} loaded, {skipped} already present, {missing_markdown} missing markdown")


if __name__ == "__main__":
    load_documents()

import uuid
from datetime import UTC, datetime

from app.assistant.schemas import Citation, GroundedAnswer
from app.database.models import DocumentChunk, SourceDocument
from app.grounding.validator import (
    NO_VERIFIED_CITATIONS_REASON,
    NO_VERIFIED_CITATIONS_REFUSAL,
    validate_grounded_answer,
)
from app.retrieval.retriever import build_source_passage


def _passage(chunk_id: uuid.UUID | None = None):
    document = SourceDocument(
        id=uuid.uuid4(),
        ticker="AAPL",
        company="Apple Inc.",
        filing_type="10-K",
        filing_date=datetime(2024, 11, 1, tzinfo=UTC),
    )
    chunk = DocumentChunk(
        id=chunk_id or uuid.uuid4(),
        document_id=document.id,
        chunk_index=3,
        page_label="8",
        text="Some filing text.",
    )
    chunk.document = document
    return build_source_passage(chunk, score=0.9, context_before=None, context_after=None)


def test_verified_citation_survives_validation():
    passage = _passage()
    retrieved = {str(passage.chunk_id): passage}
    answer = GroundedAnswer(
        answer_markdown="Apple faces supply chain risk.",
        citations=[Citation(chunk_id=str(passage.chunk_id), quote="supply chain risk")],
    )

    validated = validate_grounded_answer(answer, retrieved)

    assert validated.refused is False
    assert validated.answer_markdown == answer.answer_markdown
    assert len(validated.citations) == 1
    assert validated.citations[0].chunk_id == str(passage.chunk_id)


def test_fabricated_citation_is_stripped_not_trusted():
    passage = _passage()
    retrieved = {str(passage.chunk_id): passage}
    fabricated_id = str(uuid.uuid4())
    answer = GroundedAnswer(
        answer_markdown="Apple faces supply chain risk and also cures cancer.",
        citations=[
            Citation(chunk_id=str(passage.chunk_id), quote="supply chain risk"),
            Citation(chunk_id=fabricated_id, quote="cures cancer"),
        ],
    )

    validated = validate_grounded_answer(answer, retrieved)

    assert validated.refused is False
    citation_ids = [c.chunk_id for c in validated.citations]
    assert str(passage.chunk_id) in citation_ids
    assert fabricated_id not in citation_ids


def test_answer_with_zero_verifiable_citations_forces_refusal():
    retrieved: dict = {}
    answer = GroundedAnswer(
        answer_markdown="Apple's revenue grew significantly.",
        citations=[Citation(chunk_id=str(uuid.uuid4()), quote="revenue grew")],
    )

    validated = validate_grounded_answer(answer, retrieved)

    assert validated.refused is True
    assert validated.citations == []
    assert validated.answer_markdown == NO_VERIFIED_CITATIONS_REFUSAL
    assert validated.refusal_reason == NO_VERIFIED_CITATIONS_REASON


def test_answer_with_no_citations_at_all_forces_refusal():
    answer = GroundedAnswer(answer_markdown="Apple's revenue grew significantly.", citations=[])

    validated = validate_grounded_answer(answer, {})

    assert validated.refused is True
    assert validated.answer_markdown == NO_VERIFIED_CITATIONS_REFUSAL


def test_explicit_refusal_passes_through_without_citations():
    answer = GroundedAnswer(
        answer_markdown="I can't help with stock predictions.",
        citations=[],
        refused=True,
        refusal_reason="Question asks for investment advice.",
    )

    validated = validate_grounded_answer(answer, {})

    assert validated.refused is True
    assert validated.answer_markdown == "I can't help with stock predictions."
    assert validated.refusal_reason == "Question asks for investment advice."
    assert validated.citations == []


def test_explicit_refusal_drops_any_citations_the_model_still_attached():
    passage = _passage()
    retrieved = {str(passage.chunk_id): passage}
    answer = GroundedAnswer(
        answer_markdown="I can't help with that.",
        citations=[Citation(chunk_id=str(passage.chunk_id), quote="irrelevant")],
        refused=True,
        refusal_reason="Out of scope.",
    )

    validated = validate_grounded_answer(answer, retrieved)

    assert validated.citations == []

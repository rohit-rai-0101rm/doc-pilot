"""Fails closed on ungrounded citations.

The model's structured output is trusted for *shape* (pydantic already
enforces that) but not for *truth* — nothing stops it from inventing a
plausible-looking chunk_id it never actually retrieved. This strips any
citation that doesn't correspond to a chunk the agent's tools actually
returned during the run, and if nothing verifiable survives, forces a
refusal rather than shipping unverifiable prose with real-looking citations.
"""
from __future__ import annotations

from app.assistant.schemas import GroundedAnswer
from app.retrieval.retriever import SourcePassage

NO_VERIFIED_CITATIONS_REFUSAL = (
    "I wasn't able to find supporting passages in the filings for this question, "
    "so I can't give a grounded answer."
)
NO_VERIFIED_CITATIONS_REASON = (
    "No citation in the model's answer referenced a chunk actually retrieved from the corpus."
)


def validate_grounded_answer(
    answer: GroundedAnswer, retrieved_chunks: dict[str, SourcePassage]
) -> GroundedAnswer:
    if answer.refused:
        return GroundedAnswer(
            answer_markdown=answer.answer_markdown,
            citations=[],
            refused=True,
            refusal_reason=answer.refusal_reason,
        )

    verified_citations = [
        citation for citation in answer.citations if citation.chunk_id in retrieved_chunks
    ]

    if not verified_citations:
        return GroundedAnswer(
            answer_markdown=NO_VERIFIED_CITATIONS_REFUSAL,
            citations=[],
            refused=True,
            refusal_reason=NO_VERIFIED_CITATIONS_REASON,
        )

    return GroundedAnswer(
        answer_markdown=answer.answer_markdown,
        citations=verified_citations,
        refused=False,
        refusal_reason=None,
    )

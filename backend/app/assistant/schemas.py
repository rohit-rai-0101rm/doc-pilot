from __future__ import annotations

from pydantic import BaseModel, Field


class Citation(BaseModel):
    chunk_id: str = Field(description="The exact chunk_id returned by a tool call.")
    quote: str = Field(description="A short verbatim excerpt from that chunk supporting the claim.")


class GroundedAnswer(BaseModel):
    answer_markdown: str = Field(description="The answer to the analyst's question, in markdown.")
    citations: list[Citation] = Field(default_factory=list)
    refused: bool = Field(
        default=False,
        description="True if the corpus doesn't support an answer, or the question falls outside the filings.",
    )
    refusal_reason: str | None = Field(
        default=None, description="Required when refused is true; why no grounded answer was possible."
    )

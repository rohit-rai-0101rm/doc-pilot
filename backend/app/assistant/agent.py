"""The grounded-answer agent: a PydanticAI agent whose only way to learn
anything about a company is through bounded, read-only retrieval tools —
never raw SQL. Every chunk a tool returns is recorded in `AssistantDeps`, so
`app.grounding.validator` can later verify the model didn't cite a chunk it
never actually saw.
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from pathlib import Path

from pydantic_ai import Agent, RunContext
from pydantic_ai.models.openai import OpenAIChatModel
from pydantic_ai.providers.openai import OpenAIProvider
from sqlalchemy.orm import Session

from app.assistant.schemas import GroundedAnswer
from app.config import settings
from app.database.models import DocumentChunk
from app.retrieval.queries import fetch_chunk_by_id, fetch_neighbor_chunks
from app.retrieval.retriever import SourcePassage, build_source_passage, retrieve

INSTRUCTIONS = (Path(__file__).parent / "instructions.md").read_text()


@dataclass
class AssistantDeps:
    db: Session
    retrieved_chunks: dict[str, SourcePassage] = field(default_factory=dict)


def _passage_dict(passage: SourcePassage) -> dict:
    return {
        "chunk_id": str(passage.chunk_id),
        "ticker": passage.ticker,
        "company": passage.company,
        "filing_type": passage.filing_type,
        "filing_date": passage.filing_date.date().isoformat() if passage.filing_date else None,
        "section": passage.section_label,
        "page": passage.page_label,
        "text": passage.text,
    }


def _remember(deps: AssistantDeps, chunk: DocumentChunk) -> SourcePassage:
    passage = build_source_passage(chunk, score=0.0, context_before=None, context_after=None)
    deps.retrieved_chunks[str(passage.chunk_id)] = passage
    return passage


_model = OpenAIChatModel(
    settings.gemini_chat_model,
    provider=OpenAIProvider(api_key=settings.gemini_api_key, base_url=settings.gemini_base_url),
)

agent = Agent(
    _model,
    deps_type=AssistantDeps,
    output_type=GroundedAnswer,
    instructions=INSTRUCTIONS,
)


@agent.tool
def search_filings(ctx: RunContext[AssistantDeps], query: str) -> list[dict]:
    """Search the SEC filing corpus for passages relevant to `query`. Returns
    ranked passages with their `chunk_id`, filing metadata, and full text.
    """
    passages = retrieve(ctx.deps.db, query)
    for passage in passages:
        ctx.deps.retrieved_chunks[str(passage.chunk_id)] = passage
    return [_passage_dict(passage) for passage in passages]


@agent.tool
def read_chunk(ctx: RunContext[AssistantDeps], chunk_id: str) -> dict | None:
    """Read one specific chunk's full text and metadata by its `chunk_id`."""
    try:
        parsed_id = uuid.UUID(chunk_id)
    except ValueError:
        return None

    chunk = fetch_chunk_by_id(ctx.deps.db, parsed_id)
    if chunk is None:
        return None
    return _passage_dict(_remember(ctx.deps, chunk))


@agent.tool
def read_surrounding_chunks(ctx: RunContext[AssistantDeps], chunk_id: str) -> dict:
    """Read the chunks immediately before and after `chunk_id` in the same
    filing, to confirm a passage's full context before citing it.
    """
    passage = ctx.deps.retrieved_chunks.get(chunk_id)
    if passage is None:
        try:
            parsed_id = uuid.UUID(chunk_id)
        except ValueError:
            return {"before": None, "after": None}
        chunk = fetch_chunk_by_id(ctx.deps.db, parsed_id)
        if chunk is None:
            return {"before": None, "after": None}
        passage = _remember(ctx.deps, chunk)

    before, after = fetch_neighbor_chunks(ctx.deps.db, passage.document_id, passage.chunk_index)
    return {
        "before": _passage_dict(_remember(ctx.deps, before)) if before else None,
        "after": _passage_dict(_remember(ctx.deps, after)) if after else None,
    }

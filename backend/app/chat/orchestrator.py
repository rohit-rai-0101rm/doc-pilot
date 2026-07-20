"""Retrieve -> agent -> validate. Streaming and persistence stay in the API
layer (app.api.chat) since they're transport/storage concerns, not
orchestration — this module's only job is producing a validated answer.
"""
from __future__ import annotations

from sqlalchemy.orm import Session

from app.assistant.agent import AssistantDeps, agent
from app.assistant.schemas import GroundedAnswer
from app.grounding.validator import validate_grounded_answer
from app.retrieval.retriever import SourcePassage


async def run_grounded_reply(
    db: Session, question: str
) -> tuple[GroundedAnswer, dict[str, SourcePassage]]:
    """Runs the assistant agent (which retrieves via its own tools) and
    returns a grounding-validated answer alongside every chunk it looked at,
    so the caller can resolve citation metadata (e.g. page_label) for
    persistence without a second DB round trip.
    """
    deps = AssistantDeps(db=db)
    result = await agent.run(question, deps=deps)
    validated = validate_grounded_answer(result.output, deps.retrieved_chunks)
    return validated, deps.retrieved_chunks

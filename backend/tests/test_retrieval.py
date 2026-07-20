import uuid
from datetime import UTC, datetime

from app.database.models import DocumentChunk, SourceDocument
from app.retrieval.fusion import reciprocal_rank_fusion
from app.retrieval.retriever import build_source_passage


def _uuids(n: int) -> list[uuid.UUID]:
    return [uuid.uuid4() for _ in range(n)]


def test_fusion_of_empty_rankings_returns_nothing():
    assert reciprocal_rank_fusion([]) == []
    assert reciprocal_rank_fusion([[], []]) == []


def test_fusion_preserves_order_of_a_single_ranking():
    ids = _uuids(3)

    fused = reciprocal_rank_fusion([ids])

    assert [doc_id for doc_id, _ in fused] == ids


def test_item_found_by_both_methods_outranks_an_item_found_by_only_one():
    shared, semantic_only, full_text_only = _uuids(3)
    # `shared` ranks second in each list; the other two each rank first in
    # exactly one list. Being found twice should still win over a single #1.
    semantic_ranking = [semantic_only, shared]
    full_text_ranking = [full_text_only, shared]

    fused = reciprocal_rank_fusion([semantic_ranking, full_text_ranking])

    assert fused[0][0] == shared


def test_fusion_score_matches_rrf_formula():
    doc_id = uuid.uuid4()
    other = uuid.uuid4()

    fused = reciprocal_rank_fusion([[doc_id, other], [other, doc_id]], k=60)
    scores = dict(fused)

    # doc_id: rank 1 in the first ranking, rank 2 in the second.
    assert scores[doc_id] == 1 / (60 + 1) + 1 / (60 + 2)
    # other: rank 2 in the first ranking, rank 1 in the second.
    assert scores[other] == 1 / (60 + 2) + 1 / (60 + 1)
    assert scores[doc_id] == scores[other]


def test_fusion_respects_custom_k():
    ids = _uuids(1)

    fused_default = dict(reciprocal_rank_fusion([ids]))
    fused_small_k = dict(reciprocal_rank_fusion([ids], k=1))

    # Smaller k makes rank differences matter more, i.e. inflates single-hit scores.
    assert fused_small_k[ids[0]] > fused_default[ids[0]]


def _make_chunk(**overrides) -> DocumentChunk:
    document = SourceDocument(
        id=uuid.uuid4(),
        ticker="AAPL",
        company="Apple Inc.",
        filing_type="10-K",
        filing_date=datetime(2024, 11, 1, tzinfo=UTC),
    )
    chunk = DocumentChunk(
        id=uuid.uuid4(),
        document_id=document.id,
        chunk_index=5,
        section_label="RISK FACTORS",
        page_label="12",
        text="The company faces risks related to supply chain concentration.",
    )
    chunk.document = document
    for key, value in overrides.items():
        setattr(chunk, key, value)
    return chunk


def test_build_source_passage_carries_document_and_chunk_fields():
    chunk = _make_chunk()

    passage = build_source_passage(chunk, score=0.75, context_before=None, context_after=None)

    assert passage.chunk_id == chunk.id
    assert passage.document_id == chunk.document_id
    assert passage.ticker == "AAPL"
    assert passage.company == "Apple Inc."
    assert passage.filing_type == "10-K"
    assert passage.section_label == "RISK FACTORS"
    assert passage.page_label == "12"
    assert passage.chunk_index == 5
    assert passage.text == chunk.text
    assert passage.score == 0.75


def test_build_source_passage_attaches_neighbor_context():
    chunk = _make_chunk()

    passage = build_source_passage(
        chunk,
        score=0.5,
        context_before="Previous chunk text.",
        context_after="Next chunk text.",
    )

    assert passage.context_before == "Previous chunk text."
    assert passage.context_after == "Next chunk text."


def test_build_source_passage_allows_missing_neighbors():
    chunk = _make_chunk()

    passage = build_source_passage(chunk, score=0.5, context_before=None, context_after=None)

    assert passage.context_before is None
    assert passage.context_after is None

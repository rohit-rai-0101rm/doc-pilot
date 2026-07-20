"""Splits a source document's Markdown into retrieval-sized chunks.

Paragraph-aware: splits on blank lines (so a markdown table or paragraph
never gets cut mid-block), then greedily packs paragraphs up to
`chunk_size_chars`, carrying the last paragraph forward into the next chunk
for context continuity across the boundary.
"""
from __future__ import annotations

from dataclasses import dataclass

CHUNK_SIZE_CHARS = 4000
OVERLAP_PARAGRAPHS = 1

# Rough token estimate (~4 chars/token for English) — good enough for sizing
# metadata; exact counts aren't needed until embedding.
_CHARS_PER_TOKEN = 4


@dataclass
class Chunk:
    text: str
    start_offset: int
    end_offset: int
    token_count: int
    section_label: str | None


def _is_heading(paragraph: str) -> bool:
    stripped = paragraph.strip()
    if not stripped or len(stripped) > 100:
        return False
    if stripped.startswith(("Item ", "PART ")):
        return True
    letters = [c for c in stripped if c.isalpha()]
    return bool(letters) and all(c.isupper() for c in letters)


def _split_paragraphs(markdown: str) -> list[tuple[str, int, int]]:
    paragraphs = []
    cursor = 0
    for block in markdown.split("\n\n"):
        start = markdown.index(block, cursor)
        end = start + len(block)
        cursor = end
        if block.strip():
            paragraphs.append((block, start, end))
    return paragraphs


def chunk_markdown(markdown: str, chunk_size_chars: int = CHUNK_SIZE_CHARS) -> list[Chunk]:
    paragraphs = _split_paragraphs(markdown)
    chunks: list[Chunk] = []

    # Each entry carries the heading in effect when that paragraph was appended,
    # so a chunk's label is well-defined even after overlap carries a paragraph
    # across a flush (a plain "current heading" variable would keep drifting
    # forward with it instead of describing where the chunk actually starts).
    window: list[tuple[str, int, int, str | None]] = []
    window_len = 0
    latest_heading: str | None = None

    def flush() -> None:
        if not window:
            return
        text = "\n\n".join(p[0] for p in window)
        chunks.append(
            Chunk(
                text=text,
                start_offset=window[0][1],
                end_offset=window[-1][2],
                token_count=max(1, len(text) // _CHARS_PER_TOKEN),
                section_label=window[0][3],
            )
        )

    for paragraph, start, end in paragraphs:
        if _is_heading(paragraph):
            latest_heading = paragraph.strip()

        para_len = len(paragraph)

        if window and window_len + para_len > chunk_size_chars:
            flush()
            window = window[-OVERLAP_PARAGRAPHS:] if OVERLAP_PARAGRAPHS else []
            window_len = sum(len(p[0]) for p in window)

        window.append((paragraph, start, end, latest_heading))
        window_len += para_len

    flush()
    return chunks

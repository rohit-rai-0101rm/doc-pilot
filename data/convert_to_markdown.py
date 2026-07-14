# /// script
# requires-python = ">=3.12"
# dependencies = ["docling==2.110.0"]
# ///
"""Converts downloaded SEC HTML filings to normalized Markdown using Docling.

Docs: https://docling-project.github.io/docling/
Run: `uv run data/convert_to_markdown.py` (after `uv run data/download.py`)
"""
from __future__ import annotations

import re
import time
from pathlib import Path

from docling.document_converter import DocumentConverter

# Params: edit these, then run `uv run data/convert_to_markdown.py`
INPUT_DIR = Path(__file__).resolve().parent / "downloads"
SOURCE_EXTENSIONS = (".htm", ".html")
OVERWRITE_EXISTING = False

# SEC filing HTML tables lean heavily on colspan/rowspan for layout. Docling's
# grid model repeats a spanned cell's text into every grid position it covers,
# which turns into markdown tables with the same label or value duplicated
# across several adjacent columns (plus columns that are blank end to end —
# pure visual spacing in the original filing). Both are noise for retrieval:
# they waste tokens and dilute embeddings without adding information, so we
# collapse them before writing the file.
_TABLE_ROW_RE = re.compile(r"^\s*\|.*\|\s*$")
_SEPARATOR_CELL_RE = re.compile(r"^:?-+:?$")


def _split_row(line: str) -> list[str]:
    stripped = line.strip()
    if stripped.startswith("|"):
        stripped = stripped[1:]
    if stripped.endswith("|"):
        stripped = stripped[:-1]
    return [cell.strip() for cell in stripped.split("|")]


def _is_separator_row(cells: list[str]) -> bool:
    return bool(cells) and all(_SEPARATOR_CELL_RE.match(cell) for cell in cells)


def _clean_table_block(lines: list[str]) -> list[str]:
    rows = [_split_row(line) for line in lines]
    separator_idx = next((i for i, row in enumerate(rows) if _is_separator_row(row)), None)
    content_rows = [row for i, row in enumerate(rows) if i != separator_idx]

    if not content_rows:
        return lines

    num_cols = max(len(row) for row in content_rows)
    padded_rows = [row + [""] * (num_cols - len(row)) for row in content_rows]

    # Drop columns that are blank in every row of this table (pure spacing).
    keep_cols = [any(row[c].strip() for row in padded_rows) for c in range(num_cols)]
    pruned_rows = [[cell for c, cell in enumerate(row) if keep_cols[c]] for row in padded_rows]

    # Collapse runs of consecutive identical cells within a row (spanned-cell duplication).
    collapsed_rows = []
    for row in pruned_rows:
        collapsed: list[str] = []
        for cell in row:
            if collapsed and collapsed[-1] == cell:
                continue
            collapsed.append(cell)
        collapsed_rows.append(collapsed)

    if not collapsed_rows or not collapsed_rows[0]:
        return []

    output_lines = ["| " + " | ".join(collapsed_rows[0]) + " |"]
    output_lines.append("| " + " | ".join(["---"] * len(collapsed_rows[0])) + " |")
    for row in collapsed_rows[1:]:
        if row:
            output_lines.append("| " + " | ".join(row) + " |")
    return output_lines


def clean_markdown_tables(markdown: str) -> str:
    lines = markdown.split("\n")
    output: list[str] = []
    i = 0
    while i < len(lines):
        if _TABLE_ROW_RE.match(lines[i]):
            start = i
            while i < len(lines) and _TABLE_ROW_RE.match(lines[i]):
                i += 1
            output.extend(_clean_table_block(lines[start:i]))
        else:
            output.append(lines[i])
            i += 1
    return "\n".join(output)


def convert_filings() -> None:
    source_paths = sorted(
        path
        for path in INPUT_DIR.rglob("*")
        if path.suffix.lower() in SOURCE_EXTENSIONS
    )

    if not source_paths:
        print(f"No {SOURCE_EXTENSIONS} files found under {INPUT_DIR}")
        return

    converter = DocumentConverter()
    converted = 0
    skipped = 0
    failed = 0

    for source_path in source_paths:
        markdown_path = source_path.with_suffix(".md")

        if markdown_path.exists() and not OVERWRITE_EXISTING:
            print(f"Skipping (already converted): {source_path.name}")
            skipped += 1
            continue

        print(f"Converting: {source_path.name}")
        start = time.monotonic()
        try:
            result = converter.convert(source_path)
            markdown = clean_markdown_tables(result.document.export_to_markdown())
        except Exception as exc:  # noqa: BLE001 — one bad filing shouldn't abort the batch
            print(f"  FAILED ({exc})")
            failed += 1
            continue

        markdown_path.write_text(markdown, encoding="utf-8")
        elapsed = time.monotonic() - start
        print(f"  Wrote {markdown_path.name} ({elapsed:.1f}s)")
        converted += 1

    print(
        f"\nDone: {converted} converted, {skipped} skipped, {failed} failed "
        f"(of {len(source_paths)} total)"
    )


if __name__ == "__main__":
    convert_filings()

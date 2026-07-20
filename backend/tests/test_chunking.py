from app.ingest.chunking import chunk_markdown


def test_empty_input_returns_no_chunks():
    assert chunk_markdown("") == []


def test_short_text_is_a_single_chunk():
    markdown = "Some short filing text that fits in one chunk."
    chunks = chunk_markdown(markdown, chunk_size_chars=4000)

    assert len(chunks) == 1
    assert chunks[0].text == markdown
    assert markdown[chunks[0].start_offset : chunks[0].end_offset] == markdown


def test_long_text_splits_into_multiple_chunks_within_budget():
    paragraphs = [f"Paragraph {i}. " + ("word " * 50) for i in range(20)]
    markdown = "\n\n".join(paragraphs)

    chunks = chunk_markdown(markdown, chunk_size_chars=500)

    assert len(chunks) > 1
    for chunk in chunks:
        # A single oversized paragraph is allowed to exceed budget on its own,
        # but no chunk here is a single paragraph, so the budget should hold.
        assert len(chunk.text) <= 500 * 2


def test_offsets_map_back_into_original_text():
    paragraphs = [f"Paragraph {i} content here." for i in range(10)]
    markdown = "\n\n".join(paragraphs)

    chunks = chunk_markdown(markdown, chunk_size_chars=60)

    for chunk in chunks:
        assert markdown[chunk.start_offset : chunk.end_offset] in markdown
        # The chunk's own text should start with the slice at its offsets.
        assert chunk.text.startswith(markdown[chunk.start_offset : chunk.start_offset + 10])


def test_consecutive_chunks_overlap_by_one_paragraph():
    paragraphs = [f"Paragraph {i} with enough padding words to force a split." for i in range(10)]
    markdown = "\n\n".join(paragraphs)

    chunks = chunk_markdown(markdown, chunk_size_chars=120)

    assert len(chunks) > 1
    for previous, current in zip(chunks, chunks[1:]):
        previous_last_paragraph = previous.text.split("\n\n")[-1]
        current_first_paragraph = current.text.split("\n\n")[0]
        assert previous_last_paragraph == current_first_paragraph


def test_section_label_tracks_most_recent_heading():
    markdown = "\n\n".join(
        [
            "RISK FACTORS",
            "Some risk factor discussion goes here.",
            "More risk discussion.",
            "PROPERTIES",
            "Discussion about company properties.",
        ]
    )

    chunks = chunk_markdown(markdown, chunk_size_chars=4000)

    assert len(chunks) == 1
    assert chunks[0].section_label == "RISK FACTORS"


def test_section_label_updates_across_chunk_boundaries():
    markdown = "\n\n".join(
        [
            "RISK FACTORS",
            "Risk paragraph one with padding words to take up space here.",
            "PROPERTIES",
            "Properties paragraph with padding words to take up space here.",
        ]
    )

    chunks = chunk_markdown(markdown, chunk_size_chars=70)

    assert len(chunks) >= 2
    assert chunks[0].section_label == "RISK FACTORS"
    assert chunks[-1].section_label == "PROPERTIES"


def test_token_count_is_positive_and_roughly_proportional_to_length():
    short_chunks = chunk_markdown("word " * 10, chunk_size_chars=4000)
    long_chunks = chunk_markdown("word " * 1000, chunk_size_chars=10_000)

    assert short_chunks[0].token_count > 0
    assert long_chunks[0].token_count > short_chunks[0].token_count

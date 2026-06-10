from rag_pdfs import ChunkConfig, compare_strategies, elements_from_text_pages
from rag_pdfs.chunking import inline_captions_chunks, separate_caption_chunks


SAMPLE_PAGES = [
    """
1 Introduction
PDF RAG needs to preserve visual evidence and nearby prose.
Figure 1. Caption-aware chunk flow for inline and separate caption indexes.
The body text explains how captions should influence retrieval.
Table 1. Chunk strategy comparison.
The table summarizes coverage and chunk count.
""",
    """
2 Method
Separate caption chunks make figures searchable even when the body text is long.
Inline caption chunks keep the caption near the explanation.
""",
]


def test_elements_from_text_pages_classifies_captions_and_headings() -> None:
    elements = elements_from_text_pages(SAMPLE_PAGES, source="sample")

    assert elements[0].kind == "heading"
    assert [element.kind for element in elements].count("caption") == 2
    assert elements[-1].page == 2


def test_inline_captions_keep_captions_inside_body_stream() -> None:
    elements = elements_from_text_pages(SAMPLE_PAGES)
    chunks = inline_captions_chunks(elements, ChunkConfig(chunk_size=260, chunk_overlap=0))

    assert any("[Caption] Figure 1." in chunk.text for chunk in chunks)
    assert any(chunk.metadata["captions"] for chunk in chunks)


def test_separate_caption_chunks_create_dedicated_caption_chunks() -> None:
    elements = elements_from_text_pages(SAMPLE_PAGES)
    chunks = separate_caption_chunks(elements, ChunkConfig(chunk_size=260, chunk_overlap=0))
    caption_chunks = [chunk for chunk in chunks if chunk.kind == "caption"]

    assert len(caption_chunks) == 2
    assert "Caption:" in caption_chunks[0].text
    assert "Context before:" in caption_chunks[0].text
    assert "Context after:" in caption_chunks[0].text


def test_compare_strategies_reports_caption_coverage() -> None:
    elements = elements_from_text_pages(SAMPLE_PAGES)
    result = compare_strategies(
        elements,
        queries=["caption-aware chunk flow"],
        strategy_names=["inline_captions_chunks", "separate_caption_chunks", "page_chunks"],
        config=ChunkConfig(chunk_size=260, chunk_overlap=0),
    )

    summaries = {summary.strategy: summary for summary in result.summaries}
    assert summaries["inline_captions_chunks"].caption_coverage == 1.0
    assert summaries["separate_caption_chunks"].caption_chunks == 2
    assert result.queries[0].hits

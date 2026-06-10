# rag_pdfs

Experimental PDF RAG pipeline for comparing caption-aware chunking strategies.

This subproject extends the repository's `strata.md` principle from media transcripts to PDFs:

```text
recover source text and structure
  -> preserve figure/table captions
  -> chunk with traceable page metadata
  -> compare retrieval behavior
  -> export chunks for LangChain/vector indexes
```

## Main Strategies

- `inline_captions_chunks`: keeps figure/table captions inside the nearby body text stream. This is useful when the answer needs both the visual caption and the surrounding explanation.
- `separate_caption_chunks`: removes captions from body chunks and creates dedicated caption chunks with nearby context. This is useful when figure/table captions are high-signal retrieval targets.

## Baselines

- `page_chunks`: one chunk per page.
- `section_chunks`: groups text under detected headings.
- `recursive_text_chunks`: simple LangChain-style recursive character splitting.

## Run

Install the optional PDF/LangChain dependencies when you need to read PDFs or build LangChain retrievers:

```bash
uv sync --extra pdf-rag --extra dev
```

Run the comparison:

```bash
uv run pdf-rag-experiment paper.pdf \
  --query "What does Figure 2 show?" \
  --query "main limitation" \
  --output-dir outputs/rag_pdfs
```

Outputs:

- `<stem>.comparison.json`: complete metrics, retrieval smoke results, and chunks.
- `<stem>.comparison.md`: compact human-readable report.
- `<stem>.<strategy>.jsonl`: chunks for each strategy.

## LangChain Adapter

The chunkers are plain Python so experiments can run without a vector database. To pass chunks into LangChain:

```python
from rag_pdfs import elements_from_text_pages, inline_captions_chunks
from rag_pdfs.langchain_pipeline import to_langchain_documents

elements = elements_from_text_pages(["Figure 1. Model layout\nThe model has two towers."])
chunks = inline_captions_chunks(elements)
documents = to_langchain_documents(chunks)
```

`build_faiss_retriever(chunks, embeddings)` is available when `langchain-community` and `faiss-cpu` are installed.

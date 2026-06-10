from __future__ import annotations

from collections.abc import Iterable

from .models import PdfChunk


def to_langchain_documents(chunks: Iterable[PdfChunk]):
    """Convert project chunks to LangChain Document objects."""

    try:
        from langchain_core.documents import Document
    except ImportError as exc:
        raise RuntimeError("Install the pdf-rag extra to use LangChain adapters: uv sync --extra pdf-rag") from exc

    return [
        Document(
            page_content=chunk.text,
            metadata={
                "chunk_id": chunk.id,
                "strategy": chunk.strategy,
                "page_start": chunk.page_start,
                "page_end": chunk.page_end,
                "kind": chunk.kind,
                **chunk.metadata,
            },
        )
        for chunk in chunks
    ]


def build_faiss_retriever(chunks: Iterable[PdfChunk], embeddings, search_kwargs: dict | None = None):
    """Build a FAISS retriever from chunks using a caller-provided LangChain embeddings object."""

    try:
        from langchain_community.vectorstores import FAISS
    except ImportError as exc:
        raise RuntimeError("Install langchain-community and faiss-cpu to build a FAISS retriever") from exc

    documents = to_langchain_documents(chunks)
    vectorstore = FAISS.from_documents(documents, embeddings)
    return vectorstore.as_retriever(search_kwargs=search_kwargs or {"k": 4})

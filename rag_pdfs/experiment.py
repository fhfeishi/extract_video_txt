from __future__ import annotations

from collections import Counter
from pathlib import Path
import json
import math
import re

from .chunking import ChunkConfig, STRATEGIES, chunk_by_strategy
from .models import ExperimentResult, PdfChunk, PdfElement, QueryResult, RetrievalHit, StrategySummary


DEFAULT_STRATEGIES = [
    "inline_captions_chunks",
    "separate_caption_chunks",
    "page_chunks",
    "section_chunks",
    "recursive_text_chunks",
]


def compare_strategies(
    elements: list[PdfElement],
    queries: list[str],
    config: ChunkConfig | None = None,
    strategy_names: list[str] | None = None,
    top_k: int = 3,
) -> ExperimentResult:
    config = config or ChunkConfig()
    strategy_names = strategy_names or DEFAULT_STRATEGIES
    chunks_by_strategy = chunk_by_strategy(elements, strategy_names, config)
    summaries = [_summarize_strategy(name, chunks, elements) for name, chunks in chunks_by_strategy.items()]
    query_results = [_search_all(query, chunks_by_strategy, top_k=top_k) for query in queries]
    return ExperimentResult(summaries=summaries, queries=query_results, chunks=chunks_by_strategy)


def write_experiment_outputs(result: ExperimentResult, output_dir: Path | str, stem: str) -> None:
    out_dir = Path(output_dir).expanduser().resolve()
    out_dir.mkdir(parents=True, exist_ok=True)

    (out_dir / f"{stem}.comparison.json").write_text(
        result.model_dump_json(indent=2),
        encoding="utf-8",
    )
    (out_dir / f"{stem}.comparison.md").write_text(render_markdown_report(result), encoding="utf-8")
    for strategy, chunks in result.chunks.items():
        lines = [json.dumps(chunk.model_dump(), ensure_ascii=False) for chunk in chunks]
        (out_dir / f"{stem}.{strategy}.jsonl").write_text("\n".join(lines) + "\n", encoding="utf-8")


def render_markdown_report(result: ExperimentResult) -> str:
    lines = ["# PDF RAG Chunk Experiment", ""]
    lines.append("| strategy | chunks | avg chars | caption chunks | chunks with captions | caption coverage |")
    lines.append("| --- | ---: | ---: | ---: | ---: | ---: |")
    for summary in result.summaries:
        lines.append(
            f"| {summary.strategy} | {summary.num_chunks} | {summary.avg_chars:.1f} | "
            f"{summary.caption_chunks} | {summary.chunks_with_captions} | {summary.caption_coverage:.2f} |"
        )
    if result.queries:
        lines.extend(["", "## Retrieval Smoke Results", ""])
    for query_result in result.queries:
        lines.append(f"### {query_result.query}")
        lines.append("")
        for hit in query_result.hits:
            lines.append(
                f"- `{hit.strategy}` `{hit.chunk_id}` score={hit.score:.3f} "
                f"pages={hit.page_start}-{hit.page_end}: {hit.preview}"
            )
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def available_strategies() -> list[str]:
    return sorted(STRATEGIES)


def _summarize_strategy(strategy: str, chunks: list[PdfChunk], elements: list[PdfElement]) -> StrategySummary:
    lengths = [len(chunk.text) for chunk in chunks]
    total_captions = sum(1 for element in elements if element.kind == "caption")
    covered_captions = {
        caption
        for chunk in chunks
        for caption in chunk.metadata.get("captions", [])
        if isinstance(caption, str)
    }
    chunks_with_captions = sum(1 for chunk in chunks if chunk.metadata.get("captions"))
    caption_chunks = sum(1 for chunk in chunks if chunk.kind == "caption")
    return StrategySummary(
        strategy=strategy,
        num_chunks=len(chunks),
        avg_chars=(sum(lengths) / len(lengths)) if lengths else 0.0,
        min_chars=min(lengths) if lengths else 0,
        max_chars=max(lengths) if lengths else 0,
        caption_chunks=caption_chunks,
        chunks_with_captions=chunks_with_captions,
        caption_coverage=(len(covered_captions) / total_captions) if total_captions else 1.0,
    )


def _search_all(query: str, chunks_by_strategy: dict[str, list[PdfChunk]], top_k: int) -> QueryResult:
    hits: list[RetrievalHit] = []
    for strategy, chunks in chunks_by_strategy.items():
        for chunk, score in _rank_chunks(query, chunks)[:top_k]:
            hits.append(
                RetrievalHit(
                    chunk_id=chunk.id,
                    strategy=strategy,
                    score=score,
                    page_start=chunk.page_start,
                    page_end=chunk.page_end,
                    kind=chunk.kind,
                    preview=_preview(chunk.text),
                )
            )
    hits.sort(key=lambda hit: (-hit.score, hit.strategy, hit.chunk_id))
    return QueryResult(query=query, hits=hits[: max(top_k, top_k * len(chunks_by_strategy))])


def _rank_chunks(query: str, chunks: list[PdfChunk]) -> list[tuple[PdfChunk, float]]:
    query_terms = _tokenize(query)
    if not query_terms:
        return []
    document_frequencies = Counter()
    chunk_term_counts: list[Counter[str]] = []
    for chunk in chunks:
        counts = Counter(_tokenize(chunk.text))
        chunk_term_counts.append(counts)
        document_frequencies.update(counts.keys())
    total_docs = max(1, len(chunks))

    scored: list[tuple[PdfChunk, float]] = []
    for chunk, counts in zip(chunks, chunk_term_counts, strict=True):
        score = 0.0
        for term in query_terms:
            if term not in counts:
                continue
            idf = math.log((1 + total_docs) / (1 + document_frequencies[term])) + 1.0
            score += (1.0 + math.log(counts[term])) * idf
        if score > 0:
            scored.append((chunk, score / math.sqrt(max(1, sum(counts.values())))))
    scored.sort(key=lambda item: item[1], reverse=True)
    return scored


def _tokenize(text: str) -> list[str]:
    return re.findall(r"[a-z0-9_]+|[\u4e00-\u9fff]", text.lower())


def _preview(text: str, limit: int = 180) -> str:
    value = " ".join(text.split())
    return value if len(value) <= limit else value[: limit - 3] + "..."

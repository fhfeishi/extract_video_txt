from __future__ import annotations

import argparse
from pathlib import Path

from .chunking import ChunkConfig
from .experiment import DEFAULT_STRATEGIES, available_strategies, compare_strategies, write_experiment_outputs
from .extract import load_pdf_elements


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run PDF RAG chunking experiments.")
    parser.add_argument("pdf", type=Path, help="PDF file to extract and chunk.")
    parser.add_argument("--output-dir", type=Path, default=Path("outputs/rag_pdfs"))
    parser.add_argument("--stem", default=None, help="Output file stem. Defaults to the PDF stem.")
    parser.add_argument(
        "--strategies",
        default=",".join(DEFAULT_STRATEGIES),
        help=f"Comma-separated strategies. Available: {', '.join(available_strategies())}",
    )
    parser.add_argument("--query", action="append", default=[], help="Retrieval smoke-test query. Repeatable.")
    parser.add_argument("--queries-file", type=Path, default=None, help="One retrieval query per line.")
    parser.add_argument("--chunk-size", type=int, default=1000)
    parser.add_argument("--chunk-overlap", type=int, default=120)
    parser.add_argument("--caption-context-chars", type=int, default=260)
    parser.add_argument("--top-k", type=int, default=3)
    return parser


def main(argv: list[str] | None = None) -> None:
    parser = build_parser()
    args = parser.parse_args(argv)

    queries = list(args.query)
    if args.queries_file:
        queries.extend(
            line.strip()
            for line in args.queries_file.read_text(encoding="utf-8").splitlines()
            if line.strip()
        )

    config = ChunkConfig(
        chunk_size=args.chunk_size,
        chunk_overlap=args.chunk_overlap,
        caption_context_chars=args.caption_context_chars,
    )
    strategies = [item.strip() for item in args.strategies.split(",") if item.strip()]
    elements = load_pdf_elements(args.pdf)
    result = compare_strategies(
        elements=elements,
        queries=queries,
        config=config,
        strategy_names=strategies,
        top_k=args.top_k,
    )
    stem = args.stem or args.pdf.stem
    write_experiment_outputs(result, args.output_dir, stem)

    print(f"Loaded {len(elements)} PDF text elements.")
    print(f"Wrote PDF RAG experiment outputs to {args.output_dir.resolve()}")


if __name__ == "__main__":
    main()

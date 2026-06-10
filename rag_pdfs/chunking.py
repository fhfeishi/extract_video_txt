from __future__ import annotations

from collections.abc import Callable, Iterable
from pydantic import BaseModel, ConfigDict, Field
import re

from .models import PdfChunk, PdfElement


class ChunkConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    chunk_size: int = Field(default=1000, ge=200)
    chunk_overlap: int = Field(default=120, ge=0)
    caption_context_chars: int = Field(default=260, ge=0)
    min_chunk_chars: int = Field(default=80, ge=0)


Chunker = Callable[[list[PdfElement], ChunkConfig], list[PdfChunk]]
STRATEGIES: dict[str, Chunker] = {}


def strategy(name: str) -> Callable[[Chunker], Chunker]:
    def decorator(func: Chunker) -> Chunker:
        STRATEGIES[name] = func
        return func

    return decorator


@strategy("inline_captions_chunks")
def inline_captions_chunks(elements: list[PdfElement], config: ChunkConfig | None = None) -> list[PdfChunk]:
    """Keep captions in the same text stream as nearby body paragraphs."""

    config = config or ChunkConfig()
    blocks: list[Block] = []
    captions: list[str] = []
    pages: list[int] = []

    for element in elements:
        text = _format_element_inline(element)
        blocks.append(Block(text=text, page=element.page, captions=[element.text] if element.kind == "caption" else []))
        pages.append(element.page)
        if element.kind == "caption":
            captions.append(element.text)

    return _chunks_from_blocks(
        "inline_captions_chunks",
        blocks,
        config,
        default_kind="mixed" if captions else "body",
    )


@strategy("separate_caption_chunks")
def separate_caption_chunks(elements: list[PdfElement], config: ChunkConfig | None = None) -> list[PdfChunk]:
    """Index body text and captions separately, with small context windows around captions."""

    config = config or ChunkConfig()
    body_elements = [element for element in elements if element.kind != "caption"]
    body_blocks = [
        Block(text=_format_element_inline(element), page=element.page, captions=[])
        for element in body_elements
    ]
    chunks = _chunks_from_blocks("separate_caption_chunks", body_blocks, config, default_kind="body")

    caption_elements = [element for element in elements if element.kind == "caption"]
    for caption_index, element in enumerate(caption_elements, start=1):
        before = _nearby_text(elements, element.order, direction=-1, limit=config.caption_context_chars)
        after = _nearby_text(elements, element.order, direction=1, limit=config.caption_context_chars)
        text_parts = [f"Caption: {element.text}"]
        if before:
            text_parts.append(f"Context before: {before}")
        if after:
            text_parts.append(f"Context after: {after}")
        chunks.append(
            PdfChunk(
                id=f"separate_caption_chunks-caption-{caption_index:04d}",
                strategy="separate_caption_chunks",
                text="\n\n".join(text_parts),
                page_start=element.page,
                page_end=element.page,
                kind="caption",
                metadata={
                    "caption_text": element.text,
                    "captions": [element.text],
                    "context_before": before,
                    "context_after": after,
                },
            )
        )
    return chunks


@strategy("page_chunks")
def page_chunks(elements: list[PdfElement], config: ChunkConfig | None = None) -> list[PdfChunk]:
    """Baseline: one chunk per PDF page, captions inline."""

    pages: dict[int, list[PdfElement]] = {}
    for element in elements:
        pages.setdefault(element.page, []).append(element)

    chunks: list[PdfChunk] = []
    for index, (page, page_elements) in enumerate(sorted(pages.items()), start=1):
        captions = [element.text for element in page_elements if element.kind == "caption"]
        text = "\n".join(_format_element_inline(element) for element in page_elements)
        chunks.append(
            PdfChunk(
                id=f"page_chunks-{index:04d}",
                strategy="page_chunks",
                text=text,
                page_start=page,
                page_end=page,
                kind="page",
                metadata={"captions": captions},
            )
        )
    return chunks


@strategy("section_chunks")
def section_chunks(elements: list[PdfElement], config: ChunkConfig | None = None) -> list[PdfChunk]:
    """Heading-aware baseline: group content under detected headings."""

    config = config or ChunkConfig()
    blocks: list[Block] = []
    current: list[PdfElement] = []

    for element in elements:
        if element.kind == "heading" and current:
            blocks.append(_section_block(current))
            current = [element]
        else:
            current.append(element)
    if current:
        blocks.append(_section_block(current))

    return _chunks_from_blocks("section_chunks", blocks, config, default_kind="section")


@strategy("recursive_text_chunks")
def recursive_text_chunks(elements: list[PdfElement], config: ChunkConfig | None = None) -> list[PdfChunk]:
    """LangChain-style recursive character splitter baseline."""

    config = config or ChunkConfig()
    text = "\n\n".join(_format_element_inline(element) for element in elements)
    pages = [element.page for element in elements] or [1]
    split_texts = _recursive_split(text, config.chunk_size, config.chunk_overlap)
    chunks: list[PdfChunk] = []
    for index, chunk_text in enumerate(split_texts, start=1):
        chunks.append(
            PdfChunk(
                id=f"recursive_text_chunks-{index:04d}",
                strategy="recursive_text_chunks",
                text=chunk_text,
                page_start=min(pages),
                page_end=max(pages),
                kind="mixed",
                metadata={"captions": _captions_in_text(elements, chunk_text)},
            )
        )
    return chunks


def chunk_by_strategy(
    elements: list[PdfElement],
    strategy_names: Iterable[str],
    config: ChunkConfig | None = None,
) -> dict[str, list[PdfChunk]]:
    config = config or ChunkConfig()
    result: dict[str, list[PdfChunk]] = {}
    for name in strategy_names:
        try:
            chunker = STRATEGIES[name]
        except KeyError as exc:
            allowed = ", ".join(sorted(STRATEGIES))
            raise ValueError(f"Unknown chunk strategy {name!r}. Allowed: {allowed}") from exc
        result[name] = chunker(elements, config)
    return result


class Block(BaseModel):
    model_config = ConfigDict(extra="forbid")

    text: str
    page: int
    captions: list[str] = Field(default_factory=list)


def _chunks_from_blocks(
    strategy_name: str,
    blocks: list[Block],
    config: ChunkConfig,
    default_kind: str,
) -> list[PdfChunk]:
    chunks: list[PdfChunk] = []
    current_texts: list[str] = []
    current_pages: list[int] = []
    current_captions: list[str] = []

    def flush() -> None:
        if not current_texts:
            return
        text = "\n\n".join(current_texts).strip()
        if len(text) < config.min_chunk_chars and chunks:
            previous = chunks[-1]
            previous.text = f"{previous.text}\n\n{text}".strip()
            previous.page_end = max(previous.page_end, max(current_pages))
            previous.metadata["captions"] = list(previous.metadata.get("captions", [])) + current_captions
        else:
            index = len(chunks) + 1
            chunks.append(
                PdfChunk(
                    id=f"{strategy_name}-{index:04d}",
                    strategy=strategy_name,
                    text=text,
                    page_start=min(current_pages),
                    page_end=max(current_pages),
                    kind=default_kind,  # type: ignore[arg-type]
                    metadata={"captions": list(current_captions)},
                )
            )
        current_texts.clear()
        current_pages.clear()
        current_captions.clear()

    for block in blocks:
        pieces = _split_oversized_text(block.text, config.chunk_size, config.chunk_overlap)
        for piece in pieces:
            projected_len = len("\n\n".join([*current_texts, piece]))
            if current_texts and projected_len > config.chunk_size:
                flush()
                if chunks and config.chunk_overlap:
                    overlap = _tail(chunks[-1].text, config.chunk_overlap)
                    if overlap:
                        current_texts.append(overlap)
                        current_pages.append(block.page)
            current_texts.append(piece)
            current_pages.append(block.page)
            current_captions.extend(block.captions)
    flush()
    return chunks


def _split_oversized_text(text: str, chunk_size: int, overlap: int) -> list[str]:
    if len(text) <= chunk_size:
        return [text]
    return _recursive_split(text, chunk_size, overlap)


def _recursive_split(text: str, chunk_size: int, overlap: int) -> list[str]:
    separators = ["\n\n", "\n", "。", ".", "；", ";", "，", ",", " "]
    pieces = [text.strip()]
    for separator in separators:
        next_pieces: list[str] = []
        changed = False
        for piece in pieces:
            if len(piece) <= chunk_size:
                next_pieces.append(piece)
                continue
            parts = [part.strip() for part in piece.split(separator) if part.strip()]
            if len(parts) <= 1:
                next_pieces.append(piece)
            else:
                changed = True
                next_pieces.extend(_pack_parts(parts, separator, chunk_size))
        pieces = next_pieces
        if all(len(piece) <= chunk_size for piece in pieces) and changed:
            break

    output: list[str] = []
    for piece in pieces:
        if len(piece) <= chunk_size:
            output.append(piece)
            continue
        step = max(1, chunk_size - overlap)
        output.extend(piece[index : index + chunk_size].strip() for index in range(0, len(piece), step))
    return [piece for piece in output if piece]


def _pack_parts(parts: list[str], separator: str, chunk_size: int) -> list[str]:
    packed: list[str] = []
    current = ""
    joiner = separator if separator.strip() else " "
    for part in parts:
        candidate = part if not current else f"{current}{joiner}{part}"
        if current and len(candidate) > chunk_size:
            packed.append(current)
            current = part
        else:
            current = candidate
    if current:
        packed.append(current)
    return packed


def _tail(text: str, chars: int) -> str:
    return text[-chars:].strip()


def _format_element_inline(element: PdfElement) -> str:
    if element.kind == "caption":
        return f"[Caption] {element.text}"
    if element.kind == "heading":
        return f"# {element.text}"
    return element.text


def _nearby_text(elements: list[PdfElement], order: int, direction: int, limit: int) -> str:
    selected: list[str] = []
    iterable = reversed(elements[:order]) if direction < 0 else elements[order + 1 :]
    total = 0
    for element in iterable:
        if element.kind == "caption":
            continue
        text = element.text
        if not text:
            continue
        selected.append(text)
        total += len(text)
        if total >= limit:
            break
    if direction < 0:
        selected.reverse()
    joined = " ".join(selected)
    if len(joined) > limit:
        return joined[-limit:] if direction < 0 else joined[:limit]
    return joined


def _section_block(elements: list[PdfElement]) -> Block:
    captions = [element.text for element in elements if element.kind == "caption"]
    return Block(
        text="\n".join(_format_element_inline(element) for element in elements),
        page=elements[0].page,
        captions=captions,
    )


def _captions_in_text(elements: list[PdfElement], text: str) -> list[str]:
    captions = []
    for element in elements:
        if element.kind == "caption" and element.text in text:
            captions.append(element.text)
    return captions

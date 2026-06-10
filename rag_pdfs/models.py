from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


ElementKind = Literal["body", "caption", "heading"]
ChunkKind = Literal["body", "caption", "page", "section", "mixed"]


class PdfElement(BaseModel):
    model_config = ConfigDict(extra="forbid")

    page: int = Field(ge=1)
    order: int = Field(ge=0)
    text: str
    kind: ElementKind = "body"
    source: str | None = None
    metadata: dict[str, object] = Field(default_factory=dict)

    @field_validator("text")
    @classmethod
    def clean_text(cls, value: str) -> str:
        return " ".join(value.replace("\u3000", " ").split())


class PdfChunk(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    strategy: str
    text: str
    page_start: int = Field(ge=1)
    page_end: int = Field(ge=1)
    kind: ChunkKind = "body"
    metadata: dict[str, object] = Field(default_factory=dict)

    @field_validator("text")
    @classmethod
    def clean_text(cls, value: str) -> str:
        return value.strip()


class StrategySummary(BaseModel):
    model_config = ConfigDict(extra="forbid")

    strategy: str
    num_chunks: int
    avg_chars: float
    min_chars: int
    max_chars: int
    caption_chunks: int
    chunks_with_captions: int
    caption_coverage: float


class RetrievalHit(BaseModel):
    model_config = ConfigDict(extra="forbid")

    chunk_id: str
    strategy: str
    score: float
    page_start: int
    page_end: int
    kind: ChunkKind
    preview: str


class QueryResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    query: str
    hits: list[RetrievalHit]


class ExperimentResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    summaries: list[StrategySummary]
    queries: list[QueryResult]
    chunks: dict[str, list[PdfChunk]]

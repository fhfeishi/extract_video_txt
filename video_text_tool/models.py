from __future__ import annotations

from enum import Enum
import os
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


def default_model_root() -> Path:
    env_value = os.getenv("VIDEO_TEXT_TOOL_MODEL_ROOT")
    if env_value:
        return Path(env_value).expanduser()
    for candidate in (Path("/mnt/e/local_models"), Path(r"E:\local_models")):
        if candidate.exists():
            return candidate
    return Path("/mnt/e/local_models")


DEFAULT_MODEL_ROOT = default_model_root()
DEFAULT_ASR_MODEL = DEFAULT_MODEL_ROOT / "asr" / "iic--speech_paraformer-large-vad-punc_asr_nat-zh-cn-16k-common-vocab8404-pytorch"
DEFAULT_VAD_MODEL = DEFAULT_MODEL_ROOT / "vad" / "iic--speech_fsmn_vad_zh-cn-16k-common-pytorch"
DEFAULT_PUNC_MODEL = DEFAULT_MODEL_ROOT / "punc" / "iic--punc_ct-transformer_cn-en-common-vocab471067-large"


class Backend(str, Enum):
    AUTO = "auto"
    FUNASR = "funasr"
    DASHSCOPE = "dashscope"


class Device(str, Enum):
    AUTO = "auto"
    CUDA = "cuda"
    CPU = "cpu"


class SubtitleMode(str, Enum):
    PREFER = "prefer"
    IGNORE = "ignore"
    ONLY = "only"


class SubtitleSourceKind(str, Enum):
    EXTERNAL = "external"
    EMBEDDED = "embedded"


class Segment(BaseModel):
    model_config = ConfigDict(extra="forbid")

    start: float = Field(ge=0)
    end: float = Field(ge=0)
    text: str
    speaker: str | None = None


class SubtitleConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    mode: SubtitleMode = SubtitleMode.PREFER
    lang: str = "auto"
    stream: int | None = None
    file: Path | None = None

    @field_validator("lang")
    @classmethod
    def normalize_lang(cls, value: str) -> str:
        value = value.strip().lower()
        return value or "auto"

    @field_validator("file", mode="before")
    @classmethod
    def normalize_file(cls, value: object) -> Path | None:
        if value in (None, ""):
            return None
        return Path(str(value)).expanduser().resolve()


class LocalAsrConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    asr_model: str = str(DEFAULT_ASR_MODEL)
    vad_model: str = str(DEFAULT_VAD_MODEL)
    punc_model: str = str(DEFAULT_PUNC_MODEL)
    device: Device = Device.AUTO


class DashScopeConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    asr_model: str = "paraformer-realtime-v2"
    llm_model: str = "qwen-plus"
    language_hints: list[str] = Field(default_factory=lambda: ["zh", "en"])
    api_key_env: str = "DASHSCOPE_API_KEY"

    @field_validator("language_hints", mode="before")
    @classmethod
    def parse_language_hints(cls, value: object) -> list[str]:
        if isinstance(value, str):
            return [item.strip() for item in value.split(",") if item.strip()]
        if isinstance(value, list):
            return [str(item).strip() for item in value if str(item).strip()]
        return ["zh", "en"]


class OutputConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    output_dir: Path = Path("outputs")
    formats: set[str] = Field(default_factory=lambda: {"txt", "srt", "json"})
    max_segment_chars: int = Field(default=90, ge=0)

    @field_validator("output_dir", mode="before")
    @classmethod
    def normalize_output_dir(cls, value: object) -> Path:
        return Path(str(value)).expanduser().resolve()

    @field_validator("formats", mode="before")
    @classmethod
    def parse_formats(cls, value: object) -> set[str]:
        if isinstance(value, str):
            return {item.strip().lower() for item in value.split(",") if item.strip()}
        if isinstance(value, set):
            return {str(item).strip().lower() for item in value if str(item).strip()}
        if isinstance(value, list | tuple):
            return {str(item).strip().lower() for item in value if str(item).strip()}
        return {"txt", "srt", "json"}

    @field_validator("formats")
    @classmethod
    def validate_formats(cls, value: set[str]) -> set[str]:
        allowed = {"txt", "srt", "json"}
        unknown = value - allowed
        if unknown:
            raise ValueError(f"Unsupported output formats: {', '.join(sorted(unknown))}")
        return value


class RunConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    input_path: Path
    backend: Backend = Backend.AUTO
    subtitle: SubtitleConfig = Field(default_factory=SubtitleConfig)
    translate_to: str | None = None
    list_streams: bool = False
    max_seconds: float | None = Field(default=None, gt=0)
    use_cache: bool = True
    force: bool = False
    local: LocalAsrConfig = Field(default_factory=LocalAsrConfig)
    dashscope: DashScopeConfig = Field(default_factory=DashScopeConfig)
    output: OutputConfig = Field(default_factory=OutputConfig)

    @field_validator("input_path", mode="before")
    @classmethod
    def normalize_input_path(cls, value: object) -> Path:
        return Path(str(value)).expanduser().resolve()

    @model_validator(mode="after")
    def validate_input_exists(self) -> RunConfig:
        if not self.input_path.exists():
            raise ValueError(f"Input file does not exist: {self.input_path}")
        if self.subtitle.file and not self.subtitle.file.exists():
            raise ValueError(f"Subtitle file does not exist: {self.subtitle.file}")
        return self

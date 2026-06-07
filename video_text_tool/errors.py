from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class ToolError(Exception):
    title: str
    detail: str = ""
    hints: list[str] = field(default_factory=list)

    def __str__(self) -> str:
        lines = [f"Error: {self.title}"]
        if self.detail:
            lines.append(self.detail)
        if self.hints:
            lines.append("")
            lines.append("Try:")
            lines.extend(f"  - {hint}" for hint in self.hints)
        return "\n".join(lines)

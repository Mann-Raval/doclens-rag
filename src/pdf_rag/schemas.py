"""Answer data shared by the pipeline and interface."""
from dataclasses import dataclass, field

@dataclass(frozen=True)
class RagAnswer:
    text: str
    pages: tuple[int, ...]
    sources: tuple[str, ...] = ()
    finish_reason: str = "UNKNOWN"
    usage: dict = field(default_factory=dict)
    warning: str = ""
    attempts: int = 1
    evidence: tuple[dict, ...] = ()

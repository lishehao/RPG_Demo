from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class PromptCompileError(RuntimeError):
    error_code: str
    message: str = ""
    errors: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        resolved = self.message or (self.errors[0] if self.errors else self.error_code)
        self.message = resolved
        super().__init__(resolved)

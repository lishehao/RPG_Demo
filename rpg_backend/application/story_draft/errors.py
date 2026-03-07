from __future__ import annotations


class DraftPatchTargetNotFoundError(RuntimeError):
    def __init__(self, *, target_type: str, target_id: str) -> None:
        self.target_type = target_type
        self.target_id = target_id
        super().__init__(f"{target_type} target '{target_id}' not found")


class DraftPatchUnsupportedError(RuntimeError):
    def __init__(self, *, target_type: str, field: str) -> None:
        self.target_type = target_type
        self.field = field
        super().__init__(f"unsupported draft patch: {target_type}.{field}")


class DraftValidationError(RuntimeError):
    def __init__(self, *, errors: list[dict]) -> None:
        self.errors = errors
        super().__init__("draft patch invalid")

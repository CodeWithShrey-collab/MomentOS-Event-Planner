from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class ApiError(Exception):
    status: int
    code: str
    message: str
    fields: list[dict[str, str]] = field(default_factory=list)
    retry_after_seconds: int | None = None

    def __str__(self) -> str:
        return self.message


def error_payload(error: ApiError, request_id: str) -> tuple[dict[str, Any], int]:
    result: dict[str, Any] = {
        "error": {"code": error.code, "message": error.message},
        "request_id": request_id,
    }
    if error.fields:
        result["error"]["fields"] = error.fields
    return result, error.status


def validation_fields(errors: list[dict[str, Any]]) -> list[dict[str, str]]:
    safe: list[dict[str, str]] = []
    for error in errors[:30]:
        path = ".".join(str(part) for part in error.get("loc", ()))[:160]
        code = str(error.get("type", "invalid_value"))[:80]
        message = str(error.get("msg", "Invalid value"))[:200]
        safe.append({"path": path, "code": code, "message": message})
    return safe

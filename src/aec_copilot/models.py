"""Serializable domain models used by the CLI, MCP server, and web API."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from .errors import AECError

ENGINES = ("revit", "acad", "sw")
ATOMIC_OPS = {
    "create_level", "create_grid", "create_wall", "create_column", "create_slab",
    "create_door", "create_window", "draw_polyline", "create_part", "create_assembly",
}
INTENT_OPS = {"create_room", "create_frame", "create_building"}
SUPPORTED_OPS = ATOMIC_OPS | INTENT_OPS


class Operation(BaseModel):
    """An intent or atomic operation; operation-specific fields are validated by the compiler."""

    model_config = ConfigDict(extra="allow")
    op: str
    id: str = Field(min_length=1, max_length=80, pattern=r"^[A-Za-z0-9_\-\u4e00-\u9fff]+$")

    @field_validator("op")
    @classmethod
    def supported(cls, value: str) -> str:
        if value not in SUPPORTED_OPS:
            raise ValueError(f"Unsupported operation {value!r}; supported={sorted(SUPPORTED_OPS)}")
        return value


class Plan(BaseModel):
    model_config = ConfigDict(extra="forbid")
    schema_version: Literal["1.0"] = "1.0"
    instruction: str = Field(min_length=1, max_length=4000)
    engine: Literal["revit", "acad", "sw"] = "revit"
    units: Literal["mm"] = "mm"
    operations: list[Operation] = Field(min_length=1, max_length=2000)
    metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator("operations")
    @classmethod
    def unique_ids(cls, operations: list[Operation]) -> list[Operation]:
        # Room/frame/building intent IDs expand to prefixed element IDs. Their
        # own IDs may coexist only once as well.
        ids = [op.id for op in operations]
        if len(ids) != len(set(ids)):
            raise ValueError("Operation IDs must be unique")
        return operations


class ToolCall(BaseModel):
    name: str
    arguments: dict[str, Any]


class Difference(BaseModel):
    code: str
    element_id: str | None = None
    path: str | None = None
    expected: Any = None
    actual: Any = None
    message: str
    suggestion: str | None = None


class VerificationReport(BaseModel):
    passed: bool
    method: Literal["deterministic", "deterministic+vlm"] = "deterministic"
    differences: list[Difference] = Field(default_factory=list)
    screenshot: str | None = None
    vlm_advisory: dict[str, Any] | None = None


class AttemptRecord(BaseModel):
    attempt: int
    status: Literal["passed", "failed", "rolled_back"]
    elapsed_ms: float
    verification: VerificationReport
    token_usage: dict[str, int] = Field(default_factory=dict)


class RunResult(BaseModel):
    run_id: str
    status: Literal["passed", "failed", "preview"]
    backend: Literal["simulation", "direct", "mcp"]
    engine: str
    instruction: str
    plan: Plan
    attempts: list[AttemptRecord]
    elements: list[dict[str, Any]]
    output_dir: str
    screenshot: str | None = None
    reports: dict[str, str] = Field(default_factory=dict)
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class Issue(BaseModel):
    rule_id: str
    severity: Literal["info", "warning", "error"]
    element_id: str | None = None
    message: str
    suggestion: str
    source: Literal["project-rule", "llm-semantic"] = "project-rule"


class AuditReport(BaseModel):
    issue_count: int
    issues: list[Issue]
    disclaimer: str = "演示项目规则检查，不构成法定规范合规审查或结构安全结论。"


def expect_rollback_safe(exc: Exception) -> AECError:
    return exc if isinstance(exc, AECError) else AECError("E_ENGINE_DOWN", str(exc), exception=type(exc).__name__)

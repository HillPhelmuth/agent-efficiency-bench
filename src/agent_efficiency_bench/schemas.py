from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator


SourceType = Literal["huggingface", "github", "custom"]
Horizon = Literal["atomic", "short", "medium", "long", "very_long"]


class ModelConfig(BaseModel):
    provider: Literal["openrouter"] = "openrouter"
    model: str
    temperature: float = 0.0
    max_completion_tokens: int = 2048
    seed: int | None = None
    tools: list[dict[str, Any]] | None = None
    tool_choice: str | dict[str, Any] | None = None
    extra: dict[str, Any] = Field(default_factory=dict)


class TraceEvent(BaseModel):
    t_rel_seconds: float
    event: str
    task_id: str | None = None
    run_id: str | None = None
    span_id: str | None = None
    parent_span_id: str | None = None
    data: dict[str, Any] = Field(default_factory=dict)


class Complexity(BaseModel):
    horizon: Horizon
    interaction_type: str = "autonomous"
    expected_tool_calls_min: int | None = None
    expected_tool_calls_typical: int | None = None
    expected_human_minutes: float | None = None
    ambiguity: Literal["low", "medium", "high"] = "medium"
    requires_planning: bool = True
    requires_memory: bool = False
    requires_external_search: bool = False
    requires_policy_following: bool = False
    requires_code_execution: bool = False
    requires_recovery: bool = False


class Budget(BaseModel):
    max_wall_clock_seconds: int = 900
    max_total_tokens: int = 200_000
    max_estimated_usd: float = 2.0
    max_tool_calls: int = 80
    max_llm_calls: int = 40


class SuccessCriteria(BaseModel):
    type: str
    minimum_quality_score: float = 1.0
    checker: str | None = None
    notes: str | None = None


class BenchmarkTask(BaseModel):
    task_id: str
    source: str
    source_type: SourceType
    source_url: str | None = None
    category: str
    domain: str | None = None
    instruction: str
    environment: dict[str, Any]
    complexity: Complexity
    budgets: Budget = Field(default_factory=Budget)
    success_criteria: SuccessCriteria
    tags: list[str] = Field(default_factory=list)
    raw: dict[str, Any] = Field(default_factory=dict)

    @field_validator("instruction")
    @classmethod
    def instruction_must_not_be_empty(cls, value: str) -> str:
        if not value or not value.strip():
            raise ValueError("instruction must not be empty")
        return value.strip()

    @field_validator("task_id")
    @classmethod
    def task_id_must_not_be_empty(cls, value: str) -> str:
        if not value or not value.strip():
            raise ValueError("task_id must not be empty")
        return value.strip()


class RunTelemetry(BaseModel):
    run_id: str
    task_id: str
    agent: str
    model: str
    scaffold: str | None = None
    trial_index: int | None = None
    server_tools_configured: list[str] = Field(default_factory=list)
    success: bool
    quality_score: float = Field(ge=0.0, le=1.0)
    wall_clock_seconds: float = Field(ge=0.0)
    llm_time_seconds: float = Field(default=0.0, ge=0.0)
    tool_time_seconds: float = Field(default=0.0, ge=0.0)
    input_tokens: int = Field(ge=0)
    output_tokens: int = Field(ge=0)
    estimated_usd: float = Field(ge=0.0)
    num_llm_calls: int = Field(default=0, ge=0)
    num_tool_calls: int = Field(default=0, ge=0)
    num_browser_actions: int = Field(default=0, ge=0)
    num_terminal_commands: int = Field(default=0, ge=0)
    num_retries: int = Field(default=0, ge=0)
    num_errors: int = Field(default=0, ge=0)
    num_citations: int = Field(default=0, ge=0)
    num_annotations: int = Field(default=0, ge=0)
    terminated_by: str | None = None

    @property
    def total_tokens(self) -> int:
        return self.input_tokens + self.output_tokens


class RunManifest(BaseModel):
    run_suite_id: str
    agent: str
    model: str
    output_dir: str
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    tasks_path: str | None = None
    task_ids: list[str] = Field(default_factory=list)
    trial_count: int = 1
    trial_indices: list[int] = Field(default_factory=list)
    scaffold: str | None = None
    tools_configured: list[str] = Field(default_factory=list)
    budget: dict[str, Any] = Field(default_factory=dict)
    suite_budget: dict[str, Any] = Field(default_factory=dict)
    source_revisions: dict[str, Any] = Field(default_factory=dict)
    evaluator: dict[str, Any] = Field(default_factory=dict)
    harness: dict[str, Any] = Field(default_factory=dict)
    provider: dict[str, Any] = Field(default_factory=dict)
    git_commit: str | None = None
    environment: dict[str, Any] = Field(default_factory=dict)


class RunResult(BaseModel):
    telemetry: RunTelemetry
    output: dict[str, Any] = Field(default_factory=dict)
    trace_path: str
    artifact_dir: str | None = None

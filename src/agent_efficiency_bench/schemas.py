from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator


SourceType = Literal["huggingface", "github", "custom"]
Horizon = Literal["atomic", "short", "medium", "long", "very_long"]


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
    terminated_by: str | None = None

    @property
    def total_tokens(self) -> int:
        return self.input_tokens + self.output_tokens

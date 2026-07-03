from __future__ import annotations

import time
from dataclasses import dataclass, field

from agent_efficiency_bench.schemas import Budget, RunTelemetry


@dataclass
class BudgetTracker:
    budget: Budget
    started_at: float = field(default_factory=time.perf_counter)
    input_tokens: int = 0
    output_tokens: int = 0
    estimated_usd: float = 0.0
    llm_time_seconds: float = 0.0
    tool_time_seconds: float = 0.0
    num_llm_calls: int = 0
    num_tool_calls: int = 0
    num_retries: int = 0
    num_errors: int = 0
    num_browser_actions: int = 0
    num_terminal_commands: int = 0

    @property
    def total_tokens(self) -> int:
        return self.input_tokens + self.output_tokens

    def elapsed_seconds(self) -> float:
        return time.perf_counter() - self.started_at

    def add_llm_call(self, prompt_tokens: int, completion_tokens: int, cost_usd: float, latency_seconds: float) -> None:
        self.input_tokens += prompt_tokens
        self.output_tokens += completion_tokens
        self.estimated_usd += cost_usd
        self.llm_time_seconds += latency_seconds
        self.num_llm_calls += 1

    def add_tool_call(self, latency_seconds: float, browser_action: bool = False, terminal_command: bool = False) -> None:
        self.tool_time_seconds += latency_seconds
        self.num_tool_calls += 1
        if browser_action:
            self.num_browser_actions += 1
        if terminal_command:
            self.num_terminal_commands += 1

    def add_retry(self) -> None:
        self.num_retries += 1

    def add_error(self) -> None:
        self.num_errors += 1

    def termination_reason(self) -> str | None:
        if self.total_tokens > self.budget.max_total_tokens:
            return "budget_tokens"
        if self.elapsed_seconds() > self.budget.max_wall_clock_seconds:
            return "budget_time"
        if self.estimated_usd > self.budget.max_estimated_usd:
            return "budget_cost"
        if self.num_tool_calls > self.budget.max_tool_calls:
            return "budget_tool_calls"
        if self.num_llm_calls > self.budget.max_llm_calls:
            return "budget_llm_calls"
        return None

    def to_run_telemetry(
        self,
        run_id: str,
        task_id: str,
        agent: str,
        model: str,
        success: bool,
        quality_score: float,
        scaffold: str | None = None,
        server_tools_configured: list[str] | None = None,
        num_citations: int = 0,
        num_annotations: int = 0,
        terminated_by: str | None = None,
    ) -> RunTelemetry:
        return RunTelemetry(
            run_id=run_id,
            task_id=task_id,
            agent=agent,
            model=model,
            scaffold=scaffold,
            server_tools_configured=server_tools_configured or [],
            success=success,
            quality_score=quality_score,
            wall_clock_seconds=self.elapsed_seconds(),
            llm_time_seconds=self.llm_time_seconds,
            tool_time_seconds=self.tool_time_seconds,
            input_tokens=self.input_tokens,
            output_tokens=self.output_tokens,
            estimated_usd=self.estimated_usd,
            num_llm_calls=self.num_llm_calls,
            num_tool_calls=self.num_tool_calls,
            num_browser_actions=self.num_browser_actions,
            num_terminal_commands=self.num_terminal_commands,
            num_retries=self.num_retries,
            num_errors=self.num_errors,
            num_citations=num_citations,
            num_annotations=num_annotations,
            terminated_by=terminated_by or self.termination_reason(),
        )

from __future__ import annotations

import time
from pathlib import Path

from agent_efficiency_bench.budget import BudgetTracker
from agent_efficiency_bench.providers.openrouter import OpenRouterClient
from agent_efficiency_bench.schemas import BenchmarkTask, ModelConfig, RunResult
from agent_efficiency_bench.tracing import TraceRecorder


SYSTEM_PROMPT = """You are executing a benchmark task. Produce the final answer only. Do not claim to use tools you were not given. If the task cannot be answered from the provided instruction, make the best attempt and state uncertainty."""


class OpenRouterAnswerAgent:
    name = "openrouter-answer"

    def __init__(self, config: ModelConfig, client: OpenRouterClient | None = None):
        self.config = config
        self.client = client or OpenRouterClient()
        self.model = config.model

    def run(self, task: BenchmarkTask, artifact_dir: str | Path) -> RunResult:
        artifact_path = Path(artifact_dir)
        artifact_path.mkdir(parents=True, exist_ok=True)
        run_id = f"{task.task_id}__answer"
        trace_path = artifact_path / "trace.jsonl"
        recorder = TraceRecorder(trace_path, run_id=run_id, task_id=task.task_id)
        budget = BudgetTracker(task.budgets)
        recorder.emit("task_start", data={"agent": self.name, "model": self.model})
        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": task.instruction},
        ]
        recorder.emit("llm_call_start", data={"model": self.model})
        started = time.perf_counter()
        response = self.client.chat(
            config=self.config,
            messages=messages,
            tools=self.config.tools,
            tool_choice=self.config.tool_choice,
        )
        latency = time.perf_counter() - started
        budget.add_llm_call(
            prompt_tokens=response.prompt_tokens,
            completion_tokens=response.completion_tokens,
            cost_usd=response.cost_usd,
            latency_seconds=latency,
        )
        recorder.emit(
            "llm_call_end",
            data={
                "generation_id": response.generation_id,
                "model": response.model,
                "prompt_tokens": response.prompt_tokens,
                "completion_tokens": response.completion_tokens,
                "total_tokens": response.total_tokens,
                "cost_usd": response.cost_usd,
                "latency_seconds": latency,
                "finish_reason": response.finish_reason,
            },
        )
        termination = budget.termination_reason() or "not_evaluated"
        telemetry = budget.to_run_telemetry(
            run_id=run_id,
            task_id=task.task_id,
            agent=self.name,
            model=response.model or self.model,
            success=False,
            quality_score=0.0,
            terminated_by=termination,
        )
        recorder.emit("task_end", data={"terminated_by": telemetry.terminated_by})
        return RunResult(
            telemetry=telemetry,
            output={"answer": response.content},
            trace_path=str(trace_path),
            artifact_dir=str(artifact_path),
        )

from __future__ import annotations

import time
from pathlib import Path

from agent_efficiency_bench.agents.openrouter_answer import (
    _budget_check_data,
    _response_annotations,
    _response_citations,
    _tool_names,
)
from agent_efficiency_bench.budget import BudgetTracker
from agent_efficiency_bench.providers.openrouter import OpenRouterClient, OpenRouterResponse
from agent_efficiency_bench.schemas import BenchmarkTask, ModelConfig, RunResult
from agent_efficiency_bench.tracing import TraceRecorder


SYSTEM_PROMPT = """You are executing a benchmark task using a minimal tool-loop scaffold. First collect concise research notes, then produce a final answer. Do not claim to use tools you were not given."""


class OpenRouterToolLoopAgent:
    name = "openrouter-tool-loop"
    scaffold = "react-tool-loop"

    def __init__(self, config: ModelConfig, client: OpenRouterClient | None = None):
        self.config = config
        self.client = client or OpenRouterClient()
        self.model = config.model

    def run(self, task: BenchmarkTask, artifact_dir: str | Path) -> RunResult:
        artifact_path = Path(artifact_dir)
        artifact_path.mkdir(parents=True, exist_ok=True)
        run_id = f"{task.task_id}__tool_loop"
        trace_path = artifact_path / "trace.jsonl"
        recorder = TraceRecorder(trace_path, run_id=run_id, task_id=task.task_id)
        budget = BudgetTracker(task.budgets)
        recorder.emit("task_start", data={"agent": self.name, "model": self.model, "scaffold": self.scaffold})

        research_messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": f"Research the task and return concise notes only.\n\nTask:\n{task.instruction}"},
        ]
        research = self._call_llm(
            recorder=recorder,
            budget=budget,
            messages=research_messages,
            tools=self.config.tools,
            tool_choice=self.config.tool_choice,
            phase="research",
        )
        termination = budget.termination_reason()
        if termination:
            budget_data = _budget_check_data(budget, termination)
            recorder.emit("budget_exceeded", data=budget_data)
            recorder.emit("task_end", data={"terminated_by": termination})
            return self._result(
                task=task,
                run_id=run_id,
                artifact_path=artifact_path,
                trace_path=trace_path,
                budget=budget,
                response=research,
                answer=research.content,
                research=research.content,
                termination=termination,
            )

        final_messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": task.instruction},
            {"role": "assistant", "content": f"Research notes:\n{research.content}"},
            {"role": "user", "content": "Using the research notes, provide the final answer only."},
        ]
        final = self._call_llm(
            recorder=recorder,
            budget=budget,
            messages=final_messages,
            tools=None,
            tool_choice=None,
            phase="final",
        )
        termination = budget.termination_reason() or "not_evaluated"
        recorder.emit("task_end", data={"terminated_by": termination})
        return self._result(
            task=task,
            run_id=run_id,
            artifact_path=artifact_path,
            trace_path=trace_path,
            budget=budget,
            response=final,
            answer=final.content,
            research=research.content,
            termination=termination,
        )

    def _call_llm(
        self,
        recorder: TraceRecorder,
        budget: BudgetTracker,
        messages: list[dict],
        tools: list[dict] | None,
        tool_choice,
        phase: str,
    ) -> OpenRouterResponse:
        recorder.emit(
            "llm_call_start",
            data={
                "phase": phase,
                "model": self.model,
                "tools_configured": _tool_names(tools),
                "tools": tools or [],
                "tool_choice": tool_choice,
            },
        )
        started = time.perf_counter()
        response = self.client.chat(config=self.config, messages=messages, tools=tools, tool_choice=tool_choice)
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
                "phase": phase,
                "generation_id": response.generation_id,
                "model": response.model,
                "prompt_tokens": response.prompt_tokens,
                "completion_tokens": response.completion_tokens,
                "total_tokens": response.total_tokens,
                "cost_usd": response.cost_usd,
                "latency_seconds": latency,
                "finish_reason": response.finish_reason,
                "annotations": _response_annotations(response.raw),
                "citations": _response_citations(response.raw),
            },
        )
        recorder.emit("budget_check", data=_budget_check_data(budget, budget.termination_reason()))
        return response

    def _result(
        self,
        task: BenchmarkTask,
        run_id: str,
        artifact_path: Path,
        trace_path: Path,
        budget: BudgetTracker,
        response: OpenRouterResponse,
        answer: str,
        research: str,
        termination: str,
    ) -> RunResult:
        telemetry = budget.to_run_telemetry(
            run_id=run_id,
            task_id=task.task_id,
            agent=self.name,
            model=response.model or self.model,
            scaffold=self.scaffold,
            success=False,
            quality_score=0.0,
            terminated_by=termination,
        )
        return RunResult(
            telemetry=telemetry,
            output={"answer": answer, "research": research},
            trace_path=str(trace_path),
            artifact_dir=str(artifact_path),
        )

from __future__ import annotations

from collections import Counter
from pathlib import Path
import time

import typer
from rich.console import Console
from rich.table import Table

from agent_efficiency_bench.agents.openrouter_answer import OpenRouterAnswerAgent
from agent_efficiency_bench.evaluators.simple import NoOpEvaluator
from agent_efficiency_bench.io import read_jsonl, write_jsonl
from agent_efficiency_bench.metrics import aggregate_runs
from agent_efficiency_bench.providers.openrouter import OpenRouterClient
from agent_efficiency_bench.runner import BenchmarkRunner
from agent_efficiency_bench.schemas import BenchmarkTask, ModelConfig, RunTelemetry
from agent_efficiency_bench.sources import load_sources_from_config

app = typer.Typer(help="Agentic efficiency benchmark tooling.")
console = Console()


def select_tasks(tasks: list[BenchmarkTask], category: str | None = None, limit: int | None = None) -> list[BenchmarkTask]:
    selected = [task for task in tasks if category is None or task.category == category]
    return selected[:limit] if limit is not None else selected


@app.command("build-subset")
def build_subset(
    config: str = typer.Option("configs/sources.yaml", help="Source config YAML."),
    output: str = typer.Option("data/tasks/public_efficiency_subset.jsonl", help="Output JSONL path."),
) -> None:
    """Extract small public benchmark subsets into the normalized task schema."""
    tasks = load_sources_from_config(config)
    count = write_jsonl(output, tasks)
    console.print(f"[green]Wrote {count} tasks[/green] to {output}")


@app.command("catalog")
def catalog(path: str) -> None:
    """Summarize a normalized task JSONL file."""
    rows = [BenchmarkTask.model_validate(row) for row in read_jsonl(path)]
    by_category = Counter(row.category for row in rows)
    by_source = Counter(row.source for row in rows)

    table = Table(title=f"Task catalog: {Path(path).name}")
    table.add_column("Dimension")
    table.add_column("Value")
    table.add_column("Count", justify="right")
    for value, count in sorted(by_category.items()):
        table.add_row("category", value, str(count))
    for value, count in sorted(by_source.items()):
        table.add_row("source", value, str(count))
    console.print(table)


@app.command("score-runs")
def score_runs(path: str) -> None:
    """Summarize run telemetry JSONL using success-gated efficiency metrics."""
    runs = [RunTelemetry.model_validate(row) for row in read_jsonl(path)]
    summary = aggregate_runs(runs)
    console.print_json(summary.model_dump_json(exclude_none=True))


@app.command("run-answer")
def run_answer(
    tasks: str = typer.Option("data/tasks/public_efficiency_subset.jsonl", help="Normalized task JSONL path."),
    model: str = typer.Option(..., help="OpenRouter model id, e.g. openai/gpt-4o-mini."),
    category: str | None = typer.Option(None, help="Optional task category filter."),
    limit: int | None = typer.Option(None, help="Maximum tasks to run."),
    output_dir: str = typer.Option("runs/smoke", help="Output directory for traces and JSONL results."),
    max_completion_tokens: int = typer.Option(2048, help="Per-call max completion tokens."),
) -> None:
    """Run an answer-only OpenRouter baseline over normalized tasks."""
    loaded_tasks = [BenchmarkTask.model_validate(row) for row in read_jsonl(tasks)]
    selected = select_tasks(loaded_tasks, category=category, limit=limit)
    agent = OpenRouterAnswerAgent(config=ModelConfig(model=model, max_completion_tokens=max_completion_tokens))
    runner = BenchmarkRunner(agent=agent, evaluator=NoOpEvaluator(), output_dir=output_dir)
    results = runner.run_tasks(selected)
    console.print(f"[green]Ran {len(results)} task(s)[/green]; outputs written to {output_dir}")


@app.command("openrouter-smoke")
def openrouter_smoke(
    model: str = typer.Option(..., help="OpenRouter model id, e.g. openai/gpt-4o-mini."),
) -> None:
    """Verify OpenRouter connectivity and token/cost telemetry with one tiny request."""
    try:
        client = OpenRouterClient()
    except ValueError as exc:
        raise typer.BadParameter(str(exc)) from exc
    started = time.perf_counter()
    response = client.chat(
        ModelConfig(model=model, max_completion_tokens=16),
        [{"role": "user", "content": "Reply with exactly: ok"}],
    )
    latency = time.perf_counter() - started
    if response.prompt_tokens <= 0 or response.completion_tokens <= 0:
        raise typer.BadParameter("OpenRouter response did not include nonzero token usage")
    table = Table(title="OpenRouter smoke result")
    table.add_column("Field")
    table.add_column("Value")
    table.add_row("model", response.model)
    table.add_row("generation_id", response.generation_id)
    table.add_row("prompt_tokens", str(response.prompt_tokens))
    table.add_row("completion_tokens", str(response.completion_tokens))
    table.add_row("cost_usd", str(response.cost_usd))
    table.add_row("latency_seconds", f"{latency:.3f}")
    table.add_row("content", response.content)
    console.print(table)


if __name__ == "__main__":
    app()

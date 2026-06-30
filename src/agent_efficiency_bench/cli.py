from __future__ import annotations

from collections import Counter
from pathlib import Path

import typer
from rich.console import Console
from rich.table import Table

from agent_efficiency_bench.io import read_jsonl, write_jsonl
from agent_efficiency_bench.metrics import aggregate_runs
from agent_efficiency_bench.schemas import BenchmarkTask, RunTelemetry
from agent_efficiency_bench.sources import load_sources_from_config

app = typer.Typer(help="Agentic efficiency benchmark tooling.")
console = Console()


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


if __name__ == "__main__":
    app()

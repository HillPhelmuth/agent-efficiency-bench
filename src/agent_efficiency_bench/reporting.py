from __future__ import annotations

import statistics
from pathlib import Path
from typing import Any

from agent_efficiency_bench.metrics import aggregate_runs
from agent_efficiency_bench.schemas import RunTelemetry


def summarize_by_category(tasks: dict[str, dict[str, Any]], runs: list[RunTelemetry]) -> dict[str, dict[str, Any]]:
    grouped: dict[str, list[RunTelemetry]] = {}
    for run in runs:
        category = tasks.get(run.task_id, {}).get("category", "unknown")
        grouped.setdefault(category, []).append(run)
    return {category: _summary_for_runs(category_runs) for category, category_runs in sorted(grouped.items())}


def _summary_for_runs(runs: list[RunTelemetry]) -> dict[str, Any]:
    aggregate = aggregate_runs(runs).model_dump()
    costs = [run.estimated_usd for run in runs]
    latencies = [run.wall_clock_seconds for run in runs]
    aggregate.update(
        {
            "p50_cost_usd": _percentile(costs, 0.50),
            "p95_cost_usd": _percentile(costs, 0.95),
            "p50_latency_seconds": _percentile(latencies, 0.50),
            "p95_latency_seconds": _percentile(latencies, 0.95),
            "retry_rate": sum(run.num_retries for run in runs) / len(runs) if runs else 0.0,
            "error_rate": sum(1 for run in runs if run.num_errors > 0) / len(runs) if runs else 0.0,
        }
    )
    return aggregate


def _percentile(values: list[float], pct: float) -> float | None:
    if not values:
        return None
    if len(values) == 1:
        return values[0]
    sorted_values = sorted(values)
    index = pct * (len(sorted_values) - 1)
    lower = int(index)
    upper = min(lower + 1, len(sorted_values) - 1)
    weight = index - lower
    return sorted_values[lower] * (1 - weight) + sorted_values[upper] * weight


def write_markdown_report(output: str | Path, summary: dict[str, dict[str, Any]]) -> None:
    path = Path(output)
    path.parent.mkdir(parents=True, exist_ok=True)
    metrics = sorted({metric for values in summary.values() for metric in values})
    lines = ["# Agent Efficiency Report", "", "| category | metric | value |", "|---|---|---|"]
    for category, values in sorted(summary.items()):
        for metric in metrics:
            if metric in values:
                lines.append(f"| {category} | {metric} | {values[metric]} |")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")

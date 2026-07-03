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


def summarize_by_dimensions(
    tasks: dict[str, dict[str, Any]],
    runs: list[RunTelemetry],
    dimensions: list[str],
    manifests: dict[str, dict[str, Any]] | None = None,
) -> dict[str, dict[str, Any]]:
    grouped: dict[str, list[RunTelemetry]] = {}
    for run in runs:
        key = _group_key(tasks.get(run.task_id, {}), run, dimensions, manifests or {})
        grouped.setdefault(key, []).append(run)
    return {key: _summary_for_runs(group_runs) for key, group_runs in sorted(grouped.items())}


def _group_key(
    task: dict[str, Any],
    run: RunTelemetry,
    dimensions: list[str],
    manifests: dict[str, dict[str, Any]],
) -> str:
    parts = []
    for dimension in dimensions:
        parts.append(f"{dimension}={_dimension_value(task, run, dimension, manifests)}")
    return " | ".join(parts) if parts else "all"


def _dimension_value(
    task: dict[str, Any],
    run: RunTelemetry,
    dimension: str,
    manifests: dict[str, dict[str, Any]],
) -> str:
    if dimension in {"category", "source"}:
        return str(task.get(dimension, "unknown"))
    if dimension == "model":
        return run.model
    if dimension == "agent":
        return run.agent
    if dimension == "scaffold":
        return run.scaffold or "unknown"
    if dimension == "trial_index":
        return str(run.trial_index) if run.trial_index is not None else "none"
    if dimension == "horizon":
        return str((task.get("complexity") or {}).get("horizon", "unknown"))
    if dimension == "requires_external_search":
        value = bool((task.get("complexity") or {}).get("requires_external_search", False))
        return str(value).lower()
    if dimension == "tools_enabled":
        manifest = manifests.get(run.run_id) or manifests.get("*") or {}
        configured = manifest.get("tools_configured")
        if configured is None:
            configured = run.server_tools_configured
        value = bool(configured)
        return str(value).lower()
    return "unknown"


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
            "mean_cost_usd": statistics.mean(costs) if costs else 0.0,
            "stdev_cost_usd": statistics.stdev(costs) if len(costs) > 1 else 0.0,
            "stdev_latency_seconds": statistics.stdev(latencies) if len(latencies) > 1 else 0.0,
            "stdev_total_tokens": statistics.stdev([run.total_tokens for run in runs]) if len(runs) > 1 else 0.0,
            "stdev_quality": statistics.stdev([run.quality_score for run in runs]) if len(runs) > 1 else 0.0,
            "retry_rate": sum(run.num_retries for run in runs) / len(runs) if runs else 0.0,
            "error_rate": sum(1 for run in runs if run.num_errors > 0) / len(runs) if runs else 0.0,
            "total_citations": sum(run.num_citations for run in runs),
            "avg_citations": sum(run.num_citations for run in runs) / len(runs) if runs else 0.0,
            "total_annotations": sum(run.num_annotations for run in runs),
            "avg_annotations": sum(run.num_annotations for run in runs) / len(runs) if runs else 0.0,
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
    lines = ["# Agent Efficiency Report", "", "| group | metric | value |", "|---|---|---|"]
    for group, values in sorted(summary.items()):
        for metric in metrics:
            if metric in values:
                lines.append(f"| {group} | {metric} | {values[metric]} |")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")

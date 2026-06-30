from __future__ import annotations

from pydantic import BaseModel

from agent_efficiency_bench.schemas import RunTelemetry


class RunEfficiency(BaseModel):
    run_id: str
    task_id: str
    outcome_score: float
    total_tokens: int
    wall_clock_seconds: float
    estimated_usd: float
    quality_per_dollar: float
    quality_per_minute: float
    quality_per_1k_tokens: float


class AggregateEfficiency(BaseModel):
    total_runs: int
    successful_runs: int
    success_rate: float
    total_cost: float
    cost_per_success: float | None
    total_tokens: int
    tokens_per_success: float | None
    total_wall_clock_seconds: float
    seconds_per_success: float | None
    mean_quality: float


def _safe_div(numerator: float, denominator: float, floor: float) -> float:
    return numerator / max(denominator, floor)


def score_run(run: RunTelemetry) -> RunEfficiency:
    """Compute success-gated efficiency for one run.

    Failed runs receive an outcome score of 0 even if they are cheap. Partial
    quality can be represented by setting success=True and quality_score < 1.
    """
    outcome = run.quality_score if run.success else 0.0
    return RunEfficiency(
        run_id=run.run_id,
        task_id=run.task_id,
        outcome_score=outcome,
        total_tokens=run.total_tokens,
        wall_clock_seconds=run.wall_clock_seconds,
        estimated_usd=run.estimated_usd,
        quality_per_dollar=_safe_div(outcome, run.estimated_usd, 1e-6),
        quality_per_minute=_safe_div(outcome, run.wall_clock_seconds / 60.0, 1e-6),
        quality_per_1k_tokens=_safe_div(outcome, run.total_tokens / 1000.0, 1e-6),
    )


def aggregate_runs(runs: list[RunTelemetry]) -> AggregateEfficiency:
    total_runs = len(runs)
    successful_runs = sum(1 for run in runs if run.success)
    total_cost = round(sum(run.estimated_usd for run in runs), 10)
    total_tokens = sum(run.total_tokens for run in runs)
    total_wall_clock = sum(run.wall_clock_seconds for run in runs)
    mean_quality = sum(run.quality_score for run in runs) / total_runs if total_runs else 0.0

    return AggregateEfficiency(
        total_runs=total_runs,
        successful_runs=successful_runs,
        success_rate=successful_runs / total_runs if total_runs else 0.0,
        total_cost=total_cost,
        cost_per_success=round(total_cost / successful_runs, 10) if successful_runs else None,
        total_tokens=total_tokens,
        tokens_per_success=total_tokens / successful_runs if successful_runs else None,
        total_wall_clock_seconds=total_wall_clock,
        seconds_per_success=total_wall_clock / successful_runs if successful_runs else None,
        mean_quality=mean_quality,
    )

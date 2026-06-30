# Agent Efficiency Benchmark Design

## Core abstraction

The project separates **task definition** from **run telemetry**.

- `BenchmarkTask`: normalized instruction, source, environment, complexity labels, budgets, and success criteria.
- `RunTelemetry`: agent/model/scaffold identity plus resource usage and outcome.
- `RunEfficiency`: derived success-gated efficiency metrics.

## Why success-gated efficiency?

A failed run that spends zero dollars is not useful. Efficiency metrics therefore use `quality_score` only when `success=true`; failed runs still count toward aggregate spend, tokens, latency, and cost-per-success.

## Current public subset strategy

The initial subset is intentionally small for fast iteration:

1. 8 SWE-bench Lite tasks for coding/terminal issue resolution.
2. 8 AssistantBench dev tasks for open-web research.
3. 8 Terminal-Bench task YAMLs for terminal/container workflows.

The subset is deterministic via SHA-256 ordering of stable row IDs, not random sampling. This makes repeated builds reproducible while avoiding large downloads.

## Next adapters to add

- τ³-bench / tau2-bench conversational tool workflows.
- WorkArena / BrowserGym browser enterprise workflows.
- MCP-Bench or MCP-Universe tool-server workflows.
- OSWorld desktop/computer-use tasks.

## Recommended leaderboard columns

- success_rate
- mean_quality
- median_cost_usd
- cost_per_success
- median_latency_seconds
- p95_latency_seconds
- tokens_per_success
- tool_calls_per_success
- retry_rate
- Pareto frontier: quality vs. cost/time/tokens

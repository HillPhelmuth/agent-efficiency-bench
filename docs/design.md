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
4. 8 tau2-bench tasks for conversational tool/policy workflows, split across retail and airline domains.

The subset is deterministic via SHA-256 ordering of stable row IDs, not random sampling. This makes repeated builds reproducible while avoiding large downloads.

## v0 completion contract

v0 is complete only when the default dev subset is benchmarkable end to end.

- Each default source in the dev subset must have a source adapter.
- Each default source in the dev subset must have either a real evaluator or an official harness result parser.
- Every source included in the default dev subset must be scoreable end to end before v0 is considered complete.
- Default reports must exclude unevaluated runs from benchmark success summaries or label them explicitly as unevaluated.
- Benchmark provenance must be recorded in manifests so results can be traced back to task selection, evaluator choice, harness, and provider metadata.

Run status terms:

- `evaluated`: the harness produced a score through a local evaluator or parsed official harness result.
- `unevaluated`: the harness produced telemetry, but no scoring path exists yet for benchmark interpretation.
- `successful`: an evaluated run satisfied its success criteria.
- `failed`: the run did not satisfy its success criteria, including cases where an evaluator returned a zero-quality outcome.
- `budget-exceeded`: execution stopped because a configured budget limit was reached before another step or task could safely begin.

## Benchmark tiers

- `smoke`: one task per selected source, intended for cheap local validation and no-token or low-token checks.
- `dev`: the deterministic public subset used by the default local workflow.
- `release`: a larger pinned subset used for repeatable scaffold and model comparisons.
- `external/full`: official upstream suites that require separate harness setup and may incur substantial runtime or monetary cost.

## Current evaluator coverage

- `AssistantBench/AssistantBench`: locally evaluated through structured-answer or exact-answer logic when normalized expected metadata is available.
- `SWE-bench/SWE-bench_Lite`: explicit unevaluated status in local generic runs until official harness output is attached and parsed.
- `harbor-framework/terminal-bench`: explicit unevaluated status in local generic runs until official harness output is attached and parsed.
- `sierra-research/tau2-bench`: explicit unevaluated status in local generic runs until official harness output is attached and parsed.

This separation is intentional: v0 reporting should not present local answer-only or tool-loop scaffolds as benchmark-scored results for sources whose success criteria depend on official external harnesses.

## Next adapters to add

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

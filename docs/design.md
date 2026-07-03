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

The following adapter families are explicitly `post-v0`. v0 stays focused on the four currently scaffolded source categories and their existing evaluator or official-harness result paths.

| adapter | status | reason | prerequisites |
|---|---|---|---|
| WorkArena / BrowserGym | post-v0 | Adds browser-environment orchestration, enterprise workflow fixtures, and browser-action evaluation surfaces that are outside the current four-source v0 contract. | Stable browser harness integration, environment provisioning, browser trace schema, and evaluation mapping into common result fields. |
| MCP-Bench / MCP-Universe | post-v0 | Adds tool-server and MCP-session coordination that would require new environment setup, tool availability contracts, and likely new telemetry semantics beyond the current v0 adapters. | Pinned upstream suite choice, MCP server lifecycle management, tool/server capability manifests, and normalized evaluation output. |
| OSWorld | post-v0 | Adds desktop/computer-use execution surfaces with heavier runtime dependencies and different action/observation loops than the current web, terminal, and tool-workflow slices. | Desktop automation environment, reproducible VM/container story, action trace normalization, and official evaluation ingestion. |

They are excluded from v0 completion because none is required to make the current default dev subset benchmarkable end to end, and each would substantially widen the environment and evaluation surface beyond the present harness guarantees.

## Recommended leaderboard columns

- success_rate
- mean_quality
- unevaluated_runs
- budget_exceeded_runs
- median_cost_usd
- p95_cost_usd
- cost_per_success
- mean_tool_calls
- tool_calls_per_success
- server_tools_enabled_rate
- median_latency_seconds
- p95_latency_seconds
- tokens_per_success
- retry_rate
- error_rate
- Pareto frontier: quality vs. cost/time/tokens

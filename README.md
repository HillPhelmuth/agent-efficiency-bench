# Agent Efficiency Bench

Telemetry-first scaffolding for evaluating LLM agents on realistic tasks by **success-gated efficiency**: cost, tokens, wall-clock time, retries, and tool use.

This repository starts with small public subsets from Hugging Face and GitHub benchmarks, normalized into a common task schema.

## Goals

- Normalize heterogeneous agent benchmarks into one `BenchmarkTask` schema.
- Extract small, representative public subsets for fast iteration.
- Track run telemetry separately from outcome scoring.
- Report cost/time/token efficiency only in the context of task success or quality.

## Quick start

```bash
uv sync --extra dev
PYTHONPATH= uv run python -m pytest -q
PYTHONPATH= uv run aeb build-subset --config configs/sources.yaml --output data/tasks/public_efficiency_subset.jsonl
PYTHONPATH= uv run aeb catalog data/tasks/public_efficiency_subset.jsonl
```

## Public sources currently scaffolded

- `SWE-bench/SWE-bench_Lite` from Hugging Face — software engineering issue-resolution tasks.
- `AssistantBench/AssistantBench` from Hugging Face — realistic web research tasks.
- `harbor-framework/terminal-bench` from GitHub — terminal/container tasks sampled from task YAML files.

The extractor intentionally takes only small subsets. This repository stores normalized metadata/instructions, not heavyweight benchmark environments.

## Repository layout

```text
configs/sources.yaml                  # source selection and per-source sample sizes
data/tasks/                           # generated normalized task subsets
src/agent_efficiency_bench/           # package code
tests/                                # unit tests
```

## Score philosophy

A run that fails cheaply is not efficient. The primary reporting flow is:

1. Evaluate outcome: `success` and/or `quality_score`.
2. Measure resources: tokens, time, LLM calls, tool calls, retries, USD.
3. Report success-gated efficiency: cost per success, quality per dollar, quality per minute, quality per 1K tokens.


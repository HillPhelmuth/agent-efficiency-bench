# Agent Efficiency Bench

Telemetry-first scaffolding for evaluating LLM agents on realistic tasks by **success-gated efficiency**: cost, tokens, wall-clock time, retries, and tool use.

This repository starts with small public subsets from Hugging Face and GitHub benchmarks, normalized into a common task schema.

## Goals

- Normalize heterogeneous agent benchmarks into one `BenchmarkTask` schema.
- Extract small, representative public subsets for fast iteration.
- Track run telemetry separately from outcome scoring.
- Report cost/time/token efficiency only in the context of task success or quality.

## v0 Scope

v0 is the point where this repository becomes a credible local benchmark harness for a small default subset, not just a source-normalization scaffold.

Included in v0:

- A deterministic dev subset built from the public sources in `configs/sources.yaml` and written to `data/tasks/public_efficiency_subset.jsonl`.
- A source adapter for every default source included in that dev subset.
- End-to-end scoring for every source included in the default dev subset, either through a local evaluator or an official harness result parser.
- Reports and manifests that distinguish evaluated runs from unevaluated runs and preserve benchmark provenance.

Excluded from v0:

- Full upstream benchmark execution as the default local workflow.
- Claims of benchmark success for runs that do not have a real evaluator or official harness result.
- Large-scale paid benchmark sweeps by default.

Benchmark tiers:

- `smoke`: 1 task per selected source for fast local validation, fake-provider checks, and CLI sanity tests.
- `dev`: the deterministic public subset under `configs/sources.yaml` and `data/tasks/public_efficiency_subset.jsonl`; this is the default v0 benchmark slice.
- `release`: a larger pinned subset intended for model and scaffold comparisons once the local workflow is stable.
- `external/full`: official benchmark suites that require upstream harness setup and may run Docker, external environments, or paid model calls.

Run/evaluation terms used throughout the docs:

- `evaluated`: the run was scored by a real evaluator or by parsed official harness output.
- `unevaluated`: the run produced telemetry or artifacts, but there is no scoring path that can justify benchmark success claims.
- `successful`: the evaluated run met its success criteria.
- `failed`: the run completed or terminated without meeting success criteria.
- `budget-exceeded`: the run stopped because a task or suite budget limit was hit; any resources already spent still count in telemetry.

Current local scoring status:

- `web_research` / AssistantBench tasks are evaluated through structured-answer or exact-answer logic when expected metadata is present.
- `software_engineering` / SWE-bench Lite tasks are treated as unevaluated in generic local runs unless official harness result metadata is attached.
- `terminal_work` / Terminal-Bench tasks are treated as unevaluated in generic local runs unless official harness result metadata is attached.
- `tool_workflow` / tau2-bench tasks are treated as unevaluated in generic local runs unless official harness result metadata is attached. A tau2 official adapter now supports task-id mapping and dry-run planning, but execute still requires an explicit external runner module because the upstream command shape is not pinned in this repository.

## Quick start

```bash
uv sync --extra dev
PYTHONPATH= uv run python -m pytest -q
PYTHONPATH= uv run aeb build-subset --config configs/sources.yaml --output data/tasks/public_efficiency_subset.jsonl
PYTHONPATH= uv run aeb catalog data/tasks/public_efficiency_subset.jsonl
```

## OpenRouter execution

Live model execution uses OpenRouter. Set:

```bash
export OPENROUTER_API_KEY="..."
```

Smoke test:

```bash
PYTHONPATH= uv run aeb openrouter-smoke --model openai/gpt-5.4-nano
```

Run one cheap answer-only baseline task:

```bash
PYTHONPATH= uv run aeb run-answer \
  --tasks data/tasks/public_efficiency_subset.jsonl \
  --model openai/gpt-5.4-nano \
  --category web_research \
  --limit 1 \
  --output-dir runs/smoke \
  --max-completion-tokens 256
```

Run the minimal two-call tool-loop scaffold when you want to compare a research/synthesis loop against answer-only behavior:

```bash
PYTHONPATH= uv run aeb run-tool-loop \
  --tasks data/tasks/public_efficiency_subset.jsonl \
  --model openai/gpt-5.4-nano \
  --category web_research \
  --limit 1 \
  --output-dir runs/tool-loop-smoke \
  --max-completion-tokens 256
```

Add `--enable-web-search` for tasks that require OpenRouter's native `openrouter:web_search` server tool.

Add `--n-trials <N>` to repeat each selected task when you want variance-aware comparisons rather than a single sample.

Generate a report:

```bash
PYTHONPATH= uv run aeb report \
  --tasks data/tasks/public_efficiency_subset.jsonl \
  --runs runs/smoke/run_telemetry.jsonl \
  --output runs/smoke/report.md
```

See `docs/openrouter.md` and `docs/running-benchmarks.md` for full details.

## Public sources currently scaffolded

- `SWE-bench/SWE-bench_Lite` from Hugging Face — software engineering issue-resolution tasks.
- `AssistantBench/AssistantBench` from Hugging Face — realistic web research tasks.
- `harbor-framework/terminal-bench` from GitHub — terminal/container tasks sampled from task YAML files.
- `sierra-research/tau2-bench` from GitHub — MIT-licensed conversational tool/policy workflow tasks sampled from retail and airline domain JSON files.

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


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

- A deterministic dev subset built from the public sources in `configs/sources-dev.yaml` and written to `data/tasks/public_efficiency_subset.jsonl`, with `configs/sources.yaml` kept as a compatibility alias.
- A source adapter for every default source included in that dev subset.
- End-to-end scoring for every source included in the default dev subset, either through a local evaluator or an official harness result parser.
- Reports and manifests that distinguish evaluated runs from unevaluated runs and preserve benchmark provenance.

Excluded from v0:

- Full upstream benchmark execution as the default local workflow.
- Claims of benchmark success for runs that do not have a real evaluator or official harness result.
- Large-scale paid benchmark sweeps by default.

Benchmark tiers:

- `smoke`: 1 task per selected source for fast local validation, fake-provider checks, and CLI sanity tests.
- `dev`: the deterministic public subset under `configs/sources-dev.yaml` and `data/tasks/public_efficiency_subset.jsonl`; `configs/sources.yaml` points to the same configuration for compatibility.
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
PYTHONPATH= uv run aeb build-subset --config configs/sources-smoke.yaml --output data/tasks/public_efficiency_smoke.jsonl
PYTHONPATH= uv run aeb build-subset --config configs/sources-dev.yaml --output data/tasks/public_efficiency_subset.jsonl
PYTHONPATH= uv run aeb catalog data/tasks/public_efficiency_subset.jsonl
```

Use `configs/sources-smoke.yaml` for first-time validation, `configs/sources-dev.yaml` for normal local comparisons, and `configs/sources-release.yaml` for larger repeated-trial comparisons.

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

Launch the REST API and charting dashboard:

```bash
PYTHONPATH= uv run aeb serve --host 127.0.0.1 --port 8000
# or
PYTHONPATH= uv run aeb-api
```

Open `http://127.0.0.1:8000/` to select models, scaffolds, categories, web-search modes, trials, and suite budgets. The same workflow is available as JSON through endpoints such as `GET /api/catalog`, `GET /api/options`, `POST /api/runs`, `GET /api/runs/{job_id}`, and `GET /api/runs/{job_id}/results`.

Generate a report:

```bash
PYTHONPATH= uv run aeb report \
  --tasks data/tasks/public_efficiency_subset.jsonl \
  --runs runs/smoke/run_telemetry.jsonl \
  --output runs/smoke/report.md

PYTHONPATH= uv run aeb report \
  --tasks data/tasks/public_efficiency_subset.jsonl \
  --runs runs/smoke/run_telemetry.jsonl \
  --format json \
  --output runs/smoke/report.json
```

Reports can now be emitted as Markdown, JSON, or CSV. The grouped summaries include success rate, mean quality, median and p95 cost/latency, cost per success, tokens per success, retry/error rates, server-tool usage signals, and explicit unevaluated or budget-exceeded counts.

See `docs/openrouter.md` and `docs/running-benchmarks.md` for full details.

For a no-token end-to-end smoke check that covers subset build, audit, fake-provider execution, manifest writing, and report generation, run:

```bash
PYTHONPATH= uv run python -m pytest tests/test_integration_fake_provider.py -q
```

## Public sources currently scaffolded

- `SWE-bench/SWE-bench_Lite` from Hugging Face — software engineering issue-resolution tasks.
- `AssistantBench/AssistantBench` from Hugging Face — realistic web research tasks.
- `harbor-framework/terminal-bench` from GitHub — terminal/container tasks sampled from task YAML files.
- `sierra-research/tau2-bench` from GitHub — MIT-licensed conversational tool/policy workflow tasks sampled from retail and airline domain JSON files.

The extractor intentionally takes only small subsets. This repository stores normalized metadata/instructions, not heavyweight benchmark environments.

Browser enterprise workflows such as WorkArena/BrowserGym, MCP-centric suites such as MCP-Bench or MCP-Universe, and desktop/computer-use suites such as OSWorld are not currently scaffolded here and remain post-v0 roadmap items.

## Repository layout

```text
configs/sources-smoke.yaml            # 1 task per source for smoke validation
configs/sources-dev.yaml              # default dev subset definition
configs/sources-release.yaml          # larger release-style subset definition
configs/sources.yaml                  # compatibility alias for configs/sources-dev.yaml
data/tasks/                           # generated normalized task subsets
src/agent_efficiency_bench/           # package code
tests/                                # unit tests
```

## Score philosophy

A run that fails cheaply is not efficient. The primary reporting flow is:

1. Evaluate outcome: `success` and/or `quality_score`.
2. Measure resources: tokens, time, LLM calls, tool calls, retries, USD.
3. Report success-gated efficiency: cost per success, quality per dollar, quality per minute, quality per 1K tokens.


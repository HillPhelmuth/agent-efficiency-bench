# Running Benchmarks

## 1. Verify the local package

```bash
PYTHONPATH= uv run python -m pytest -q
```

## 2. Build or inspect the public task subset

```bash
PYTHONPATH= uv run aeb build-subset \
  --config configs/sources.yaml \
  --output data/tasks/public_efficiency_subset.jsonl

PYTHONPATH= uv run aeb catalog data/tasks/public_efficiency_subset.jsonl

PYTHONPATH= uv run aeb audit-tasks \
  data/tasks/public_efficiency_subset.jsonl \
  --output docs/calibration/task-audit.md
```

For v0, this dev subset is the default local benchmark slice. Smoke runs are smaller local validation paths, while official full benchmark harnesses remain separate from these local scaffold runs.

By default, local `run-answer` and `run-tool-loop` executions now use task-aware evaluator selection. AssistantBench-style web-research tasks can be scored locally when expected metadata is present. SWE-bench, Terminal-Bench, and tau2 tasks remain explicitly `unevaluated` in these generic local runs unless official harness result metadata is attached and parsed.

The audit command reports task counts by source/category/horizon/interaction/success criteria and flags weak evaluator or instruction signals.

The current default dev subset has 32 tasks total: 8 `software_engineering`, 8 `web_research`, 8 `terminal_work`, and 8 `tool_workflow`. That maps to 8 tasks each from SWE-bench Lite, AssistantBench, Terminal-Bench, and tau2-bench.

## 3. Verify OpenRouter connectivity

Without an API key, this should fail clearly:

```bash
PYTHONPATH= uv run aeb openrouter-smoke --model openai/gpt-5.4-nano
```

With an API key:

```bash
export OPENROUTER_API_KEY="..."
PYTHONPATH= uv run aeb openrouter-smoke --model openai/gpt-5.4-nano
```

## 4. Run one answer-only baseline task

```bash
PYTHONPATH= uv run aeb run-answer \
  --tasks data/tasks/public_efficiency_subset.jsonl \
  --model openai/gpt-5.4-nano \
  --category web_research \
  --limit 1 \
  --output-dir runs/smoke \
  --n-trials 2 \
  --max-completion-tokens 256 \
  --max-suite-usd 1.00 \
  --max-suite-tasks 1
```

If the task requires live web search, add `--enable-web-search`. This passes OpenRouter's native server tool configuration:

```json
{"type": "openrouter:web_search", "parameters": {"engine": "native"}}
```

When provider-side search is enabled, telemetry records `server_tools_configured`, `num_annotations`, and `num_citations` separately from local `num_tool_calls`.

Outputs:

```text
runs/smoke/run_results.jsonl
runs/smoke/run_telemetry.jsonl
runs/smoke/<task_id>/trace.jsonl
```

## 4a. Run the minimal tool-loop scaffold

Use `run-tool-loop` when you want a comparable multi-step scaffold: one research call, budget check, then one final synthesis call. With `--enable-web-search`, only the research step receives OpenRouter's native web-search server tool; the final step synthesizes from the research notes without tools.

```bash
PYTHONPATH= uv run aeb run-tool-loop \
  --tasks data/tasks/public_efficiency_subset.jsonl \
  --model openai/gpt-5.4-nano \
  --category web_research \
  --limit 1 \
  --output-dir runs/tool-loop-smoke \
  --max-completion-tokens 256 \
  --enable-web-search \
  --max-suite-failures 1
```

Use `run-answer` for the cheapest single-call baseline. Use `run-tool-loop` when comparing scaffold overhead and whether a research/synthesis loop improves answer quality enough to justify the additional LLM call.

When `--n-trials` is greater than `1`, artifacts are written under per-task trial directories such as `runs/smoke/<task_id>/trial-000/trace.jsonl` and `runs/smoke/<task_id>/trial-001/trace.jsonl`. Telemetry rows carry `trial_index`, manifests record `trial_count` and executed `trial_indices`, and grouped reports can aggregate by `trial_index` or expose variance across repeated trials.

All three run commands (`run-answer`, `run-tool-loop`, and `run-assistantbench`) support suite-level safety cutoffs: `--max-suite-usd`, `--max-suite-seconds`, `--max-suite-tasks`, and `--max-suite-failures`. When one of these limits is reached, the current task finishes, the suite state is written to `manifest.json` under `suite_budget`, and the runner stops before starting the next task.

## 5. Run AssistantBench tasks

Closed-book baseline:

```bash
PYTHONPATH= uv run aeb run-assistantbench \
  --model openai/gpt-5.4-nano \
  --limit 1 \
  --mode closed_book \
  --output-dir runs/assistantbench-smoke
```

OpenRouter web-search mode. The mode name is kept for compatibility, but this now uses `tools=[{"type":"openrouter:web_search"}]` rather than the deprecated plugin API:

```bash
PYTHONPATH= uv run aeb run-assistantbench \
  --model openai/gpt-5.4-nano \
  --limit 1 \
  --mode openrouter_web_plugin \
  --output-dir runs/assistantbench-web-smoke
```

## 6. Score and report

```bash
PYTHONPATH= uv run aeb score-runs runs/smoke/run_telemetry.jsonl

PYTHONPATH= uv run aeb report \
  --tasks data/tasks/public_efficiency_subset.jsonl \
  --runs runs/smoke/run_telemetry.jsonl \
  --output runs/smoke/report.md

PYTHONPATH= uv run aeb report \
  --tasks data/tasks/public_efficiency_subset.jsonl \
  --runs runs/smoke/run_telemetry.jsonl \
  --manifest runs/smoke/manifest.json \
  --group-by category,model,tools_enabled,horizon,trial_index \
  --output runs/smoke/grouped-report.md
```

Each run output directory now includes a `manifest.json` with the run suite ID, git commit, task IDs, model, agent, scaffold, task file path, configured tools, budget metadata, and environment metadata. Trace files also record configured tools on `llm_call_start` and response annotations/citations on `llm_call_end` when OpenRouter returns them.

Grouped reports can use those telemetry fields to distinguish runs that enabled provider-side search even when a manifest is unavailable.

Repeated-trial summaries now also include simple variance signals such as standard deviation for cost, latency, total tokens, and quality. Use repeated trials for release-style model comparisons when budget allows; keep smoke checks at `--n-trials 1`.

## 6a. Two-mode AssistantBench calibration

Use the same small task slice in closed-book and web-search modes to compare the cost/latency lift from live search:

```bash
PYTHONPATH= uv run aeb run-assistantbench \
  --model openai/gpt-5.4-nano \
  --limit 1 \
  --mode closed_book \
  --output-dir runs/calibration-closed-book

PYTHONPATH= uv run aeb run-assistantbench \
  --model openai/gpt-5.4-nano \
  --limit 1 \
  --mode openrouter_web_plugin \
  --output-dir runs/calibration-web-search

PYTHONPATH= uv run aeb report \
  --tasks data/tasks/public_efficiency_subset.jsonl \
  --runs runs/calibration-web-search/run_telemetry.jsonl \
  --output runs/calibration-web-search/report.md
```

## 7. Official harness command adapters

Terminal-Bench command preview:

```bash
PYTHONPATH= uv run aeb terminal-bench-command \
  --task-id count-dataset-tokens \
  --model openai/gpt-5.4-nano
```

Terminal-Bench official harness dry run:

```bash
PYTHONPATH= uv run aeb run-terminal-bench-official \
  --task-id count-dataset-tokens \
  --model openai/gpt-5.4-nano \
  --output-dir runs/terminal-bench-official
```

Terminal-Bench official harness execute path. `--execute` is required for any command that can actually invoke Harbor/Docker or spend model tokens:

```bash
PYTHONPATH= uv run aeb run-terminal-bench-official \
  --task-id count-dataset-tokens \
  --model openai/gpt-5.4-nano \
  --output-dir runs/terminal-bench-official \
  --execute \
  --max-suite-usd 5.00 \
  --max-suite-failures 1
```

SWE-bench command preview:

```bash
PYTHONPATH= uv run aeb swe-bench-command \
  --predictions-path runs/swe/predictions.jsonl \
  --run-id smoke
```

SWE-bench official evaluation dry run:

```bash
PYTHONPATH= uv run aeb run-swe-bench-official \
  --predictions-path runs/swe/predictions.jsonl \
  --run-id smoke
```

SWE-bench official evaluation execute path. `--execute` is required for any command that can actually launch the official harness:

```bash
PYTHONPATH= uv run aeb run-swe-bench-official \
  --predictions-path runs/swe/predictions.jsonl \
  --run-id smoke \
  --execute \
  --max-suite-failures 1
```

tau2 official workflow dry run:

```bash
PYTHONPATH= uv run aeb run-tau2-official \
  --task-id tau2_bench_retail__55 \
  --model openai/gpt-5.4-nano \
  --output-dir runs/tau2-official
```

tau2 official workflow execute path. Because this repository does not pin the upstream tau2 runner command shape, `--execute` also requires an explicit `--runner-module` that knows how to run tau2 tasks in your environment:

```bash
PYTHONPATH= uv run aeb run-tau2-official \
  --task-id tau2_bench_retail__55 \
  --model openai/gpt-5.4-nano \
  --output-dir runs/tau2-official \
  --runner-module tau2.runner \
  --execute
```

These commands only print official harness invocations. They do not execute Docker containers or spend model tokens by themselves.

`run-terminal-bench-official` is separate from the preview command. By default it performs a prerequisite-aware dry run and prints the planned Harbor command, output path, and suite-budget metadata. Only `--execute` will attempt to run Harbor.

`run-swe-bench-official` is separate from the preview command. By default it performs a prerequisite-aware dry run and prints the planned evaluation command, report path, and suite-budget metadata. Only `--execute` will attempt to run the official SWE-bench harness.

`run-tau2-official` is separate from generic local answer/tool-loop runs. Its dry-run path validates normalized tau2 task mapping and records that the upstream runner command is unresolved unless you supply `--runner-module`. Only `--execute` with a configured runner module will attempt to run a tau2 workflow.

## Safety notes

- Failed runs still count toward aggregate cost, tokens, and latency.
- Budget-exceeded runs still count toward aggregate cost, tokens, and latency already consumed before the budget exit was detected.
- Suite-level budget limits stop the run before the next task starts and record the observed suite totals in `manifest.json`.
- `num_tool_calls` counts only local harness tool calls. OpenRouter server tools are reported separately through `server_tools_configured`, `num_annotations`, and `num_citations`.
- Full Terminal-Bench/SWE-bench runs require external official harness setup.
- `run-terminal-bench-official --execute` can invoke Docker/Harbor and spend real model tokens, so keep the default dry-run path until prerequisites and task mapping are confirmed.
- `run-swe-bench-official --execute` can launch the official SWE-bench harness, so keep the default dry-run path until predictions, report paths, and prerequisites are confirmed.
- `run-tau2-official --execute` is intentionally guarded and requires an explicit runner module because this repository does not yet pin a single upstream tau2 execution command.
- Always start with `--limit 1` and inspect trace files before scaling up.

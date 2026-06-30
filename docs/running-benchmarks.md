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
```

The current subset is intentionally small: 8 SWE-bench Lite tasks, 8 AssistantBench tasks, and 8 Terminal-Bench metadata tasks.

## 3. Verify OpenRouter connectivity

Without an API key, this should fail clearly:

```bash
PYTHONPATH= uv run aeb openrouter-smoke --model openai/gpt-4o-mini
```

With an API key:

```bash
export OPENROUTER_API_KEY="..."
PYTHONPATH= uv run aeb openrouter-smoke --model openai/gpt-4o-mini
```

## 4. Run one answer-only baseline task

```bash
PYTHONPATH= uv run aeb run-answer \
  --tasks data/tasks/public_efficiency_subset.jsonl \
  --model openai/gpt-4o-mini \
  --category web_research \
  --limit 1 \
  --output-dir runs/smoke \
  --max-completion-tokens 256
```

Outputs:

```text
runs/smoke/run_results.jsonl
runs/smoke/run_telemetry.jsonl
runs/smoke/<task_id>/trace.jsonl
```

## 5. Run AssistantBench tasks

Closed-book baseline:

```bash
PYTHONPATH= uv run aeb run-assistantbench \
  --model openai/gpt-4o-mini \
  --limit 1 \
  --mode closed_book \
  --output-dir runs/assistantbench-smoke
```

OpenRouter web plugin mode, if enabled for your account/model:

```bash
PYTHONPATH= uv run aeb run-assistantbench \
  --model openai/gpt-4o-mini \
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
```

## 7. Official harness command adapters

Terminal-Bench command preview:

```bash
PYTHONPATH= uv run aeb terminal-bench-command \
  --task-id count-dataset-tokens \
  --model openai/gpt-4o-mini
```

SWE-bench command preview:

```bash
PYTHONPATH= uv run aeb swe-bench-command \
  --predictions-path runs/swe/predictions.jsonl \
  --run-id smoke
```

These commands only print official harness invocations. They do not execute Docker containers or spend model tokens by themselves.

## Safety notes

- Failed runs still count toward aggregate cost, tokens, and latency.
- Full Terminal-Bench/SWE-bench runs require external official harness setup.
- Always start with `--limit 1` and inspect trace files before scaling up.

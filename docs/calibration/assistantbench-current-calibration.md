# AssistantBench Current-Code Calibration

Date: 2026-07-03

This note replaces older calibration observations with a small current-code spot check using the current manifest, provenance, and server-tool telemetry fields.

## Commands used

```bash
PYTHONPATH= uv run aeb run-assistantbench \
  --model openai/gpt-5.4-nano \
  --limit 1 \
  --mode closed_book \
  --output-dir runs/calibration-current-closed-book \
  --max-suite-usd 1 \
  --max-suite-tasks 1

PYTHONPATH= uv run aeb run-assistantbench \
  --model openai/gpt-5.4-nano \
  --limit 1 \
  --mode openrouter_web_plugin \
  --output-dir runs/calibration-current-web-search \
  --max-suite-usd 1 \
  --max-suite-tasks 1

PYTHONPATH= uv run aeb run-tool-loop \
  --tasks data/tasks/public_efficiency_subset.jsonl \
  --model openai/gpt-5.4-nano \
  --category web_research \
  --limit 1 \
  --output-dir runs/calibration-current-tool-loop \
  --max-completion-tokens 256 \
  --enable-web-search \
  --max-suite-usd 1 \
  --max-suite-tasks 1
```

All three runs targeted the same sampled AssistantBench task:

- `assistantbench__8ad84bd6fe38481ba49e7ad1f6fbd43219a999074e5c6fc940003281f55ec65b`

## Summary

| mode | scaffold | success | quality | wall_clock_seconds | input_tokens | output_tokens | estimated_usd | llm_calls | citations | annotations |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| closed_book | answer-only | false | 0.0 | 2.0537 | 75 | 166 | 0.000220275 | 1 | 0 | 0 |
| web_search | web-search-answer | false | 0.0 | 17.9127 | 12931 | 536 | 0.023023638 | 1 | 1 | 1 |
| tool_loop_web_search | react-tool-loop | false | 0.0 | 26.1145 | 26182 | 512 | 0.0440946792 | 2 | 0 | 0 |

## What changed versus older reports

- Manifests now include `budget`, `suite_budget`, `environment`, `source_revisions`, `evaluator`, and `provider` blocks.
- The OpenRouter runs preserved requested model `openai/gpt-5.4-nano` and observed returned model `openai/gpt-5.4-nano-20260317`.
- Provider provenance also preserved the upstream provider name `OpenAI`.
- Server-tool telemetry is now explicit: the web-search answer-only run recorded `server_tools_configured=["openrouter:web_search"]`, `num_citations=1`, and `num_annotations=1` while leaving `num_tool_calls=0`.

## Interpretation

This single-task spot check is not a benchmark claim. It is a current-code telemetry and evaluation sanity check.

- The closed-book baseline was extremely cheap and fast, but it failed the structured AssistantBench checks.
- Native OpenRouter web search materially increased spend and latency on the same task, but still failed the current structured checks for this prompt.
- The minimal tool-loop scaffold further increased cost and latency versus answer-only web search, while not improving the evaluation outcome on this one task.

For this task, the expected structured target included `text_contains=["Potash Markets - Clark Street"]` plus a citation requirement. None of the three runs satisfied the structured target. The web-search answer-only run at least returned one citation/annotation, while the tool-loop run did not surface citations in the final recorded telemetry.

## Manifest and provenance sanity check

Observed current-code manifest fields across all three runs:

- `source_revisions.AssistantBench/AssistantBench.revision = "dev"`
- `evaluator.name = "RegistryEvaluator"`
- `provider.requested_provider = "openrouter"`
- `provider.requested_model = "openai/gpt-5.4-nano"`
- `provider.returned_models = ["openai/gpt-5.4-nano-20260317"]`
- `suite_budget.terminated_by = "suite_budget_tasks"`

The suite termination reason was expected here because each calibration command intentionally set `--max-suite-tasks 1` to stop after a single task.

## Notes on artifacts

The raw run artifacts live under:

- `runs/calibration-current-closed-book`
- `runs/calibration-current-web-search`
- `runs/calibration-current-tool-loop`

They were generated for local inspection and are not required to be committed for the durable report to remain useful.
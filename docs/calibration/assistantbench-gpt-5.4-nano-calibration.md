# AssistantBench GPT-5.4 Nano Baseline Calibration

This baseline report compares the first closed-book and OpenRouter-native-web-search calibration runs for the same AssistantBench task.

## Commands Used

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
```

Raw `runs/` artifacts remain gitignored; this report captures the durable summary.

## Run Metadata

| Field | Closed-book | Web-search |
|---|---|---|
| Manifest | `runs/calibration-closed-book/manifest.json` | `runs/calibration-web-search/manifest.json` |
| Run suite ID | `suite-cb36f459e564` | `suite-d67e1e14bac0` |
| Git commit | `c263e3eabbf1653c4503ce23065d653980b1f5de` | `c263e3eabbf1653c4503ce23065d653980b1f5de` |
| Agent | `openrouter-answer` | `openrouter-answer` |
| Requested model | `openai/gpt-5.4-nano` | `openai/gpt-5.4-nano` |
| Returned model | `openai/gpt-5.4-nano-20260317` | `openai/gpt-5.4-nano-20260317` |
| Tools configured | none | `openrouter:web_search` |
| Task file | `data/tasks/public_efficiency_subset.jsonl` | `data/tasks/public_efficiency_subset.jsonl` |

## Task

| Field | Value |
|---|---|
| Task ID | `assistantbench__8ad84bd6fe38481ba49e7ad1f6fbd43219a999074e5c6fc940003281f55ec65b` |
| Expected answer | `Potash Markets - Clark Street` |
| Task type | Web research / local supermarket lookup |
| Prompt summary | Identify a supermarket near Lincoln Park with ready-to-eat salads under $15. |

## Metrics

| Metric | Closed-book | Web-search |
|---|---:|---:|
| Success | `false` | `false` |
| Quality score | `0.0` | `0.0` |
| Wall-clock seconds | `2.213680` | `9.510537` |
| LLM time seconds | `2.210696` | `9.508413` |
| Input tokens | `75` | `17,899` |
| Output tokens | `184` | `457` |
| Total tokens | `259` | `18,356` |
| Estimated USD | `$0.00024255` | `$0.0338095395` |
| LLM calls | `1` | `1` |
| Local tool calls | `0` | `0` |
| Terminated by | `evaluated` | `evaluated` |

## Tool and Citation Observations

Closed-book trace observations:

- `llm_call_start` recorded `tools_configured: []`.
- `llm_call_end` recorded no annotations and no citations.
- The answer stated that it could not reliably determine current local supermarket/pricing data without live access.

Web-search trace observations:

- `llm_call_start` recorded `tools_configured: ["openrouter:web_search"]`.
- The OpenRouter native web-search tool payload was recorded as `{"type": "openrouter:web_search", "parameters": {"engine": "native"}}`.
- `llm_call_end` contained two `url_citation` annotations.
- Extracted citation URLs:
  - `https://www.doordash.com/business/trader-joes-3947/menu`
  - `https://www.jewelosco.com/home/pre-made-salad.html`

## Output Comparison

| Mode | Output summary | Evaluation |
|---|---|---|
| Closed-book | Refused to assert a concrete supermarket and asked for location/source clarification. | Failed exact-answer check. |
| Web-search | Suggested Trader Joe's and Jewel-Osco with citations but did not identify the expected `Potash Markets - Clark Street`. | Failed exact-answer check. |

## Takeaways

1. The calibration loop works end-to-end: manifests, telemetry JSONL, result JSONL, and trace JSONL were generated for both modes.
2. OpenRouter native web search is being configured and recorded correctly.
3. OpenRouter returned citation metadata in the web-search run, and the harness captured both raw annotations and extracted citation URLs.
4. Web search substantially increased cost and token usage on this task: total tokens increased from `259` to `18,356`, and estimated cost increased from `$0.00024255` to `$0.0338095395`.
5. Web search produced a more grounded answer but did not improve exact-answer correctness on this specific task.
6. `num_tool_calls` remains `0` because OpenRouter server-side search is not a local harness tool call; reporting should continue to distinguish local tool calls from provider-side server tool availability/metadata.

## Known Limitations

- The current exact-match evaluator is too brittle for this web-research style task.
- The run predated manifest budget/environment population, so the raw calibration manifests still show empty `budget` and `environment` fields.
- Scaffold identity is still not populated in telemetry.
- This is a single-task calibration and should not be interpreted as a stable model ranking.

## Next Recommended Experiment

Run a small 4-8 task AssistantBench sample in both modes after regenerating manifests with budget/environment metadata. Then generate a grouped report using:

```bash
PYTHONPATH= uv run aeb report \
  --tasks data/tasks/public_efficiency_subset.jsonl \
  --runs runs/calibration-web-search/run_telemetry.jsonl \
  --manifest runs/calibration-web-search/manifest.json \
  --group-by category,model,tools_enabled,horizon \
  --output runs/calibration-web-search/grouped-report.md
```

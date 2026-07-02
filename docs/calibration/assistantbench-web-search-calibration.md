# AssistantBench Web Search Calibration

This report compares the first one-task AssistantBench calibration run in closed-book mode versus OpenRouter native web-search mode.

## Run Identity

| Field | Closed-book | Web-search |
|---|---:|---:|
| Manifest | `runs/calibration-closed-book/manifest.json` | `runs/calibration-web-search/manifest.json` |
| Run suite ID | `suite-cb36f459e564` | `suite-d67e1e14bac0` |
| Agent | `openrouter-answer` | `openrouter-answer` |
| Requested model | `openai/gpt-5.4-nano` | `openai/gpt-5.4-nano` |
| Returned model | `openai/gpt-5.4-nano-20260317` | `openai/gpt-5.4-nano-20260317` |
| Git commit | `c263e3eabbf1653c4503ce23065d653980b1f5de` | `c263e3eabbf1653c4503ce23065d653980b1f5de` |
| Task ID | `assistantbench__8ad84bd6fe38481ba49e7ad1f6fbd43219a999074e5c6fc940003281f55ec65b` | `assistantbench__8ad84bd6fe38481ba49e7ad1f6fbd43219a999074e5c6fc940003281f55ec65b` |
| Tools configured | none | `openrouter:web_search` |

The two manifests have matching task IDs, agent, requested model, returned model family, task source path, and git commit. The intended mode difference is captured correctly: closed-book has no tools, while web-search configures OpenRouter native search.

## Metrics Comparison

| Metric | Closed-book | Web-search | Difference |
|---|---:|---:|---:|
| Success | `false` | `false` | no change |
| Quality score | `0.0` | `0.0` | no change |
| Wall-clock seconds | `2.213680` | `9.510537` | `+7.296857` |
| LLM time seconds | `2.210696` | `9.508413` | `+7.297717` |
| Input tokens | `75` | `17,899` | `+17,824` |
| Output tokens | `184` | `457` | `+273` |
| Total tokens | `259` | `18,356` | `+18,097` |
| Estimated USD | `$0.00024255` | `$0.0338095395` | `+$0.0335669895` |
| LLM calls | `1` | `1` | no change |
| Local tool calls | `0` | `0` | no change |
| Terminated by | `evaluated` | `evaluated` | no change |

## Trace Observations

### Closed-book trace

- `llm_call_start` includes `tools_configured: []`.
- `llm_call_end` includes no annotations and no citations.
- The answer explicitly states uncertainty and asks for more information because live local inventory/pricing data is unavailable.

### Web-search trace

- `llm_call_start` includes `tools_configured: ["openrouter:web_search"]`.
- The full tool payload is present: `{"type": "openrouter:web_search", "parameters": {"engine": "native"}}`.
- `llm_call_end` includes two `url_citation` annotations and two extracted citation URLs:
  - `https://www.doordash.com/business/trader-joes-3947/menu`
  - `https://www.jewelosco.com/home/pre-made-salad.html`
- `num_tool_calls` remains `0` because OpenRouter server-side search happens inside a single provider call and is not currently exposed as a local harness tool call.

## Answer Comparison

| Mode | Answer summary | Evaluation result |
|---|---|---|
| Closed-book | Could not determine the answer reliably without live local supermarket/pricing data. | Failed exact-answer evaluation. Expected `Potash Markets - Clark Street`. |
| Web-search | Suggested Trader Joe's and Jewel-Osco with citations. It did not identify the expected answer. | Failed exact-answer evaluation. Expected `Potash Markets - Clark Street`. |

## Findings

1. **Instrumentation is working.** The manifests, telemetry, results, and traces all exist for both modes. Web-search mode correctly records `openrouter:web_search` in both the manifest and trace.
2. **OpenRouter returned grounding metadata.** The web-search trace captured both raw annotations and extracted citation URLs.
3. **Server-side search is expensive relative to closed-book on this task.** The web-search run used about 70.9x more total tokens and about 139.4x more estimated USD than closed-book.
4. **Web search changed the answer but did not improve correctness for this task.** The searched answer was more grounded, but still failed the expected exact answer.
5. **Current telemetry does not count provider-side server tools as `num_tool_calls`.** This is expected in the current implementation but should be represented separately in future reporting, e.g. `server_tools_configured` or `server_tool_observations`.

## Telemetry Gaps / Follow-up Issues

- `RunManifest.budget` and `RunManifest.environment` are still empty; this is already tracked as Task 2 in `plan-state.md`.
- `RunTelemetry.scaffold` is currently omitted/null, making scaffold-level reporting weaker; this is tracked in Task 9.
- `num_tool_calls` only tracks local harness tools and does not represent OpenRouter server-side tool use.
- Exact-match evaluation is too brittle for many web-research tasks. This task likely needs a more structured evaluator that can account for cited sources, candidate entities, and partial correctness.
- Reporting currently requires manual side-by-side comparison for separate run directories; grouped reporting by model/scaffold/tools is tracked in Task 3.

## Verification

The calibration artifacts reviewed were:

- `runs/calibration-closed-book/manifest.json`
- `runs/calibration-closed-book/run_telemetry.jsonl`
- `runs/calibration-closed-book/run_results.jsonl`
- `runs/calibration-closed-book/assistantbench__8ad84bd6fe38481ba49e7ad1f6fbd43219a999074e5c6fc940003281f55ec65b/trace.jsonl`
- `runs/calibration-web-search/manifest.json`
- `runs/calibration-web-search/run_telemetry.jsonl`
- `runs/calibration-web-search/run_results.jsonl`
- `runs/calibration-web-search/assistantbench__8ad84bd6fe38481ba49e7ad1f6fbd43219a999074e5c6fc940003281f55ec65b/trace.jsonl`

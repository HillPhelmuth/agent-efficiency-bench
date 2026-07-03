# OpenRouter Execution

Agent Efficiency Bench uses OpenRouter as the model provider for live model calls.

## Environment variables

```bash
export OPENROUTER_API_KEY="..."
export OPENROUTER_APP_TITLE="Agent Efficiency Bench"          # optional
export OPENROUTER_HTTP_REFERER="https://github.com/local/aeb" # optional
```

Commands that call models fail fast if `OPENROUTER_API_KEY` is missing.

## Smoke test

Use a cheap model and a tiny output cap before running any benchmark task:

```bash
PYTHONPATH= uv run aeb openrouter-smoke --model openai/gpt-5.4-nano
```

The command prints the returned model, generation ID, prompt tokens, completion tokens, cost, latency, and response content.

## Web search tools

OpenRouter's deprecated `plugins=[{"id":"web"}]` and `:online` model suffix paths are not used. Benchmarks that need current web information should pass the server-tool configuration through `ModelConfig.tools`:

```json
{
  "tools": [
    {"type": "openrouter:web_search", "parameters": {"engine": "auto"}}
  ]
}
```

`OpenRouterClient.chat(...)` forwards `tools` and optional `tool_choice` into the Chat Completions request. `run-assistantbench --mode openrouter_web_plugin` keeps the historical mode name for compatibility, but now configures `openrouter:web_search` instead of the deprecated plugin API.

Provider-side server tool usage is tracked separately from local harness tool calls:

- `RunTelemetry.server_tools_configured` records configured OpenRouter server tools such as `openrouter:web_search`.
- `RunTelemetry.num_annotations` records how many response annotations OpenRouter returned.
- `RunTelemetry.num_citations` records how many citation URLs were extracted from the response.
- `RunTelemetry.num_tool_calls` remains local-harness-only and does not count provider-side server tool execution inside a single OpenRouter response.

## Usage and cost accounting

The OpenRouter client records usage from the chat completion response:

- `usage.prompt_tokens`
- `usage.completion_tokens`
- `usage.total_tokens`
- `usage.cost`

If cost is missing and OpenRouter returned a generation ID, the client can query:

```text
GET https://openrouter.ai/api/v1/generation?id=<generation_id>
```

Local token estimates are not used for authoritative accounting. If usage is missing, the run should be treated as telemetry-incomplete rather than silently estimated.

Trace JSONL files record configured tools on `llm_call_start` plus raw annotations and extracted citations on `llm_call_end`. Reports can then summarize whether server tools were enabled and how much grounding metadata a run returned.

## Reproducibility notes

OpenRouter may route a model ID to different upstream providers. For comparison runs:

- Record both requested model and returned model.
- Preserve any upstream provider or routing metadata that OpenRouter returns.
- Keep temperature at `0.0` unless stochasticity is intentional.
- Use fixed task subsets.
- Repeat important runs to measure variance.
- Keep trace JSONL files as audit evidence.

Current manifests record OpenRouter provenance under `provider`, including the requested provider/model plus any observed returned models, upstream providers, or routing hints surfaced in run output.

## Cost safety

Start with:

```text
limit: 1
category: web_research
max_completion_tokens: 256
```

For generic web-research runs that should use OpenRouter native search, pass:

```bash
PYTHONPATH= uv run aeb run-answer \
  --model openai/gpt-5.4-nano \
  --category web_research \
  --limit 1 \
  --enable-web-search
```

Do not run Terminal-Bench or SWE-bench full harnesses until you have confirmed Docker/official harness setup and budget caps.
